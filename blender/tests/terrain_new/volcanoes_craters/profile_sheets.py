"""Package 9's profile sheets: each analytic shape beside its reference, as profiles and hillshades, with the
reference test's numbers printed on the sheet.

    python blender/tests/terrain_new/volcanoes_craters/profile_sheets.py

Writes out/volcanoes_craters/<name>_profile_sheet.png for mount_fuji, crater_lake, meteor_crater and sp_crater:
the real DEM's hillshade and the analytic surface's (same tile, same pixel, north up, light from the north-west),
the profiles the test measures (real: blue; analytic: orange; the formula alone: aqua dashed), and the PASS / FAIL /
INFO rows of test_references.py for that landform. Plain Python (numpy, matplotlib).
"""
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import _common as C  # noqa: E402
import test_references as T  # noqa: E402

REAL, GEN, FORMULA = '#2a78d6', '#eb6834', '#1baf7a'          # the dataviz reference palette's slots 1-3
INK, INK2, SURFACE, GRID = '#0b0b0b', '#52514e', '#fcfcfb', '#e4e3df'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2,
                     'ytick.color': INK2, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
                     'axes.facecolor': SURFACE, 'figure.facecolor': SURFACE, 'lines.linewidth': 2.0,
                     'legend.frameon': False, 'axes.titlesize': 10, 'axes.titleweight': 'bold'})
V, I = C.import_solvers()
R = C.refs()


def hillshade_panel(ax, h, p, title, water=None):
    hs = R.hillshade(C.with_lake_surface(h, water)[::-1], p)
    half = 0.5 * h.shape[0] * p / 1000.0
    ax.imshow(hs, cmap='gray', vmin=0, vmax=1, extent=(-half, half, -half, half))
    ax.set_title(title)
    ax.set_xlabel('km east')
    ax.set_ylabel('km north')
    ax.grid(False)


def numbers_panel(ax, group):
    ax.axis('off')
    rows = [r for r in T.ROWS if r[0] == group]
    lines = []
    for _g, name, gen, ref, tol, unit, status, _info in rows:
        lines.append(f'{status:4s}  {name[:52]:52s} {gen:9.3f} {ref:9.3f} {tol:>8s} {unit}')
    ax.text(0.0, 1.0, f'{"":4s}  {"check":52s} {"analytic":>9s} {"real":>9s} {"allowed":>8s}\n' + '\n'.join(lines),
            va='top', ha='left', family='monospace', fontsize=7.2, color=INK, transform=ax.transAxes)


def legend(ax):
    ax.legend(loc='best', fontsize=8)


def save(fig, name):
    os.makedirs(C.OUT, exist_ok=True)
    path = os.path.join(C.OUT, f'{name}_profile_sheet.png')
    fig.savefig(path, dpi=100)
    plt.close(fig)
    print('wrote', path)


