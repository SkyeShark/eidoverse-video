"""Package 9 (first half): each analytic shape against its reference's profile, measured the same way on both.

    python blender/tests/terrain_new/volcanoes_craters/test_references.py [fuji,meteor,lake,sp]

The analytic shape is evaluated on its reference's own tile (same extent; at twice the pixel, box-averaged to it, as
the judge compares) with the preset measured from that reference (volcanic.FUJI, CRATER_LAKE, SP_CRATER;
impact.METEOR_CRATER), on a placeholder base of low world noise. Every number is measured by one procedure on both
fields; craters find their centre from the data. Each row prints the generated value, the reference's, the allowed
difference and PASS / FAIL; INFO rows are the gaps the second half closes (gullies, cliffs, talus), printed with the
reason. Exit status 0 when every checked row passes.
"""
import math
import sys
import time

import numpy as np

import _common as C

ROWS = []


def row(group, name, gen, ref, tol, unit='', info=None):
    """Record one comparison: |gen - ref| <= tol passes; tol None makes an INFO row (not checked)."""
    if tol is None:
        status = 'INFO'
    elif callable(tol):
        status = 'PASS' if tol(gen, ref) else 'FAIL'
    else:
        status = 'PASS' if abs(gen - ref) <= tol else 'FAIL'
    tol_s = '' if tol is None else ('rule' if callable(tol) else f'+-{tol:g}')
    ROWS.append((group, name, gen, ref, tol_s, unit, status, info or ''))


# ---------------------------------------------------------------- Mount Fuji
def fuji_measures(h, X, Y, p, centre):
    out = {}
    radii = np.arange(500.0, 13001.0, 250.0)
    out['profile'] = C.ring_median(h, X, Y, centre, radii, 125.0)
    rs = C.radial_slope_deg(h, p, X, Y, centre)
    for km in (1, 3, 5, 7, 10, 13):
        out[f'slope_{km}km'] = float(C.ring_median(rs, X, Y, centre, [km * 1000.0], 250.0)[0])
    rr = np.arange(100.0, 1001.0, 20.0)
    ring = C.ring_median(h, X, Y, centre, rr, 20.0)
    r = np.hypot(X - centre[0], Y - centre[1])
    out['crater_rim_m'] = float(rr[np.argmax(ring)])
    out['crater_depth_m'] = float(ring.max() - h[r < 150.0].min())
    s = [C.sector_median(h, X, Y, centre, 6000.0, 300.0, a) for a in (315.0, 135.0, 45.0, 225.0)]
    out['rift_minus_cross_6km'] = 0.5 * (s[0] + s[1]) - 0.5 * (s[2] + s[3])
    bins = np.linspace(1000.0, 15000.0, 11)
    mids = 0.5 * (bins[1:] + bins[:-1])
    sl = [float(np.median(rs[(r >= a) & (r < b)])) for a, b in zip(bins[:-1], bins[1:])]
    out['spearman_slope_vs_r'] = C.spearman(np.array(sl), mids)
    gy, gx = np.gradient(h, p)
    down = np.arctan2(-gx, -gy)                          # downslope azimuth (compass radians)
    radial = np.arctan2(X - centre[0], Y - centre[1])
    off = np.abs((np.degrees(down - radial) + 180.0) % 360.0 - 180.0)
    flank = (np.degrees(np.arctan(np.hypot(gx, gy))) > 5.0) & (r > 1000.0) & (r < 12000.0)
    out['aspect_radial_frac'] = float(np.mean(off[flank] < 30.0))
    return out


