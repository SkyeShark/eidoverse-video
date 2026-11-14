"""W2d / W2e: the STROKES on the wolf's body (species/wolf_body.py, families/limbed.build_volume_sdf): ONLY what reads
through the skin on the wet and mange canids (the lead's call 1: "the scapular spine, the olecranon, the accessory carpal
pad, the tuber coxae, the stifle, the calcaneus with its tendon, each measured there").

W2e (the lead's call 6: "evaluate the strokes ANALYTICALLY over the GRID members instead of baking them into the grid
(or another construction that cannot terrace)"): W2d baked them into the grid volumes, and the scapular spine's oblique
ridge printed a ladder of dashes on the 2 mm trunk grid, in the FIELD (the W2d checker: the same on a 0.5 mm mesh).
Each stroke is now a STROKE member of the program (the staged GRID patch's kind 10, op DISPLACE: work/bestiary/patches/
sdf_grid.md), evaluated analytically where the program is evaluated, after the body's GRID members in their group: a
Gaussian bump across its outward direction (constant along it within its band), and a RIDGE a row of such bumps spaced
0.8 sigma along its smooth curve, each of weight height x spacing / (sqrt(2 pi) sigma), whose sum is a Gaussian ridge of
that height with no seam along it (the row's ripple at 0.8 sigma is ~1e-24 of the height). Both sides: each stroke and
its mirror image.

Each stroke is anchored on the skeleton (a chain point plus an offset in mm) and PROJECTED onto the composed body's
skin along a measured outward direction, so it sits on the surface it lifts. Heights and widths are measured on the
references in their own units and carried to the wolf by a length both share (the chest depth for the coyotes r05 and
r06: r05 591 px -> the clay's 288 mm, 0.487 mm per px; r06 ~610 px, 0.47 mm per px):
  olecranon       r05 the planted foreleg: the elbow's point stands ~10 px (5 mm) proud of the line from the triceps
                  down the forearm's caudal edge; r06 likewise; a bump at the elbow's point (0.512 WH, WOLF_BODY_PHOTOS
                  §3.1). W2e: 24 mm behind the elbow joint (was 30): the olecranon's skin point ~39 mm behind the joint
                  (a large dog's tuber 30-35 mm caudal of the condyles plus the skin). W2e check: the 5 mm is the TOTAL
                  relief, and the composed body's bony olecranon already stands ~3 mm proud: with a 4 mm bump the clay's
                  point stood 6.4 mm proud of that line (check_w2e/elbow_relief.py on the 0.5 mm forelimb mesh: the
                  forearm's caudal edge and the triceps both at z ~492 mm, the point at 485.7), a marble from the side
                  and the three-quarter back; the bump 2.5 mm (it lifts the side outline ~0.96 of its height) brings the
                  point to ~5 mm, r05's
  accessory carpal pad  r05: the caudal outline bulges ~10 px (5 mm) at the carpus (y 1780-1800 px), r06 ~12 px (5.6
                  mm) at the carpus's back: W2e 4.0 mm, sigma 5.5 mm (W2d 4.5 / 4.5: its slope across, 0.61 h / sigma,
                  0.61, past what the body's divisor leaves for a distance bound, 0.47), 18 mm under the carpal joint
  calcaneus       the composed program builds the point (the tuber and the two lines; wolf_body.BONES holds it): no
                  stroke (W2d check: a 'sharpening bump' printed a bead)
  tendon          r06: the caudal outline straight for ~200 px (94 mm) above the tuber: the common calcanean tendon as a
                  cord up 90 mm from the tuber, with the hollows either side of it. W2e (the lead: "the calcanean
                  tendon's hollows shallower (no slit from behind)"): the cord 2.6 mm (W2d 3.0), sigma 4; the hollows
                  1.0 mm (W2d 2.0), sigma 6 (W2d 5), 11 mm cranial of the cord, medial and lateral
  stifle          r05, r06: the patella and the tibial crest a soft rise on the hind leg's cranial outline at the stifle:
                  3 mm, sigma 10 mm
  tuber coxae     r05 (the mange coyote's croup), r08: a bump at the croup's front corner either side, the iliac crest's
                  lateral point ~40 mm ahead of the hip joint, 70 mm up, 50 mm off the midline [E]. W2e (the lead:
                  "blend away the croup's horseshoe rim (... tuber coxae)"): 2.0 mm, sigma 14 (W2d 4.0 / 12, the
                  mange coyote's: lumps at the croup's corners on a hairless WOLF, whose gluteal fascia covers them)
  scapular spine  r05: a faint ridge on the shoulder from near the point of the shoulder up the blade, ~2 mm: 2.5 mm high,
                  sigma 5 mm (W2e: the measured sigma back; W2d had widened it to 6.5 hunting the ladder, which was the
                  bake), from 30 % to 85 % of the way from the shoulder joint to the scapula's dorsal border
"""
import numpy as np

