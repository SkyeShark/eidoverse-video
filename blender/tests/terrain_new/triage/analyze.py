"""Numbers behind the triage's visual calls, from each cached field in metres (plain numpy):

  slope p50 / p90 / p99 / max   degrees, finite differences over one texel
  cliff%     area steeper than 60 degrees (walls: stretched texels on the mesh, a texture smear)
  flat%      area under 2 degrees
  base%      area within 0.5% of the relief of the lowest level: how much of the tile is the untouched plane a stamp
             was set on
  terrace    the largest share of the area that sits in any one 1/200-of-relief height band (a dead-flat terrace,
             plateau or floor shows as a spike; smooth relief spreads out to ~0.5-2%)
  profile    radial mean-height profile around the highest point for the cone-like subjects (volcano, cinder cones)

  --hydro    also routes water over the field (the port's hydrology.py: priority-flood fill, flow accumulation): the
             share of the tile that fills as lakes, the deepest lake, and the share that carries a channel. Real
             drained land fills ~1%; a field full of closed pits fills far more.

    python analyze.py [name,name] [--hydro]     # prints a table, writes renders/analysis.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scenes  # noqa: E402


def metrics(name):
    d = np.load(scenes.cache_path(name), allow_pickle=False)
    m = json.loads(str(d['meta']))
    z = d['height'].astype(np.float64) * m['vs'] * m['W']
    n = z.shape[0]
    tex = m['W'] / n
    gy, gx = np.gradient(z, tex)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    rel = float(z.max() - z.min())
    lo = z.min()
    base = float(np.mean(z <= lo + 0.005 * max(rel, 1e-6)))
    hist, _e = np.histogram(z, bins=200)
    out = {'relief_m': rel, 'texel_m': tex,
           'slope_p50': float(np.percentile(s, 50)), 'slope_p90': float(np.percentile(s, 90)),
           'slope_p99': float(np.percentile(s, 99)), 'slope_max': float(s.max()),
           'cliff_pct': float(np.mean(s > 60) * 100), 'flat_pct': float(np.mean(s < 2) * 100),
           'base_pct': base * 100, 'terrace_pct': float(hist.max() / z.size * 100)}
    return out, z, s, m


def radial_profile(z, tex, nbins=40):
    j, i = np.unravel_index(int(np.argmax(z)), z.shape)
    yy, xx = np.indices(z.shape)
    r = np.hypot(xx - i, yy - j) * tex
    rmax = min(i, j, z.shape[1] - i, z.shape[0] - j) * tex
    bins = np.linspace(0, rmax, nbins + 1)
    k = np.digitize(r.ravel(), bins) - 1
    ok = (k >= 0) & (k < nbins)
    prof = np.bincount(k[ok], weights=z.ravel()[ok], minlength=nbins) / np.maximum(np.bincount(k[ok], minlength=nbins), 1)
    mid = 0.5 * (bins[1:] + bins[:-1])
    slope = np.degrees(np.arctan(-np.gradient(prof, mid)))
    return mid, prof, slope


def hydro(name):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', 'terrain_ekigar')))
    import _ekigar_load
    ek = _ekigar_load.load()
    d = np.load(scenes.cache_path(name), allow_pickle=False)
    m = json.loads(str(d['meta']))
    h = d['height'].astype(np.float64)
    z0 = np.zeros_like(h)
    hy = ek.Heightfield(np.stack([h, z0, z0, z0]), {}, m['tile'], m['W'], m['vs']).hydrology()
    return {'lake_pct': float((hy['lakeDepth_m'] > 0.5).mean() * 100), 'lake_max_m': float(hy['lakeDepth_m'].max()),
            'channel_pct': float((hy['channels'] > 0.5).mean() * 100)}


if __name__ == '__main__':
    argv = [a for a in sys.argv[1:] if not a.startswith('--')]
    names = argv[0].split(',') if argv else [s['name'] for s in scenes.SUBJECTS]
    want_hydro = '--hydro' in sys.argv
    res = {}
    print(f"{'subject':34s} {'relief':>8s} {'p50':>5s} {'p90':>5s} {'p99':>5s} {'max':>5s} {'cliff%':>7s} "
          f"{'flat%':>6s} {'base%':>6s} {'terr%':>6s}")
    for nme in names:
        if not os.path.exists(scenes.cache_path(nme)):
            continue
        r, z, s, m = metrics(nme)
        if any(k in nme for k in ('volcano', 'fuji', 'cone', 'lavaDome', 'bornhardt', 'hemisphere')):
            mid, prof, sl = radial_profile(z, r['texel_m'])
            r['radial_slope_deg'] = [round(float(v), 1) for v in sl[::4]]
            r['radial_r_m'] = [round(float(v)) for v in mid[::4]]
        if want_hydro:
            r.update(hydro(nme))
        res[nme] = r
        print(f"{nme:34s} {r['relief_m']:8.0f} {r['slope_p50']:5.1f} {r['slope_p90']:5.1f} {r['slope_p99']:5.1f} "
              f"{r['slope_max']:5.1f} {r['cliff_pct']:7.2f} {r['flat_pct']:6.1f} {r['base_pct']:6.1f} "
              f"{r['terrace_pct']:6.2f}" + (f"  lakes {r['lake_pct']:5.1f}% (deepest {r['lake_max_m']:.0f} m) "
                                            f"channels {r['channel_pct']:.2f}%" if want_hydro else ''))
    os.makedirs(scenes.RENDERS, exist_ok=True)
    p = os.path.join(scenes.RENDERS, 'analysis.json')
    old = json.load(open(p)) if os.path.exists(p) else {}
    old.update(res)
    with open(p, 'w') as f:
        json.dump(old, f, indent=1)