def check_fuji():
    V, _ = C.import_solvers()
    href, meta, X, Y = C.load_reference('mount_fuji')
    p = meta['pixel_size_m']
    g = C.generated('mount_fuji')
    centre = V.FUJI['centre']
    a, b = fuji_measures(g['h'], X, Y, p, centre), fuji_measures(href, X, Y, p, centre)
    rms = float(np.sqrt(np.mean((a['profile'] - b['profile']) ** 2)))
    row('fuji', 'median radial profile 0.5-13 km, rms difference', rms, 0.0, 35.0, 'm')
    for km in (1, 3, 5, 7, 10):
        row('fuji', f'radial slope median at {km} km', a[f'slope_{km}km'], b[f'slope_{km}km'], 2.5, 'deg')
    row('fuji', 'radial slope median at 13 km', a['slope_13km'], b['slope_13km'], None, 'deg',
        'the real foot meets the Misaka / Tanzawa mountains and the lake plain; the placeholder base is flat')
    row('fuji', 'summit crater rim radius', a['crater_rim_m'], b['crater_rim_m'], 100.0, 'm')
    row('fuji', 'summit crater depth (rim ring to floor, 40 m pixels)', a['crater_depth_m'], b['crater_depth_m'], 60.0,
        'm')
    row('fuji', 'rift sectors (NW, SE) above cross sectors (NE, SW) at 6 km', a['rift_minus_cross_6km'],
        b['rift_minus_cross_6km'], lambda gv, rv: gv > 50.0, 'm',
        'same sense required; the real figure also carries the base tilt (north 1000 m, south-west 300 m)')
    row('fuji', 'family: Spearman rho, radial slope vs distance (10 bins)', a['spearman_slope_vs_r'],
        b['spearman_slope_vs_r'], lambda gv, rv: gv <= -0.9 and rv <= -0.9, '')
    row('fuji', 'family: flank aspects within 30 deg of radial', a['aspect_radial_frac'], b['aspect_radial_frac'],
        lambda gv, rv: gv >= 0.7, '', 'design 10: >= 70 %')


# ---------------------------------------------------------------- Meteor Crater
def crater_centre(h, X, Y, start, r_min, r_max, iters=3):
    """The rim crest's centroid, refined from a starting guess."""
    c = start
    for _ in range(iters):
        azs, rr, _zz = C.rim_crests(h, X, Y, c, r_min, r_max, 5.0)
        th = np.radians(azs)
        c = (c[0] + float(np.mean(rr * np.sin(th))), c[1] + float(np.mean(rr * np.cos(th))))
    return c


def meteor_measures(h, X, Y, p, start):
    c = crater_centre(h, X, Y, start, 350.0, 800.0)
    azs, rr, zz = C.rim_crests(h, X, Y, c, 350.0, 800.0, 5.0)
    r = np.hypot(X - c[0], Y - c[1])
    az = C.compass_deg(X, Y, c)
    plain = float(np.median(h[(r > 1350.0) & (r < 1480.0)]))
    floor = float(np.median(h[r < 0.15 * rr.mean()]))
    D = 2.0 * float(rr.mean())
    out = dict(centre=c, D=D, rim_above_plain=float(zz.mean() - plain), rim_to_floor=float(zz.mean() - floor))
    out['d_over_D'] = out['rim_to_floor'] / D
    out['h_over_D'] = out['rim_above_plain'] / D
    rho = r / np.interp(az, azs, rr, period=360.0)
    qs = np.arange(0.0, 2.41, 0.05)
    out['rho'] = qs
    out['profile'] = np.array([np.median(h[np.abs(rho - q) < 0.025]) - plain for q in qs])
    beyond = np.where((qs > 1.0) & (out['profile'] < 1.0))[0]
    out['reach'] = float(qs[beyond[0]]) if beyond.size else float(qs[-1])
    H = C.harmonics(rr, azs, 6)
    out['h4'], out['h4_phase'] = H[4]
    out['corner_az'] = (-out['h4_phase'] / 4.0) % 90.0
    s = C.slope_deg(h, p)
    out['wall_p99'] = float(np.percentile(s[rho < 0.97], 99))
    out['wall_p90'] = float(np.percentile(s[rho < 0.97], 90))
    out['ejecta_p90'] = float(np.percentile(s[(rho > 1.1) & (rho < 2.0)], 90))
    return out