# the stroke's window along its outward direction (mm): (band inside, taper inside, band outside, taper outside), past
# w02's gradient gate's 5 mm sampling band either side
BAND = (6.0, 24.0, 8.0, 40.0)
RIDGE_STEP = 0.8               # the ridges' bumps this many sigma apart along the curve
# (name, the anchor chain point, b, t, offset mm (lateral, up, forward), outward direction (lateral, up, forward),
#  kind, parameters)
STROKES = (
    # W2l (the lead's "the elbow's knob"; the W2i checker's carpal knob): the olecranon's bump 0.8 mm over sigma 8 (was 2.5
    # / 6) on the ulnar flexor's broad top (SPEC skin.fore.tendons), the accessory carpal pad's 2.5 over sigma 7.5 (was
    # 4.0 / 5.5): with wolf_body.BONES' smaller balls the elbow is one rounded corner and the carpus a 3-5 mm swelling
    # (r05's ~5 mm), not knobs with notches above and below (work/bestiary/wolf/scratch_w2lb, runs base2 -> v6)
    ('olecranon', 'elbow', None, 0.0, (4.0, -8.0, -24.0), (0.15, -0.25, -1.0), 'bump', dict(h=0.8, s=8.0)),
    ('acc_carpal_pad', 'carpus', None, 0.0, (0.0, -18.0, -6.0), (0.0, -0.2, -1.0), 'bump', dict(h=2.5, s=7.5)),
    ('stifle', 'stifle', None, 0.0, (2.0, -12.0, 10.0), (0.2, 0.0, 1.0), 'bump', dict(h=3.0, s=10.0)),
    ('tuber_coxae', 'hip', None, 0.0, (-10.0, 70.0, 40.0), (0.7, 0.7, 0.0), 'bump', dict(h=2.0, s=14.0)),
)
# ridges: (name, anchor a, b, t0, t1, offset, outward, height, sigma, hollow (depth, sigma, cranial offset) or None)
# W2f (the lead's call 6: "the knife-cut diagonal crease at the neck-shoulder junction traced to its construction seam
# ... and removed"): the SCAPULAR SPINE ridge is gone. The crease is its line: on the W2e check's bind mesh the sharpest
# run in the neck-shoulder box (211 edges, 6-13 deg, centred at x 98, y 575, z 585 mm, 52 mm by 42 along the blade's
# slope, scratch_w2f/crease_probe.py) lies on the ridge's path from 30 % to 85 % of the way from the shoulder joint to
# the scapula's dorsal border; 2.5 mm high at sigma 5 it read as a cut, not a spine (a hairless wolf's spine lies under
# the deltoid and the trapezius; r05's ~2 mm is a mange coyote's)
RIDGES = (
    ('calcanean_tendon', 'hock', 'stifle', 0.12, 0.52, (0.0, 0.0, -18.0), (0.0, 0.0, -1.0), 2.6, 4.0,
     (1.0, 6.0, 11.0)),
)


def _pt(chain, a, b, t, off):
    P = chain['pos']
    pa = np.asarray(P[f'{a}_L'], float) * 1000.0
    p = pa if b is None else pa + t * (np.asarray(P[f'{b}_L'], float) * 1000.0 - pa)
    return p + np.asarray(off, float)


def _skin(prog, p, d, reach=60.0):
    """the skin along the outward direction d from p (mm): marched from 30 mm inside to `reach` outside"""
    d = np.asarray(d, float) / np.linalg.norm(d)
    t = np.arange(-30.0, reach, 0.25)
    f = prog.eval((p[None] + t[:, None] * d[None]) * 1.0e-3) * 1000.0
    inside = np.nonzero(f < 0)[0]
    if not len(inside):
        return p, False
    j = inside[-1]
    if j + 1 >= len(t):
        return p, False
    return p + d * (t[j] + 0.25 * f[j] / (f[j] - f[j + 1])), True


def _row(C, s):
    """a smooth curve through the points C (a cubic spline on their chord length) sampled every RIDGE_STEP sigma:
    the bumps' centres and their fractions u of the curve's length"""
    from scipy.interpolate import CubicSpline
    sk = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    cs = CubicSpline(sk, C, axis=0)
    L = float(sk[-1])
    n = max(int(np.ceil(L / (RIDGE_STEP * s))), 2)
    sd = np.linspace(0.0, L, n + 1)
    return cs(sd), sd / L, L / n


