"""THE HORN SURFACE: the HIGH of a horn as voxel strokes on its block-out (work/bestiary/research/DEER_PLAN.md §5.3;
the horn generator families/horn.py gives the skeleton and the block-out program; the build's notes
work/bestiary/deer/horns/build_NOTES.md). One module for every horn family and for hooves (the hoof builder's growth
rings come here as a stroke kind of their own): THE INTERFACE IS

    pl = plan(skel, prog, seed)          every stroke as numpy rows, in metres, seated on the block-out. Pure data:
                                         the same plan builds the high at any voxel size, and the UV stage reads its
                                         gutter lines (seams hide in gutters)
    G = build(skel, prog, pl, voxel)     a voxel.SparseSDF of the block-out with the strokes applied and relevelled:
                                         the field forge/bake.py bakes from (normal, AO, cavity, curvature, position)
    HORN_IDS                             the material ids the strokes write (the bake's 'mat' channel): the skin
                                         stage (families/horn_skin.py) reads them as masks

THE ANTLER'S TIERS, read off the photos (deer/horns/refs/c11: Cervus_elaphus_AM_LM369-6 and -9, Rothirsch
Geweihansatz 070816 1, Cervus elaphus 01 by-dpc), all sized in the preset's millimetres and scaled with the part:
  BEADS    the burr's crust: fused nodules 2-6 mm across in three uneven rows on the rim, small ones over all of
           it, the beam's furrows cut into its upper edge (the preset's `burr` rows)
  GUTTERS  the vessel grooves: long meandering channels along every branch, 5-10 mm apart and up to 1.6 mm deep on
           the lower beam, shallower up the tines, gone where the tips are polished
  PEARLS   rice-grain bumps 2-5 mm long on the ridges between gutters, big and crowded near the burr, thinning out
           up each branch, none on the polished tips; each lies ALONG its branch
  GRAIN    the fine fluting everywhere below the polished tips: shallow grooves 2-3 mm apart along the branch, in
           staggered lengths that start, stop and merge (the photos show no smooth plain between the channels: the
           first high had them and read as engraved clay, build/look/h09_look_trunk_a.png), with small pearls on the
           ridges between them
Every stroke is SEATED: its foot is a point of its branch's own measured section pushed out along the section's
radius onto the block-out's zero set (sdf.Program.project), so a pattern follows the blended fork it crosses, and a
foot buried in another branch is dropped (the beam's lines stop under a tine's root).
"""
import numpy as np

from .. import voxel as VX

# material ids of the horn strokes: above the growth range 1-63 (bake.py's growth-occlusion test drops those) and the
# cyborg range 64-95. STAGED for growth.ID_RANGES as horn=(96, 111) (work/bestiary/deer/STAGED.md)
HORN_IDS = dict(bead=96, pearl=97, gutter=98, ring=99, grain=100)
HORN_RANGE = (96, 111)
BATCHES = ('grain', 'gutters', 'notches', 'pearls', 'beads')        # the order the strokes are applied in


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-30)