def check_meteor():
    _, I = C.import_solvers()
    href, meta, X, Y = C.load_reference('meteor_crater')
    p = meta['pixel_size_m']
    g = C.generated('meteor_crater')
    a, b = meteor_measures(g['h'], X, Y, p, I.METEOR_CRATER['centre']), meteor_measures(href, X, Y, p, (17.0, 26.0))
    row('meteor', 'diameter D (rim crest mean x 2)', a['D'], b['D'], 0.03 * b['D'], 'm')
    row('meteor', 'rim to floor / D (Pike 0.2 fresh; infilled here)', a['d_over_D'], b['d_over_D'], 0.01, '')
    row('meteor', 'rim above the plain / D (Pike 0.036 fresh)', a['h_over_D'], b['h_over_D'], 0.006, '')
    rms = float(np.sqrt(np.mean((a['profile'] - b['profile']) ** 2)))
    row('meteor', 'median profile along rho = r / rim radius, 0-2.4, rms', rms, 0.0, 8.0, 'm')
    row('meteor', 'ejecta reach (profile under 1 m), in rim radii', a['reach'], b['reach'], 0.3, 'R')
    row('meteor', 'outline 4-fold harmonic (squareness)', a['h4'], b['h4'], 0.02, 'of R')
    row('meteor', 'outline corners, compass (mod 90)', a['corner_az'], b['corner_az'],
        lambda gv, rv: abs((gv - rv + 45.0) % 90.0 - 45.0) <= 15.0, 'deg')
    row('meteor', 'ejecta slope p90, 1.1-2 R', a['ejecta_p90'], b['ejecta_p90'], 3.0, 'deg')
    row('meteor', 'wall slope p90 inside the rim', a['wall_p90'], b['wall_p90'], None, 'deg',
        'the real upper walls are Kaibab / Coconino cliffs with talus: strata + threshold (second half)')
    row('meteor', 'family: wall slope p99 inside the rim', a['wall_p99'], b['wall_p99'], None, 'deg',
        'same: a parabolic bowl peaks at 39 degrees; the cliffs come from the strata column and the talus pass')
    return a, b


# ---------------------------------------------------------------- Crater Lake
def lake_measures(h, water, X, Y, p, centre, lake_level):
    lake = water == 128
    r = np.hypot(X - centre[0], Y - centre[1])
    az = C.compass_deg(X, Y, centre)
    azs = np.arange(0.0, 360.0, 5.0)
    shore, rim_r, rim_z = [], [], []
    for a in azs:
        sec = np.abs(((az - a + 180.0) % 360.0) - 180.0) < 2.5
        rs = float(r[sec & lake].max())
        band = sec & (r > rs) & (r < rs + 2000.0)
        k = np.argmax(np.where(band, h, -1e30))
        shore.append(rs)
        rim_r.append(r.ravel()[k])
        rim_z.append(h.ravel()[k])
    shore, rim_r, rim_z = map(np.array, (shore, rim_r, rim_z))
    out = dict(shore=shore, rim_r=rim_r, rim_z=rim_z, azs=azs)
    out['shore_mean'] = float(shore.mean())
    Hs = C.harmonics(shore, azs, 4)
    out['shore_h2'] = Hs[2][0]
    out['long_axis'] = (-Hs[2][1] / 2.0) % 180.0
    out['rim_above_lake'] = float(rim_z.mean() - lake_level)
    out['rim_above_lake_min'] = float(rim_z.min() - lake_level)
    out['rim_above_lake_max'] = float(rim_z.max() - lake_level)
    out['rim_r_mean'] = float(rim_r.mean())
    Hr = C.harmonics(rim_r, azs, 12)
    out['rim_scallop_band'] = max(Hr[k][0] for k in range(6, 13))
    Hs16 = C.harmonics(shore, azs, 16)
    out['shore_scallop_rms'] = math.sqrt(sum(Hs16[k][0] ** 2 for k in range(6, 17)) / 2.0)
    s = C.slope_deg(h, p)
    shore_i = np.interp(az, azs, shore, period=360.0)
    rim_i = np.interp(az, azs, rim_r, period=360.0)
    wall = (r > shore_i + p) & (r < rim_i - p) & ~lake
    out['wall_p50'], out['wall_p90'] = (float(v) for v in np.percentile(s[wall], [50, 90]))
    outer = (r > rim_i + 300.0) & (r < rim_i + 2500.0)
    out['outer_p50'] = float(np.percentile(s[outer], 50))
    from_lake = _island(lake, h)
    out['island_km2'] = float(from_lake.sum() * p * p / 1e6)
    out['island_top'] = float(h[from_lake].max() - lake_level) if from_lake.any() else 0.0
    return out