def stroke_value(P, c, n, s, w, band=BAND):
    """one stroke's displacement at points P (mm), as the kernel's sd_stroke evaluates it"""
    b_in, t_in, b_out, t_out = band
    q = np.asarray(P, float) - c
    t = q @ n
    r2 = np.maximum(np.sum(q * q, 1) - t * t, 0.0)
    g = np.exp(-r2 / (2.0 * s * s))
    u = np.clip((np.sqrt(r2) - 3.5 * s) / s, 0.0, 1.0)
    g *= 1.0 - u * u * (3.0 - 2.0 * u)
    uo = np.clip((t - b_out) / t_out, 0.0, 1.0)
    ui = np.clip((-t - b_in) / t_in, 0.0, 1.0)
    return w * g * (1.0 - uo * uo * (3.0 - 2.0 * uo)) * (1.0 - ui * ui * (3.0 - 2.0 * ui))


def strokes(spec, chain, prog=None):
    """the strokes as STROKE members: dict(members=[(name, centre mm, unit outward direction, sigma mm, weight mm)]
    for both sides, effective=[(name, height mm, sigma mm)] (a bump's, a ridge's: for the slope bound), rows to report,
    key (their numbers), field (P mm -> the summed displacement mm, as the program evaluates it))"""
    members, rows, key, eff = [], [], [], []

    def add(nm, c, n, s, w):
        n = np.asarray(n, float) / np.linalg.norm(n)
        for side, sfx in ((1.0, '_L'), (-1.0, '_R')):
            m = np.array([side, 1.0, 1.0])
            members.append((f'{nm}{sfx}', c * m, n * m, float(s), float(w)))

    for nm, a, b, t, off, out, kind, par in STROKES:
        p = _pt(chain, a, b, t, off)
        ok = True
        if prog is not None:
            p, ok = _skin(prog, p, np.asarray(out, float))
        add(nm, p, out, par['s'], par['h'])
        eff.append((nm, par['h'], par['s']))
        rows.append(f'{nm}: bump {par["h"]:.1f} mm, sigma {par["s"]:.1f} at ({p[0]:.0f}, {p[1]:.0f}, {p[2]:.0f}) mm'
                    + ('' if ok else ' (NOT on the skin)'))
        key.append((nm, np.round(p, 3).tolist(), par['h'], par['s']))
    for nm, a, b, t0, t1, off, out, h, s, hollow in RIDGES:
        ts = np.linspace(t0, t1, 12)
        C = np.array([_pt(chain, a, b, t, off) for t in ts])
        if prog is not None:
            C = np.array([_skin(prog, c, np.asarray(out, float))[0] for c in C])
        L = float(np.sum(np.linalg.norm(np.diff(C, axis=0), axis=1)))
        Cs, u, step = _row(C, s)
        end = np.clip(np.minimum(u, 1.0 - u) * 5.0, 0.0, 1.0)          # eased over the end fifths (W2d's)
        end = end * end * (3.0 - 2.0 * end)
        wk = h * step / (np.sqrt(2.0 * np.pi) * s)
        for i, (c, e) in enumerate(zip(Cs, end)):
            if e > 0.0:
                add(f'{nm}{i:02d}', c, out, s, wk * e)
        eff.append((nm, h, s))
        if hollow is not None:
            dep, sh, cr = hollow
            for lat, lab in ((1.0, 'lat'), (-1.0, 'med')):
                Ch, uh, steph = _row(C + np.array([lat * 0.7 * cr, 0.0, 0.7 * cr]), sh)
                eh = np.clip(np.minimum(uh, 1.0 - uh) * 5.0, 0.0, 1.0)
                eh = eh * eh * (3.0 - 2.0 * eh)
                wh = -dep * steph / (np.sqrt(2.0 * np.pi) * sh)
                for i, (c, e) in enumerate(zip(Ch, eh)):
                    if e > 0.0:
                        add(f'{nm}_hollow_{lab}{i:02d}', c, out, sh, wh * e)
            eff.append((f'{nm} hollows', dep, sh))
        rows.append(f'{nm}: ridge {h:.1f} mm, sigma {s:.1f}, {L:.0f} mm long from ({C[0][0]:.0f}, {C[0][1]:.0f}, '
                    f'{C[0][2]:.0f}) to ({C[-1][0]:.0f}, {C[-1][1]:.0f}, {C[-1][2]:.0f}) mm, {len(Cs)} bumps '
                    f'{step:.1f} mm apart' + (f'; hollows {hollow[0]:.1f} mm (sigma {hollow[1]:.0f}) either side'
                                               if hollow else ''))
        key.append((nm, np.round(C, 3).tolist(), h, s, hollow))

    def field(P):
        P = np.asarray(P, float)
        out_ = np.zeros(len(P))
        for _, c, n, s, w in members:
            out_ += stroke_value(P, c, n, s, w)
        return out_
    return dict(members=members, effective=eff, rows=rows, key=key, field=field)