def H_sstep(x):
    x = np.clip(np.asarray(x, np.float64), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def seat(prog, br, s, theta, maxd=0.008):
    """points of branch br at (s, theta) seated on the block-out: (P (n, 3), N the block-out's outward normal, ok).
    A foot that finds no surface within maxd along its section radius is buried in another branch: ok False"""
    s = np.asarray(s, np.float64)
    theta = np.asarray(theta, np.float64)
    p, n, b, _ = br.frame(s)
    d = np.cos(theta)[:, None] * n + np.sin(theta)[:, None] * b
    P0 = p + np.asarray(br.radius(s, theta))[:, None] * d
    # the march starts 5 um INSIDE the section: a foot exactly on the surface reads f = 0.0, which project() takes
    # for "outside" and marches INWARD, through the branch, to the far wall (found with maxd 30 mm: the cage's shaft
    # rings came back on the opposite side of their tines, folds of 180 deg; build/out/h06_low_report.json, 20:1x)
    P, st = prog.project(P0 - d * 5.0e-6, d, maxd=maxd)
    # NOT `st == 0`: a foot that starts exactly ON the surface (f = +-0.0: every foot away from a fork, the branch's
    # section and the sweep agree to < 0.1 um) finds no sign change to bracket and comes back by the Newton
    # fallback, status 1, unmoved and right. Measured on the brow: 11 of 40 feet of one line, which cut every
    # gutter into dashes (build/look/h05_high_regions_a.png). The test is the result: on the zero set, within reach
    ok = (np.abs(prog.eval(P)) < 2.0e-6) & (np.linalg.norm(P - P0, axis=1) <= maxd)
    N = prog.normals(P)
    return P, _unit(N), ok


def _envelopes(br, s, polish_from, top_from=None):
    """how strongly gutters and pearls stand at arc length s of a branch (0-1 each): full on the lower beam, fading
    up each tine, zero on the polished tips. top_from: on the beam, the arc length of the last fork (its end beyond
    it tapers as a tine)"""
    L = br.length
    if br.kind == 'beam':
        u = s / L
        g = np.interp(u, [0.0, 0.55, 0.80, 0.93, 1.0], [1.0, 1.0, 0.45, 0.0, 0.0])
        p = np.interp(u, [0.0, 0.06, 0.30, 0.60, 0.80, 0.90, 1.0], [1.0, 1.0, 0.75, 0.55, 0.25, 0.0, 0.0])
        if top_from is not None:
            ut = np.clip((s - top_from) / max(L - top_from, 1e-9), 0.0, 1.0)
            fade = np.interp(ut, [0.0, 0.25, polish_from, 1.0], [1.0, 0.7, 0.0, 0.0])
            g = np.where(s > top_from, np.minimum(g, fade), g)
            p = np.where(s > top_from, np.minimum(p, fade), p)
        return g, p
    u = s / L
    g = np.interp(u, [0.0, 0.10, 0.40, polish_from, 1.0], [0.75, 0.75, 0.40, 0.0, 0.0])
    # (fix round 1: a living prime stag's tines are COARSELY PEARLED up to their short ivory ends, refs c11 Richmond
    # Park 2025 01: the pearls held 0.7 only to 0.10 of a tine and were gone by 0.56, so every tine was a smooth fang)
    p = np.interp(u, [0.0, 0.15, 0.45, polish_from - 0.08, 1.0], [0.85, 0.80, 0.55, 0.0, 0.0])
    return g, p


def _grain_envelopes(br, s, polish_from, top_from, mm):
    """the grain's strength and the ridge pearls' chance at arc length s (0-1 each). The grain runs higher than
    the channels (a tine is fluted until its polish starts); the small pearls crowd the first hand's breadth above
    the burr and the tines' bases, and thin out fast"""
    L = br.length
    u = s / L
    if br.kind == 'beam':
        g = np.interp(u, [0.0, 0.60, 0.86, 0.96, 1.0], [1.0, 1.0, 0.55, 0.0, 0.0])
        # (fix round 1: a living prime stag's beam is pearled its whole length, refs c11 Richmond Park 2025 01; the
        # cast antler's lower beam only, 0.50 at 130 mm and 0.10 at 600, was the first table)
        p = np.interp(s / mm, [0.0, 60.0, 130.0, 300.0, 600.0, 880.0], [0.95, 0.92, 0.85, 0.78, 0.65, 0.25])
        if top_from is not None:
            ut = np.clip((s - top_from) / max(L - top_from, 1e-9), 0.0, 1.0)
            fade = np.interp(ut, [0.0, 0.35, min(polish_from + 0.10, 0.95), 1.0], [1.0, 0.75, 0.0, 0.0])
            g = np.where(s > top_from, np.minimum(g, fade), g)
            p = np.where(s > top_from, np.minimum(p, fade * 0.3), p)
        return g, p
    g = np.interp(u, [0.0, 0.15, 0.50, min(polish_from + 0.08, 0.95), 1.0], [0.9, 0.9, 0.6, 0.0, 0.0])
    p = np.interp(u, [0.0, 0.15, 0.45, polish_from - 0.06, 1.0], [0.85, 0.82, 0.62, 0.0, 0.0])      # (fix round 1)
    return g, p


def _run_gap(ok, step):
    """per point of a run of feet the distance (metres along the run) to the nearest foot that found no seat"""
    n = len(ok)
    pos = np.arange(n)
    bad = ~ok
    last = np.maximum.accumulate(np.where(bad, pos, -10 ** 9))
    nxt = np.minimum.accumulate(np.where(bad, pos, 10 ** 9)[::-1])[::-1]
    return np.minimum(pos - last, nxt - pos) * step


def _pearls(prog, br, rng, sf, mm, sp, thp, near, size, pA, pB, pRa, pRb, round_frac=0.0):
    """pearls at (sp, thp) of a branch, appended to the stroke lists. A pearl is a SPINDLE lying ALONG its branch (a
    rice grain: thick in the middle, running out at both ends): two round cones end to end, never a capsule (those
    read as pills). size scales it (the grain's ridge pearls are smaller); near (0-1) grows the ones by the burr"""
    L = br.length
    n = len(sp)
    # sizes skewed small (many grains, a few knobs); lengths from a round dot to a short ridge. One even draw of
    # both made every pearl the same lozenge with the same outline (build/look/h05_high_regions_d_grain.png)
    rad = (sf['pearl_r'][0] + (sf['pearl_r'][1] - sf['pearl_r'][0]) * rng.uniform(0.0, 1.0, n) ** 2.0) * \
        mm * size * (1.0 + 0.5 * near)
    half = (sf['pearl_len'][0] * 0.45 + (sf['pearl_len'][1] * 1.5 - sf['pearl_len'][0] * 0.45) *
            rng.uniform(0.0, 1.0, n) ** 1.6) * mm * size * (1.0 + 0.5 * near)
    # (fix round 1) THREE SHAPES, not one: 8 % big round tubercles, 12 % run into a short RIDGE (a crest segment),
    # the rest grains. One bean form in one width read as rows of identical pale dashes (the check's item 6)
    kind = rng.uniform(0.0, 1.0, n)
    big, chain = kind < 0.08, (kind >= 0.08) & (kind < 0.20)
    rad = np.where(big, rad * 1.5, rad)
    half = np.where(big, half * 0.6, np.where(chain, half * 2.2, half))
    # round_frac of them (the grain's crest pearls on a living stag: the preset's `round_pearls`) are round
    # TUBERCLES, half as long as they are wide to a little longer, not grains along the branch
    rnd = (rng.uniform(0.0, 1.0, n) < round_frac) & ~chain
    half = np.where(rnd, rad * rng.uniform(0.5, 1.4, n), half)
    rise = rad * rng.uniform(0.32, 0.62, n) * (1.0 + 0.3 * near)             # the top above the surface
    # its three points a little off the branch's line, in MILLIMETRES of arc: an ANGLE of 0.09 put the ends 3 mm
    # aside on the 35 mm trunk, and 4 mm grains lay diagonal like scattered leaves (build/look/h09_look_trunk_a.png)
    r_here = np.maximum(br.lerp(br.r0, sp), 2.0 * mm)
    off = rng.uniform(-0.45, 0.45, (3, n)) * rad / r_here
    Pa, Na, oka = seat(prog, br, np.maximum(sp - half, 1e-4), thp + off[0])
    Pm, Nm, okm = seat(prog, br, np.clip(sp + half * rng.uniform(-0.4, 0.4, n), 1e-4, L - 1e-4), thp + off[1])
    Pb, Nb, okb = seat(prog, br, np.minimum(sp + half, L - 1e-4), thp + off[2])
    okp = oka & okb & okm
    # a bean, never a lozenge: the two ends' radii and heights drawn apart (0.30-0.48 of the middle read as thorns,
    # one shared share as a cut gem)
    ta, tb = rng.uniform(0.50, 0.95, n), rng.uniform(0.50, 0.95, n)
    ha, hb = rng.uniform(0.25, 0.8, n), rng.uniform(0.25, 0.8, n)
    Ca = (Pa + Na * (rise * ha - rad * ta)[:, None])[okp]
    Cm = (Pm + Nm * (rise - rad)[:, None])[okp]
    Cb = (Pb + Nb * (rise * hb - rad * tb)[:, None])[okp]
    pA += [Ca, Cm]
    pB += [Cm, Cb]
    pRa += [(rad * ta)[okp], rad[okp]]
    pRb += [rad[okp], (rad * tb)[okp]]


def plan(skel, prog, seed=11, log=print):
    """every stroke of the antler's surface, seated. Returns a dict of batches, each dict(kind, A, B, ra, rb, mode,
    k, mat), plus 'lines': the gutters' polylines per branch (for the UV seams) and 'extra' (bead bounding spheres
    for the grid's band)"""
    rng = np.random.default_rng(seed)
    pr = skel.preset
    sf = pr['surface']
    mm = skel.scale * 1.0e-3
    pitch = sf['gutter_pitch'] * mm
    dep0, dep1 = sf['gutter_depth'][0] * mm, sf['gutter_depth'][1] * mm
    wid0, wid1 = sf['gutter_width'][0] * mm, sf['gutter_width'][1] * mm
    beam = skel.branches[0]
    top_from = max(beam.meta.get('stations', {}).values()) if beam.meta.get('stations') else None
    gA, gB, gRa, gRb = [], [], [], []
    pA, pB, pRa, pRb = [], [], [], []
    nA, nB, nRa, nRb = [], [], [], []
    lines = {}
    burr_feet = []                 # the angles round the beam at which a channel starts on the burr
    step = 2.5 * mm
    for br in skel.branches:
        if br.kind == 'rim':
            continue
        L = br.length
        s0 = (14.0 * mm) if br.kind == 'beam' else 0.6 * float(br.r0[0])
        s_ref = min(0.2 * L + s0, L * 0.5)
        n_main = max(6, int(round(br.girth(s_ref) / pitch)))
        n_base = max(0, int(round(br.girth(s0 + 4.0 * mm) / pitch)) - n_main) if br.kind == 'beam' else 0
        dth = 2.0 * np.pi / n_main
        th0 = (np.arange(n_main) + rng.uniform(-0.36, 0.36, n_main)) * dth
        late = 0.04 if br.kind == 'beam' else 0.14          # no two channels of a tine start at one station
        # (start, end, angle at the start, angle gained by the end): the main channels run the branch; short ones
        # crowd the beam's base; BRAIDS leave a main channel and run into its neighbour (channels join at a
        # slant, as on the lower beam of refs c11 LM369-9; they never cross square: the first plan's random side
        # channels made X crossings, build/look/h05_high_regions_a.png)
        spans = [(s0 + rng.uniform(0.0, late) * L, L * rng.uniform(0.82, 1.0), t, 0.0) for t in th0]
        spans += [(s0, s0 + rng.uniform(40.0, 150.0) * mm, (j + 0.5 + rng.uniform(-0.2, 0.2)) * dth * n_main /
                   max(n_base, 1), 0.0) for j in range(n_base)]
        for _ in range(n_main // 2):
            sa = rng.uniform(0.05, 0.6) * L
            spans.append((sa, sa + rng.uniform(30.0, 85.0) * mm, th0[rng.integers(n_main)],
                          dth * rng.choice([-1.0, 1.0]) * rng.uniform(0.7, 1.0)))
        # the bundle's shared slow swing (every channel of a branch leans the same way at the same place)
        lam1, ph1, amp1 = rng.uniform(70.0, 140.0) * mm, rng.uniform(0, 6.28), rng.uniform(1.0, 2.2) * mm
        br_lines = []
        for (sa, sb, t0, gain) in spans:
            sb = min(sb, L - 1.5 * mm)
            if sb - sa < 12.0 * mm:
                continue
            # THE BEAM'S FURROWS RUN INTO THE BURR (11-12; refs c11 Rothirsch Geweihansatz 070816 1: the grooves
            # of the lower beam stand deep right down to the crust and notch its upper edge). A channel that starts
            # within 12 mm of the burr is at its depth 6 mm from its start (every other end fades over 22 mm: a
            # channel that starts out on the open beam comes out of nothing), and the crust is notched where it
            # arrives (`burr_feet`)
            at_burr = br.kind == 'beam' and sa < s0 + 12.0 * mm
            s = np.arange(sa, sb, step)
            lam2, lam3 = rng.uniform(18.0, 34.0) * mm, rng.uniform(35.0, 70.0) * mm
            r_here = np.maximum(br.lerp(br.r0, s), 2.0 * mm)
            # the meander in MILLIMETRES of arc (so thin tines do not swing wider than the beam)
            arc = (amp1 * np.sin(2.0 * np.pi * s / lam1 + ph1)
                   + rng.uniform(0.3, 0.9) * mm * np.sin(2.0 * np.pi * s / lam2 + rng.uniform(0, 6.28)))
            th = t0 + arc / r_here + gain * H_sstep((s - sa) / max(sb - sa, 1e-9))
            # a channel lives only where its branch's OWN section is the surface (within 2.5 mm): in a fork's saddle
            # the block-out is the blend, the feet of two branches' channels land on each other, and the saddle
            # came out as a star of colliding grooves (build/look/h05_high_regions_b.png). Saddles stay smooth
            P, N, ok = seat(prog, br, s, th, maxd=2.5 * mm)
            # each channel fades at its OWN height (one polish line for all of them reads as a machined stop)
            pf = sf['polish_from'] * rng.uniform(0.74, 1.08)
            env, penv = _envelopes(br, s, pf, top_from if br.kind == 'beam' else None)
            e_in = np.minimum(np.clip((s - sa) / ((6.0 if at_burr else 22.0) * mm), 0.0, 1.0),
                              np.clip((sb - s) / (22.0 * mm), 0.0, 1.0))
            if at_burr:
                burr_feet.append(float(th[0]))
            if (~ok).any():                      # ... and runs out to a point where a saddle or a root cuts it
                idx = np.arange(len(s))
                gap = np.abs(idx[:, None] - idx[~ok][None, :]).min(axis=1) * step
                e_in = np.minimum(e_in, np.clip(gap / (16.0 * mm), 0.0, 1.0))
            # a channel pinches and swells along its run, and runs out to a point at each end
            swell = 0.78 + 0.22 * np.sin(2.0 * np.pi * s / lam3 + rng.uniform(0, 6.28))
            # a FEW channels are deep and most are shallow (the cast antler's lower flank has two or three dark
            # grooves among many faint ones: refs c11 dpc); an even draw made every line an engraved cut
            w = env * swell * (0.30 + 0.70 * rng.uniform() ** 1.8)
            depth = (dep0 + (dep1 - dep0) * w) * np.clip(w * 3.0, 0.0, 1.0) * e_in ** 0.8
            width = (wid0 + (wid1 - wid0) * w) * (0.25 + 0.75 * e_in ** 0.7)
            # a groove of depth d and width w is a round stroke of radius rho whose axis stands h over the surface
            rho = (width * width / 4.0 + depth * depth) / np.maximum(2.0 * depth, 1e-9)
            h = rho - depth
            C = P + N * h[:, None]
            good = ok & (depth > 0.08 * mm)
            seg = good[:-1] & good[1:]
            gA.append(C[:-1][seg])
            gB.append(C[1:][seg])
            gRa.append(rho[:-1][seg])
            gRb.append(rho[1:][seg])
            br_lines.append(dict(s=s[good], theta=th[good], P=P[good]))
            # PEARLS on the ridge beside this gutter (half a pitch round), spaced along it
            sp = sa + np.cumsum(rng.uniform(5.0, 11.0, max(4, int((sb - sa) / (4.0 * mm)))) * mm)
            sp = sp[sp < sb]
            if not len(sp):
                continue
            keep = rng.uniform(0.0, 1.0, len(sp)) < np.interp(sp, s, penv) * 1.6
            sp = sp[keep]
            if not len(sp):
                continue
            thp = np.interp(sp, s, th) + (0.5 * pitch + rng.uniform(-0.18, 0.18, len(sp)) * pitch) / \
                np.maximum(br.lerp(br.r0, sp), 2.0 * mm)
            near = np.clip(1.0 - (sp - s0) / (70.0 * mm), 0.0, 1.0) if br.kind == 'beam' else np.zeros(len(sp))
            _pearls(prog, br, rng, sf, mm, sp, thp, near, 1.0, pA, pB, pRa, pRb)
        lines[br.name] = br_lines
        # ---- THE GRAIN: the fine fluting between the channels, and the small pearls on its ridges. The branch is
        # laid in staggered WINDOWS along its length; each window has its own count of columns round the branch
        # (the girth changes: columns merge where the branch thins), each column one shallow groove that overruns
        # its window's ends by a random share, so lines start, stop and overlap everywhere and none is a rail.
        # Every groove leans with the bundle's shared swing (amp1 / lam1: the channels' own), so the grain never
        # crosses a channel square
        gp = sf.get('grain_pitch', 0.0) * mm
        if gp > 0.0:
            gd0, gd1 = sf['grain_depth'][0] * mm, sf['grain_depth'][1] * mm
            gw0, gw1 = sf['grain_width'][0] * mm, sf['grain_width'][1] * mm
            win = sf.get('grain_window', 55.0) * mm
            gstep = 3.0 * mm
            rows, ps, pth = [], [], []
            a = s0
            while a < L - 8.0 * mm:
                b = min(a + win * rng.uniform(0.75, 1.3), L - 1.5 * mm)
                n = max(5, int(round(br.girth(0.5 * (a + b)) / gp)))
                dcol = 2.0 * np.pi / n
                thc = (np.arange(n) + rng.uniform(-0.28, 0.28, n)) * dcol + rng.uniform(0.0, dcol)
                over = rng.uniform(0.0, 0.4, (n, 2)) * win
                rows.append(np.column_stack([np.maximum(a - over[:, 0], s0), np.minimum(b + over[:, 1], L - 1.5 * mm),
                                             thc, rng.uniform(-0.6, 0.6, n) * dcol, rng.uniform(0.0, 1.0, n) ** 1.5,
                                             rng.uniform(0.3, 1.0, n) * mm, rng.uniform(14.0, 30.0, n) * mm,
                                             rng.uniform(0.0, 6.28, n), rng.uniform(0.80, 1.12, n),
                                             rng.uniform(9.0, 26.0, n) * mm, rng.uniform(0.0, 6.28, n)]))
                # the ridge crests of this window (half a column round), a pearl every 3.5-12 mm along each, each
                # pearl off the crest by up to a third of a column (fix round 1: at +-0.12 of a column and 5-11 mm
                # the pearls stood in ROWS of identical pale dashes, the check's board a row 3; the photos' pearling
                # is a scatter of tubercles that merge into the crests, refs c11 Richmond Park 2025 01)
                # (and the second look, beside refs c11 Richmond Park 2025 01 at matched size: a living stag's beam
                # and tines are a CRUST of round tubercles a few mm apart; the first spacing left smooth flutes
                # between sparse grains: 2.4-6 mm now)
                km = int((b - a) / (2.4 * mm)) + 1
                sp = a + np.cumsum(rng.uniform(2.4, 6.0, (n, km)) * mm, axis=1) - rng.uniform(0.0, 5.0, (n, 1)) * mm
                tp = (thc + 0.5 * dcol)[:, None] + rng.uniform(-0.34, 0.34, (n, km)) * dcol
                m = (sp > a) & (sp < b)
                ps.append(sp[m])
                pth.append(tp[m])
                a = b
            R = np.concatenate(rows)
            sa, sb, t0, lean, strength, wig, lam2, ph2, reach, lam3, ph3 = R.T
            cnt = np.maximum(((sb - sa) / gstep).astype(int) + 1, 2)
            idx = np.repeat(np.arange(len(cnt)), cnt)
            first = np.cumsum(cnt) - cnt
            u = (np.arange(int(cnt.sum())) - first[idx]) / (cnt[idx] - 1)
            s = sa[idx] + (sb - sa)[idx] * u
            r_here = np.maximum(br.lerp(br.r0, s), 2.0 * mm)
            swing = amp1 * np.sin(2.0 * np.pi * s / lam1 + ph1)
            th = t0[idx] + (swing + wig[idx] * np.sin(2.0 * np.pi * s / lam2[idx] + ph2[idx])) / r_here + \
                lean[idx] * (u - 0.5)
            P, N, ok = seat(prog, br, s, th, maxd=3.5 * mm)
            # each line fades at its OWN height (its envelope read a little lower or higher: `reach`): one polish
            # line for all of them drew a comb's edge across the tine (build/look/h05_high_regions_d_grain.png)
            genv, penv = _grain_envelopes(br, np.clip(s / reach[idx], 0.0, L), sf['polish_from'],
                                          top_from if br.kind == 'beam' else None, mm)
            run = (sb - sa)[idx]
            e_in = np.clip(np.minimum(u, 1.0 - u) * run / (9.0 * mm), 0.0, 1.0)
            e_in = np.minimum(e_in, np.clip(_run_gap(ok, run / np.maximum(cnt[idx] - 1, 1)) / (10.0 * mm), 0.0, 1.0))
            # ... and pinches and swells along its run (a line of even depth is a rail)
            genv = genv * (0.62 + 0.38 * np.sin(2.0 * np.pi * s / lam3[idx] + ph3[idx]))
            # ONE tool radius per line (the round tool that cuts the line's full width at its full depth): where the
            # depth runs out the groove narrows to a point by itself. A width held while the depth fell gave shallow
            # dishes with round ends, a row of stitches up the tine (build/look/h05_high_regions_e_beans_notches.png)
            d_full = (gd0 + (gd1 - gd0) * strength)[idx]
            w_full = (gw0 + (gw1 - gw0) * strength)[idx]
            rho = (w_full * w_full / 4.0 + d_full * d_full) / (2.0 * d_full)
            depth = d_full * genv * e_in ** 0.8
            C = P + N * (rho - depth)[:, None]
            good = ok & (depth > 0.012 * mm)
            seg = good[:-1] & good[1:] & (idx[:-1] == idx[1:])
            nA.append(C[:-1][seg])
            nB.append(C[1:][seg])
            nRa.append(rho[:-1][seg])
            nRb.append(rho[1:][seg])
            sp, tp = np.concatenate(ps), np.concatenate(pth)
            _, pch = _grain_envelopes(br, sp, sf['polish_from'], top_from if br.kind == 'beam' else None, mm)
            keep = rng.uniform(0.0, 1.0, len(sp)) < pch
            sp, tp = sp[keep], tp[keep]
            if len(sp):
                tp = tp + amp1 * np.sin(2.0 * np.pi * sp / lam1 + ph1) / np.maximum(br.lerp(br.r0, sp), 2.0 * mm)
                near = np.clip(1.0 - (sp - s0) / (70.0 * mm), 0.0, 1.0) if br.kind == 'beam' else np.zeros(len(sp))
                _pearls(prog, br, rng, sf, mm, sp, tp, near, sf.get('ridge_pearl', 0.7), pA, pB, pRa, pRb,
                        round_frac=sf.get('round_pearls', 0.0))
    cat = lambda xs, w=3: np.concatenate(xs) if xs else np.zeros((0, w) if w > 1 else 0)     # noqa: E731
    out = dict(lines=lines)
    out['gutters'] = dict(kind=VX.STROKE_CONE, A=cat(gA), B=cat(gB), ra=cat(gRa, 1), rb=cat(gRb, 1), mode='carve',
                          k=0.8 * mm, mat=HORN_IDS['gutter'])
    out['grain'] = dict(kind=VX.STROKE_CONE, A=cat(nA), B=cat(nB), ra=cat(nRa, 1), rb=cat(nRb, 1), mode='carve',
                        k=0.45 * mm, mat=HORN_IDS['grain'])
    out['pearls'] = dict(kind=VX.STROKE_CONE, A=cat(pA), B=cat(pB), ra=cat(pRa, 1), rb=cat(pRb, 1), mode='add',
                         k=0.9 * mm, mat=HORN_IDS['pearl'])
    # THE BURR'S CRUST (11-12, check 2's failure 2; the preset's `burr` rows say what each number is). The living
    # stag's burr (refs c11 Rothirsch Geweihansatz 070816 1) is a LOW crust of fused nodules of many sizes on an
    # uneven rim, the beam's furrows running into it. The first two recipes drew one row of knobs, each taller than
    # wide, with a notch cut between every two: a row of molars at 0.5 m whatever their sizes (check 1's item 6,
    # check 2's failure 2). Here: rows of LUMPS that overlap and fuse (the batch's smooth union), none taller than
    # wide, bigger where the rim itself is thick; a furrow cut into the rim only where a channel of the beam
    # arrives (`burr_feet`), and a few more at random; small nodules over all of it
    rims = [b for b in skel.branches if b.kind == 'rim']
    bA, bB, bR = [], [], []
    kA, kB, kR = [], [], []
    if rims:
        rim = rims[0]
        bu = pr['burr']
        m = len(rim.P) - 1
        _, _, _, t_ax = beam.frame(rim.s_parent)
        ctr = beam.frame(rim.s_parent)[0]
        asp_r = float(rim.asp[0])
        thick = rim.r0[:-1] / float(np.mean(rim.r0[:-1]))            # the rim's own thickness round it, over its mean

        def at(q):
            i0 = int(np.floor(q)) % m
            f = q - np.floor(q)
            c = rim.P[i0] * (1 - f) + rim.P[i0 + 1] * f
            rr = float(rim.r0[i0] * (1 - f) + rim.r0[i0 + 1] * f)
            radial = c - ctr
            radial = _unit(radial - t_ax * float(radial @ t_ax))
            return c, rr, radial, np.cross(t_ax, radial)

        def on_rim(q, phi):
            """the rim's own surface at place q round it and angle phi across its section (0 straight out of the
            beam, + toward the beam's distal side): the point, its outward direction, the direction along the rim"""
            c, rr, radial, tang = at(q)
            d = _unit(radial * np.cos(phi) + t_ax * np.sin(phi))
            return c + radial * (rr * asp_r * np.cos(phi)) + t_ax * (rr * np.sin(phi)), d, tang, rr

        # every lump as a record first (place, angle, radius, how far it stands out, whether it grows lumps of its
        # own), so all their feet are seated on the block-out in ONE call (the rim meets the beam in a fillet: a
        # foot on the rim's bare section there would stand inside it)
        recs = []
        for (count, (r_lo, r_hi), (phi_c, phi_w), (o_lo, o_hi)) in bu.get('nodules', ()):
            # uneven on purpose: gaps from a wide spread, each row starting at its own place round the rim
            gaps = rng.uniform(0.45, 1.75, count)
            for q in (np.cumsum(gaps) / gaps.sum() + rng.uniform()) * m:
                q = float(q % m)
                tk = float(np.clip(thick[int(q) % m], 0.7, 1.45))
                r_b = (r_lo + (r_hi - r_lo) * rng.uniform() ** 1.9) * mm * tk ** 1.5
                recs.append((q, np.radians(phi_c + rng.uniform(-1.0, 1.0) * phi_w), r_b,
                             r_b * rng.uniform(o_lo, o_hi), True))
        for q in rng.uniform(0.0, m, int(bu.get('crust', 0))):
            r_c = (0.4 + 0.8 * rng.uniform() ** 1.7) * mm
            recs.append((float(q), np.radians(rng.uniform(-75.0, 95.0)), r_c, r_c * rng.uniform(0.25, 0.75), False))
        if recs:
            feet = [on_rim(q, phi) for (q, phi, _, _, _) in recs]
            P0 = np.array([f_[0] for f_ in feet])
            D = np.array([f_[1] for f_ in feet])
            TAN = np.array([f_[2] for f_ in feet])
            Ps, _ = prog.project(P0 - D * (1.5 * mm), D, maxd=5.0 * mm)
            seated = np.abs(prog.eval(Ps)) < 2.0e-6
            P = np.where(seated[:, None], Ps, P0)
            E1 = np.cross(D, TAN)
            for i, (q, phi, r_b, rise, lumps) in enumerate(recs):
                c2 = P[i] + D[i] * (rise - r_b)
                # a lump a little longer one way, ANY way along the rim's surface (never up the beam by rule)
                a = rng.uniform(0.0, np.pi)
                tilt = _unit(np.cos(a) * TAN[i] + np.sin(a) * E1[i] + D[i] * rng.uniform(-0.2, 0.2))
                ln = rng.uniform(0.0, 0.7 if lumps else 1.2) * r_b
                bA.append(c2 - tilt * ln)
                bB.append(c2 + tilt * ln)
                bR.append(r_b)
                if lumps:
                    # a knob is a lump of lumps: 0-2 smaller ones grown onto its side
                    for _ in range(int(rng.choice([0, 0, 1, 1, 2]))):
                        r_s = r_b * rng.uniform(0.40, 0.70)
                        ang = rng.uniform(0.0, 2.0 * np.pi)
                        c4 = c2 + (np.cos(ang) * TAN[i] + np.sin(ang) * E1[i]) * r_b * rng.uniform(0.6, 1.0) + \
                            D[i] * rng.uniform(-0.25, 0.10) * r_b
                        t4 = _unit(rng.normal(size=3))
                        l4 = rng.uniform(0.0, 0.6) * r_s
                        bA.append(c4 - t4 * l4)
                        bB.append(c4 + t4 * l4)
                        bR.append(r_s)
        # THE FURROWS IN THE CRUST: where a channel of the beam starts on the burr the rim's upper half is cut on
        # its line (the channel running in), and the rest of the preset's count at random places, shallower
        n_notch = int(bu.get('notches', 0))
        feet_q = [(t / (2.0 * np.pi) % 1.0) * m for t in burr_feet]
        rng.shuffle(feet_q)
        places = [(q, True) for q in feet_q[:n_notch]] + [(float(q), False)
                                                           for q in rng.uniform(0.0, m, max(n_notch - len(feet_q), 0))]
        for q, from_beam in places:
            r_n = rng.uniform(0.6, 1.2) * mm
            deep = rng.uniform(0.5, 1.0) * mm if from_beam else rng.uniform(0.25, 0.6) * mm
            pa, da, _, _ = on_rim(q, np.radians(rng.uniform(72.0, 88.0)))
            pb, db, _, _ = on_rim(q + rng.uniform(-1.5, 1.5), np.radians(rng.uniform(0.0, 30.0) if from_beam
                                                                        else rng.uniform(-40.0, 20.0)))
            kA.append(pa + da * (r_n - deep))
            kB.append(pb + db * (r_n - 0.45 * deep))
            kR.append(r_n)
    bA, bB, bR = np.array(bA).reshape(-1, 3), np.array(bB).reshape(-1, 3), np.array(bR)
    out['beads'] = dict(kind=VX.STROKE_CONE, A=bA, B=bB, ra=bR, rb=bR * rng.uniform(0.8, 1.0, len(bR)), mode='add',
                        k=0.9 * mm, mat=HORN_IDS['bead'])
    kA, kB, kR = np.array(kA).reshape(-1, 3), np.array(kB).reshape(-1, 3), np.array(kR)
    out['notches'] = dict(kind=VX.STROKE_CONE, A=kA, B=kB, ra=kR, rb=kR * rng.uniform(0.7, 1.0, len(kR)),
                          mode='carve', k=0.7 * mm, mat=HORN_IDS['gutter'])
    out['extra'] = (0.5 * (bA + bB), bR + np.linalg.norm(bB - bA, axis=1) * 0.5) if len(bR) else None
    out['counts'] = dict(gutter_strokes=len(out['gutters']['A']), gutter_lines=sum(len(v) for v in lines.values()),
                         grain_strokes=len(out['grain']['A']), pearls=len(out['pearls']['A']) // 2, beads=len(bR))
    log(f'[horn_surface] plan: {out["counts"]["gutter_strokes"]} gutter strokes on '
        f'{out["counts"]["gutter_lines"]} lines, {out["counts"]["grain_strokes"]} grain strokes, '
        f'{out["counts"]["pearls"]} pearls, {len(bR)} burr beads')
    return out


def apply(G, pl, near=None):
    """the plan's strokes onto a voxel grid, in BATCHES' order. near = (centre, radius): only the strokes that
    start within the radius (a region's grid: h05's looks, h08's bake pieces)"""
    for name in BATCHES:
        b = pl[name]
        if not len(b['A']):
            continue
        m = np.ones(len(b['A']), bool) if near is None else \
            (np.linalg.norm(b['A'] - np.asarray(near[0]), axis=1) < float(near[1]))
        if m.any():
            G.strokes(b['kind'], b['A'][m], b['B'][m], b['ra'][m], b['rb'][m], mode=b['mode'], k=b['k'],
                      mat=b['mat'])
    return G


def build(skel, prog, pl, voxel=0.0003, band=None, log=print, relevel=True, smooth=1):
    """the high: a SparseSDF of the block-out, the gutters carved, the pearls and beads added (each batch exact
    among its own strokes, filleted to the form), one light smoothing pass over the strokes' voxel steps, then the
    relevel (|grad| = 1 in the band: the bake's cavity and curvature read true)"""
    lo, hi = skel.bounds(pad=0.006)
    band = float(band) if band is not None else max(8.0 * voxel, 0.0024 * skel.scale)
    G = VX.SparseSDF(prog, lo, hi, voxel=voxel, band=band, log=log, extra=pl.get('extra'))
    apply(G, pl)
    if smooth:
        G.smooth(iters=int(smooth), strength=0.35)
    if relevel:
        G.redistance()
    return G