def _island(lake, h):
    """The largest land region wholly enclosed by the lake (flood fill from the tile border marks the rest)."""
    land = ~lake
    seen = np.zeros_like(land)
    n0, n1 = land.shape
    stack = [(i, j) for i in range(n0) for j in (0, n1 - 1) if land[i, j]]
    stack += [(i, j) for j in range(n1) for i in (0, n0 - 1) if land[i, j]]
    for i, j in stack:
        seen[i, j] = True
    while stack:                                         # 4-connected flood fill of the land touching the border
        i, j = stack.pop()
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < n0 and 0 <= b < n1 and land[a, b] and not seen[a, b]:
                seen[a, b] = True
                stack.append((a, b))
    return land & ~seen


def check_lake():
    V, _ = C.import_solvers()
    href, meta, X, Y = C.load_reference('crater_lake')
    p = meta['pixel_size_m']
    water_ref = C.load_reference_water('crater_lake')
    lake_level = water_ref[1][0]['level_m']
    g = C.generated('crater_lake')
    centre = V.CRATER_LAKE['centre']
    a = lake_measures(C.with_lake_surface(g['h'], g['water']), g['water'][0], X, Y, p, centre, lake_level)
    b = lake_measures(href, water_ref[0], X, Y, p, centre, lake_level)
    row('lake', 'shore radius, mean', a['shore_mean'], b['shore_mean'], 250.0, 'm')
    row('lake', 'shore outline 2-fold harmonic (8 x 10 km)', a['shore_h2'], b['shore_h2'], 0.03, 'of R')
    row('lake', 'shore long axis, compass (mod 180)', a['long_axis'], b['long_axis'],
        lambda gv, rv: abs((gv - rv + 90.0) % 180.0 - 90.0) <= 20.0, 'deg')
    row('lake', 'rim crest radius, mean', a['rim_r_mean'], b['rim_r_mean'], 300.0, 'm')
    row('lake', 'rim crest above the lake, mean', a['rim_above_lake'], b['rim_above_lake'], 60.0, 'm')
    row('lake', 'rim crest above the lake, lowest', a['rim_above_lake_min'], b['rim_above_lake_min'], 100.0, 'm')
    row('lake', 'rim crest above the lake, highest', a['rim_above_lake_max'], b['rim_above_lake_max'], 120.0, 'm')
    row('lake', 'wall slope p50 above the water', a['wall_p50'], b['wall_p50'], 5.0, 'deg')
    row('lake', 'wall slope p90 above the water', a['wall_p90'], b['wall_p90'], None, 'deg',
        'the real walls carry cliff bands and chutes (rock breakup, threshold + talus: second half)')
    row('lake', 'outer flank slope p50 (rim + 0.3-2.5 km)', a['outer_p50'], b['outer_p50'], 3.0, 'deg')
    row('lake', 'shore outline scallops: RMS of harmonics 6-16', a['shore_scallop_rms'], b['shore_scallop_rms'],
        0.4 * b['shore_scallop_rms'], 'of R', 'design: a scalloped ring (the real shore: embayments at 7-10 a turn)')
    row('lake', 'rim outline scallop band (largest harmonic 6-12)', a['rim_scallop_band'], b['rim_scallop_band'], None,
        'of R', 'the real figure is inflated by the crest search jumping between the rim and peaks behind it')
    row('lake', 'Wizard Island area at the waterline', a['island_km2'], b['island_km2'], 0.4 * b['island_km2'], 'km2')
    row('lake', 'Wizard Island summit above the lake', a['island_top'], b['island_top'], 30.0, 'm')
    return a, b