# ---------------------------------------------------------------- Fuji
def fuji():
    T.check_fuji()
    href, meta, X, Y = C.load_reference('mount_fuji')
    p = meta['pixel_size_m']
    g = C.generated('mount_fuji')
    c = V.FUJI['centre']
    fig, ax = plt.subplots(2, 3, figsize=(16, 10.5), constrained_layout=True)
    hillshade_panel(ax[0, 0], href, p, 'Mount Fuji, GSI DEM10B at 40 m (real)')
    hillshade_panel(ax[0, 1], g['h'], p, 'FUJI preset: exp cone, crater, Hoei, rift cones (analytic)')
    radii = np.arange(250.0, 15001.0, 250.0)
    zr = C.ring_median(href, X, Y, c, radii, 125.0)
    zg = C.ring_median(g['h'], X, Y, c, radii, 125.0)
    F = V.FUJI
    zf = F['base_m'] + V.exp_cone(radii, F['height_m'], F['radius_m'], V.cone_decay_m(F['height_m'],
                                                                                         F['upper_slope_deg']),
                                  F['crater_radius_m'])
    zd = V.exp_cone(radii, 3700.0, 18000.0, V.cone_decay_m(3700.0, 33.0), 540.0)
    a = ax[0, 2]
    a.plot(radii / 1000, zr, color=REAL, label='real, median round the crater')
    a.plot(radii / 1000, zg, color=GEN, label='analytic surface, same measure')
    a.plot(radii / 1000, zf, color=FORMULA, ls='--', label='exp cone formula, FUJI preset')
    a.plot(radii / 1000, zd, color=INK2, ls=':', lw=1.5, label="design's numbers (H 3700, 33 deg, R 18 km), foot at 0")
    a.set_title('Radial profile')
    a.set_xlabel('distance from the crater centre, km')
    a.set_ylabel('height, m')
    legend(a)
    rs_r = C.radial_slope_deg(href, p, X, Y, c)
    rs_g = C.radial_slope_deg(g['h'], p, X, Y, c)
    a = ax[1, 0]
    a.plot(radii / 1000, C.ring_median(rs_r, X, Y, c, radii, 250.0), color=REAL, label='real')
    a.plot(radii / 1000, C.ring_median(rs_g, X, Y, c, radii, 250.0), color=GEN, label='analytic surface')
    lam = V.cone_decay_m(F['height_m'], F['upper_slope_deg'])
    q = radii[radii > F['crater_radius_m']]
    a.plot(q / 1000, V.exp_cone_slope_deg(q, F['height_m'], F['radius_m'], lam, F['crater_radius_m']), color=FORMULA,
           ls='--', label='formula: atan((H/lambda) e^-(r-rc)/lambda / (1 - e^-(R-rc)/lambda))')
    a.set_title('Radial slope (median of the downhill-outward component)')
    a.set_xlabel('distance from the crater centre, km')
    a.set_ylabel('slope, degrees')
    legend(a)
    a = ax[1, 1]
    rr = np.arange(1000.0, 14001.0, 500.0)
    for azs, ls, lab in (((315.0, 135.0), '-', 'rift sectors NW + SE'), ((45.0, 225.0), '--', 'cross sectors NE + SW')):
        zr_s = np.mean([[C.sector_median(href, X, Y, c, q, 250.0, az) for q in rr] for az in azs], axis=0)
        zg_s = np.mean([[C.sector_median(g['h'], X, Y, c, q, 250.0, az) for q in rr] for az in azs], axis=0)
        a.plot(rr / 1000, zr_s, color=REAL, ls=ls, label=f'real, {lab}')
        a.plot(rr / 1000, zg_s, color=GEN, ls=ls, label=f'analytic, {lab}')
    a.set_title('Asymmetry: the flanks along the NW-SE rift stand higher')
    a.set_xlabel('distance from the crater centre, km')
    a.set_ylabel('height, m')
    legend(a)
    numbers_panel(ax[1, 2], 'fuji')
    fig.suptitle('Package 9 (analytic half): the stratovolcano profile against Mount Fuji. The analytic surface is '
                 'the constructional start: no gullies, apron or lava flows yet (second half).', color=INK)
    save(fig, 'mount_fuji')