# ---------------------------------------------------------------- SP Crater
def sp_measures(h, X, Y, p, guess):
    r0 = np.hypot(X - guess[0], Y - guess[1])
    k = np.argmin(np.where(r0 < 200.0, h, 1e30))
    c = (float(X.ravel()[k]), float(Y.ravel()[k]))
    floor = float(h.ravel()[k])
    azs, rr, zz = C.rim_crests(h, X, Y, c, 0.0, 400.0, 10.0)
    r = np.hypot(X - c[0], Y - c[1])
    base = float(np.median(h[(r > 800.0) & (r < 1000.0)]))
    radii = np.arange(rr.mean() + 50.0, 1100.0, 25.0)
    sl = C.ring_median(C.slope_deg(h, p), X, Y, c, radii, p)
    below = np.where(sl < 12.0)[0]
    rb = float(radii[below[0]]) if below.size else float(radii[-1])
    s = C.slope_deg(h, p)
    flank = (r > rr.mean() + 60.0) & (r < 0.8 * rb)
    out = dict(H=float(zz.mean() - base), W=2.0 * rb, crater_r=float(rr.mean()), depth=float(zz.mean() - floor))
    out['hw'] = out['H'] / out['W']
    out['crater_ratio'] = 2.0 * out['crater_r'] / out['W']
    out['flank_p50'], out['flank_p90'] = (float(v) for v in np.percentile(s[flank], [50, 90]))
    return out


def check_sp():
    V, _ = C.import_solvers()
    href, p, X, Y = C.load_sp_crater()
    g = C.generated('sp_crater')
    a, b = sp_measures(g['h'], X, Y, p, V.SP_CRATER['at']), sp_measures(href, X, Y, p, (20.0, -20.0))
    row('sp', 'cone height above its base', a['H'], b['H'], 25.0, 'm')
    row('sp', 'basal width (flank slope under 12 deg)', a['W'], b['W'], 0.1 * b['W'], 'm')
    row('sp', 'family: H / W (Wood 0.18)', a['hw'], b['hw'], 0.02, '')
    row('sp', 'crater rim width / W (Wood 0.40; SP 0.28)', a['crater_ratio'], b['crater_ratio'], 0.06, '')
    row('sp', 'crater depth below the rim', a['depth'], b['depth'], 25.0, 'm')
    row('sp', 'flank slope p50', a['flank_p50'], b['flank_p50'], 3.0, 'deg')
    row('sp', 'family: flank slope p90 (design 28-33)', a['flank_p90'], b['flank_p90'],
        lambda gv, rv: 28.0 <= gv <= 34.0, 'deg', 'the real p90 at 7.8 m over 10 m source data')
    return a, b


CHECKS = dict(fuji=check_fuji, meteor=check_meteor, lake=check_lake, sp=check_sp)


def main(argv):
    names = argv[0].split(',') if argv else list(CHECKS)
    t0 = time.time()
    for n in names:
        CHECKS[n]()
    w = max(len(r[1]) for r in ROWS)
    print(f'{"":7s} {"check":{w}s} {"generated":>10s} {"reference":>10s} {"allowed":>8s}')
    for group, name, gen, ref, tol, unit, status, info in ROWS:
        print(f'{status:5s} {group:7s} {name:{w}s} {gen:10.3f} {ref:10.3f} {tol:>8s} {unit}'
              + (f'   ({info})' if info else ''))
    failed = [r for r in ROWS if r[6] == 'FAIL']
    print(f'{len(ROWS) - len(failed)} of {len(ROWS)} rows pass or inform; {len(failed)} fail; {time.time() - t0:.1f} s')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