# ---------------------------------------------------------------- Meteor Crater
def meteor():
    a_m, b_m = T.check_meteor()
    href, meta, X, Y = C.load_reference('meteor_crater')
    p = meta['pixel_size_m']
    g = C.generated('meteor_crater')
    fig, ax = plt.subplots(2, 3, figsize=(16, 10.5), constrained_layout=True)
    hillshade_panel(ax[0, 0], href, p, 'Meteor Crater, 3DEP at 3 m (real)')
    hillshade_panel(ax[0, 1], g['h'], p, 'METEOR_CRATER preset: Pike bowl, 0.143 D fill, ejecta (analytic)')
    a = ax[0, 2]
    a.plot(b_m['rho'], b_m['profile'], color=REAL, label='real, median along rho = r / rim radius')
    a.plot(a_m['rho'], a_m['profile'], color=GEN, label='analytic surface, same measure')
    rho = np.linspace(0, 2.4, 400)
    D = b_m['D']
    hm = b_m['rim_above_plain']
    bowl = np.where(rho <= 1, hm - 0.2 * D * (1 - rho ** 2), hm / np.maximum(rho, 1e-3) ** 3)
    a.plot(rho, bowl, color=FORMULA, ls='--', label='Pike: 0.2 D parabola inside, h (r/R)^-3 outside')
    a.axhline(hm - 0.1426 * D, color=INK2, ls=':', lw=1.2, label='infill 0.143 D below the rim')
    a.set_ylim(-200, 80)
    a.set_title('Profile across the rim (height over the plain)')
    a.set_xlabel('rho = r / rim crest radius at that azimuth')
    a.set_ylabel('m over the plain')
    legend(a)
    a = ax[1, 0]
    for hh, col, lab, start in ((href, REAL, 'real', (17.0, 26.0)), (g['h'], GEN, 'analytic', I.METEOR_CRATER['centre'])):
        cc = T.crater_centre(hh, X, Y, start, 350.0, 800.0)
        azs, rr, _zz = C.rim_crests(hh, X, Y, cc, 350.0, 800.0, 5.0)
        a.plot(azs, rr, color=col, label=f'{lab} rim crest radius')
    a.set_title('Planform: rim crest radius (4 corners)')
    a.set_xlabel('compass azimuth, degrees')
    a.set_ylabel('m from the centre')
    legend(a)
    a = ax[1, 1]
    s_r, s_g = C.slope_deg(href, p), C.slope_deg(g['h'], p)
    for s, hh, col, lab, start in ((s_r, href, REAL, 'real', (17.0, 26.0)), (s_g, g['h'], GEN, 'analytic',
                                                                            I.METEOR_CRATER['centre'])):
        cc = T.crater_centre(hh, X, Y, start, 350.0, 800.0)
        r = np.hypot(X - cc[0], Y - cc[1])
        a.hist(s[r < 560.0], bins=np.arange(0, 75, 2.5), histtype='step', color=col, lw=2,
               label=f'{lab}, inside the rim', density=True)
        a.hist(s[(r > 700.0) & (r < 1200.0)], bins=np.arange(0, 75, 2.5), histtype='step', color=col, lw=1.2, ls='--',
               label=f'{lab}, ejecta 1.15-2 R', density=True)
    a.set_title('Slopes (real walls: cliffs to 70 deg)')
    a.set_xlabel('slope, degrees')
    a.set_ylabel('density')
    legend(a)
    numbers_panel(ax[1, 2], 'meteor')
    fig.suptitle('Package 9 (analytic half): the impact crater stamp against Meteor Crater. No wall gullies, strata '
                 'cliffs or talus yet (second half).', color=INK)
    save(fig, 'meteor_crater')


# ---------------------------------------------------------------- Crater Lake
def lake():
    a_l, b_l = T.check_lake()
    href, meta, X, Y = C.load_reference('crater_lake')
    p = meta['pixel_size_m']
    wr = C.load_reference_water('crater_lake')
    g = C.generated('crater_lake')
    lv = wr[1][0]['level_m']
    fig, ax = plt.subplots(2, 3, figsize=(16, 10.5), constrained_layout=True)
    hillshade_panel(ax[0, 0], href, p, 'Crater Lake, 3DEP at 14 m (real)', wr)
    hillshade_panel(ax[0, 1], g['h'], p, 'CRATER_LAKE preset (analytic)', g['water'])
    a = ax[0, 2]
    a.plot(b_l['azs'], b_l['shore'], color=REAL, label='real shore radius')
    a.plot(a_l['azs'], a_l['shore'], color=GEN, label='analytic shore radius')
    a.plot(b_l['azs'], b_l['rim_r'], color=REAL, ls='--', lw=1.3, label='real rim crest radius')
    a.plot(a_l['azs'], a_l['rim_r'], color=GEN, ls='--', lw=1.3, label='analytic rim crest radius')
    a.set_title('Outline by azimuth: 8 x 10 km, long ENE-WSW, scalloped')
    a.set_xlabel('compass azimuth from the outline centre, degrees')
    a.set_ylabel('m')
    legend(a)
    a = ax[1, 0]
    a.plot(b_l['azs'], b_l['rim_z'] - lv, color=REAL, label='real rim crest above the lake')
    a.plot(a_l['azs'], a_l['rim_z'] - lv, color=GEN, label='analytic rim crest above the lake')
    a.set_title('Rim height round the caldera')
    a.set_xlabel('compass azimuth, degrees')
    a.set_ylabel('m above the lake')
    legend(a)
    a = ax[1, 1]
    c = V.CRATER_LAKE['centre']
    j = int(np.argmin(np.abs(Y[:, 0] - c[1])))
    xs = X[0] / 1000
    a.plot(xs, C.with_lake_surface(href, wr)[j], color=REAL, label='real, west-east through the centre')
    a.plot(xs, C.with_lake_surface(g['h'], g['water'])[j], color=GEN, label='analytic, same line')
    a.plot(xs, g['h'][j], color=GEN, ls=':', lw=1.2, label='analytic under the water: talus, floor, island platform')
    a.set_title('Cross-section: walls, lake, Wizard Island (west)')
    a.set_xlabel('km east of the tile centre')
    a.set_ylabel('height, m')
    legend(a)
    numbers_panel(ax[1, 2], 'lake')
    fig.suptitle('Package 9 (analytic half): the caldera collapse against Crater Lake. The walls are a clean rock '
                 'face over talus: no chutes, cliff bands or eroded outer flanks yet (second half).', color=INK)
    save(fig, 'crater_lake')


# ---------------------------------------------------------------- SP Crater
def sp():
    a_s, b_s = T.check_sp()
    href, p, X, Y = C.load_sp_crater()
    g = C.generated('sp_crater')
    fig, ax = plt.subplots(2, 3, figsize=(16, 10.5), constrained_layout=True)
    hillshade_panel(ax[0, 0], href, p, 'SP Crater field, Terrain Tiles (3DEP 10 m) at 7.8 m (real)')
    hillshade_panel(ax[0, 1], g['h'], p, 'SP_CRATER preset: Wood cone at repose (analytic)')
    a = ax[0, 2]
    radii = np.arange(0.0, 1200.0, 15.0)
    for hh, col, lab, guess in ((href, REAL, 'real', (20.0, -20.0)), (g['h'], GEN, 'analytic', V.SP_CRATER['at'])):
        r0 = np.hypot(X - guess[0], Y - guess[1])
        k = np.argmin(np.where(r0 < 200.0, hh, 1e30))
        cc = (float(X.ravel()[k]), float(Y.ravel()[k]))
        base = float(np.median(hh[(np.hypot(X - cc[0], Y - cc[1]) > 800.0) & (np.hypot(X - cc[0], Y - cc[1]) < 1000.0)]))
        a.plot(radii, C.ring_median(hh, X, Y, cc, radii, p) - base, color=col, label=f'{lab}, median round the crater')
    W = V.SP_CRATER['width_m']
    zf = V.cinder_cone(radii, 0.0 * radii, width_m=W, hw_ratio=0.18, crater_ratio=0.28, flank_deg=32.0,
                       crater_depth_frac=0.41)
    a.plot(radii, zf, color=FORMULA, ls='--', label='formula: H/W 0.18, crater/W 0.28, 32 deg flank, 30 deg walls')
    a.set_title('Radial profile over the cone\'s base')
    a.set_xlabel('distance from the crater floor, m')
    a.set_ylabel('m over the base')
    legend(a)
    a = ax[1, 0]
    s_r, s_g = C.slope_deg(href, p), C.slope_deg(g['h'], p)
    for s, hh, col, lab, guess in ((s_r, href, REAL, 'real', (20.0, -20.0)), (s_g, g['h'], GEN, 'analytic',
                                                                            V.SP_CRATER['at'])):
        r0 = np.hypot(X - guess[0], Y - guess[1])
        k = np.argmin(np.where(r0 < 200.0, hh, 1e30))
        cc = (float(X.ravel()[k]), float(Y.ravel()[k]))
        a.plot(radii, C.ring_median(s, X, Y, cc, radii, p), color=col, label=f'{lab} slope median')
    a.axhspan(30, 33, color=GRID, label='scoria repose 30-33 deg')
    a.set_title('Slope by distance: crater wall, flank at repose, concave toe')
    a.set_xlabel('distance from the crater floor, m')
    a.set_ylabel('slope, degrees')
    legend(a)
    a = ax[1, 1]
    names = ['H / W', 'crater W / W']
    xs = np.arange(len(names))
    a.bar(xs - 0.22, [b_s['hw'], b_s['crater_ratio']], 0.4, color=REAL, label='real SP Crater')
    a.bar(xs + 0.22, [a_s['hw'], a_s['crater_ratio']], 0.4, color=GEN, label='analytic')
    a.scatter(xs, [0.18, 0.40], color=INK, marker='_', s=900, zorder=3, label="Wood 1980's fresh-cone means")
    a.set_xticks(xs, names)
    a.set_title('Wood ratios')
    legend(a)
    numbers_panel(ax[1, 2], 'sp')
    fig.suptitle('Package 9 (analytic half): the cinder cone against SP Crater (the triage\'s Terrain Tiles cache, '
                 'until package 2 fetches 3DEP 1 m). No lava flow or aging yet (second half).', color=INK)
    save(fig, 'sp_crater')


if __name__ == '__main__':
    for f in (fuji, meteor, lake, sp):
        f()
