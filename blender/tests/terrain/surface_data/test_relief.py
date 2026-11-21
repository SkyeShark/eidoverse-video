"""The relief below the cell as a gully spectrum (SURFACING_DESIGN.md 2.3, step 3; the 11-20 fix of the washboard), in
plain Python through the numpy twins (no Blender):

    python blender/tests/terrain/surface_data/test_relief.py

Checks:
  reuse      twins.gully_octave with neither spacing nor depth varied is solvers/detail.py's phacelle_noise (the
             gully filter the geometry's gully stage uses), to rounding
  octaves    bake._gully_octaves keys every octave by world wavelength from one top octave on every level: a parent and
             its child share their octaves (wavelength, lattice base and offset) and the child adds the finer ones; an
             octave of at least 3 cells reads a geometry gate
  cone       on a smooth stamped cone (the stratovolcano's and the cinder cones' case) the twin of phacelle.glsl:
             - a spectrum: the shaded relief's power across the fall line (along contours) spreads over several
               octaves, where the old one-octave relief put most of it in one (the corrugation); the judge's
               repetition on crops of the flank is reported beside it as a diagnostic;
             - a few deep gullies: the depth is heavy-tailed (the 99th percentile of |relief| several times its median);
             - water: the upper flank, under the catchment an octave needs, is smoother than the lower;
             - sand: none where 0.6 m of sand lies; snow: an octave under a snowpack of twice its amplitude is gone
Writes out/surface_data/relief.json and out/surface_data/relief_cone.png (hillshades: the old relief | the new).
"""
import json
import math
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import numpy as np  # noqa: E402

from eidoblend.terrain.core import world_noise as N  # noqa: E402
from eidoblend.terrain.solvers import detail as DT  # noqa: E402
from eidoblend.terrain.surface import bake as B  # noqa: E402
from eidoblend.terrain.surface import twins as TW  # noqa: E402

OUT = os.path.join(HERE, '..', 'out', 'surface_data')
F = np.float32
TAU = 2.0 * math.pi


def check_reuse():
    rng = np.random.default_rng(3)
    px = rng.uniform(-40.0, 40.0, (64, 64))
    py = rng.uniform(-40.0, 40.0, (64, 64))
    a = rng.uniform(0, TAU, (64, 64))
    dx, dy = np.cos(a), np.sin(a)
    c0, s0, sdx, sdy = DT.phacelle_noise(px, py, dx, dy, 1.0, 0.25, 0.5, (17, -5))
    c1, s1, gx, gy, Am, _ax, _ay = TW.gully_octave(px, py, 17, -5, dx, dy, 1.0, 0.5, 0.0, 0.0, 3.0)
    err = max(float(np.abs(c1 - c0).max()), float(np.abs(s1 - s0).max()),
              float(np.abs(gx - (-s0 * sdx)).max()), float(np.abs(gy - (-s0 * sdy)).max()),
              float(np.abs(Am - 1.0).max()))
    return dict(ok=err < 1e-9, max_error=err)


class _Lv(SimpleNamespace):
    pass


def check_octaves():
    """A main level of 7.8125 m and two hero levels below it: the tables' rows, as the bake makes them."""
    lvs = [_Lv(index=0, role='main', cell=7.8125, n=1024, x0=-4000.0, y0=-4000.0, parent=None),
           _Lv(index=1, role='hero', cell=3.90625, n=1024, x0=-1500.0, y0=-1800.0, parent=0),
           _Lv(index=2, role='hero', cell=0.48828125, n=1024, x0=-300.0, y0=-200.0, parent=1)]
    bk = B._Baker.__new__(B._Baker)
    bk.levels, bk.main, bk.seed, bk.o, bk._stages = lvs, 0, 1, B.resolve_options(SimpleNamespace(), None, None), []
    bk.t = SimpleNamespace(recipe=None)
    rows = []
    for i, lv in enumerate(lvs):
        fD = B.detail_factor(lv, bk.o)
        octs, _gp, _rp = bk._gully_octaves(i, lv.cell / fD)
        r = []
        for k in range(octs.shape[1] // 2):
            A, Bv = octs[0, 2 * k], octs[0, 2 * k + 1]
            lam = 1.0 / float(Bv[0])
            x0p = lv.x0 - B.MARGIN * lv.cell
            # the lattice cell of a world point on this level (base + floor(fraction + (x - x0p) / lam))
            cell0 = int(A[0]) + math.floor(float(A[2]) + (123.456 - x0p) / lam)
            r.append(dict(lam=round(lam, 6), amp=round(float(Bv[1]), 6), gate=int(Bv[3]), cell0=cell0,
                          coarse=lam >= 3.0 * lv.cell))
        rows.append(r)
    top = [r[0]['lam'] for r in rows]
    # a context level too coarse for any octave: a placeholder row the kernel never runs (bake passes uOct 0)
    ctx = _Lv(index=3, role='context', cell=156.25, n=1024, x0=-80000.0, y0=-80000.0, parent=None)
    bk.levels = lvs + [ctx]
    octs_c, _gp, _rp = bk._gully_octaves(3, ctx.cell)
    none_ok = int((octs_c[0, 1::2, 2] > 0.5).sum()) == 0
    bk.levels = lvs
    shared_ok = True
    for p, c in ((0, 1), (1, 2)):
        for rp in rows[p]:
            hit = [rc for rc in rows[c] if rc['lam'] == rp['lam']]
            shared_ok &= len(hit) == 1 and hit[0]['cell0'] == rp['cell0'] and hit[0]['amp'] == rp['amp']
        shared_ok &= len(rows[c]) > len(rows[p])
    gates_ok = all((r['gate'] >= 0) == r['coarse'] for rr in rows for r in rr)
    return dict(ok=bool(shared_ok and gates_ok and none_ok and len(set(top)) == 1), top_m=top[0],
                shared=bool(shared_ok), gates=bool(gates_ok), coarse_level_none=bool(none_ok),
                octaves=[[r['lam'] for r in rr] for rr in rows])


def cone(n=320, cell=4.0, R=560.0, H=260.0):
    """A smooth stamped cinder cone (repose flank, flat crater floor) on a plain: h, the downhill direction, the
    specific catchment of divergent flow on a cone (r / 2 below the rim)."""
    c = (np.arange(n) + 0.5 - n / 2) * cell
    X, Y = np.meshgrid(c, c)
    r = np.hypot(X, Y)
    rim = 90.0
    h = np.where(r < rim, H - 30.0 * (1 - r / rim), H * np.clip(1 - (r - rim) / (R - rim), 0, 1))
    with np.errstate(invalid='ignore', divide='ignore'):
        dx, dy = np.where(r > 0, X / r, 0.0), np.where(r > 0, Y / r, 0.0)
    a = np.where(r > rim, (r * r - rim * rim) / (2.0 * np.maximum(r, 1.0)), 4.0) + 4.0
    return X, Y, r, h.astype(F), dx, dy, a.astype(F)


def run_phacelle(h, dx, dy, a, cell, octs, rp, sand=None, snow=None, uk=None):
    """phacelle's twin on a field at one texel per cell, every gate open but the ones given."""
    n = h.shape[0]
    hg = TW.field_normal({'hT': np.stack([h, h, h, h], 2)}, {'uTexel': cell})['outG']
    steer = np.zeros((n, n, 4), F)
    steer[..., 2], steer[..., 3] = dx, dy
    cov = np.zeros((n, n, 4), F)
    cov[..., 1] = 0.0 if sand is None else sand
    cov[..., 0] = cov[..., 1]
    cov[..., 2] = 0.0 if snow is None else snow
    cov[..., 3] = a
    u = {'uOct': octs.shape[1] // 2, 'uTexel': cell, 'uF': 1, 'uSteer': float(rp['steer']), 'uNorm': 0.5,
         'uSlope': (10.0, 18.0, 30.0, 38.0), 'uRockDeg': (34.0, 46.0), 'uCover': (0.1, 1.0), 'uNormalCap': 4.0,
         'uRockRef': 1.0, 'uRockOn': 0, 'uStrength': 0.5,
         'uSpec': (float(rp['jitter']), float(rp['spread']), float(rp['along']), 0.0),
         'uInit': (float(rp['initiation']), float(rp['loose_initiation'])) + tuple(float(v) for v in rp['sand_m']),
         'uLoose': tuple(float(v) for v in rp['loose_m']), 'uBury': tuple(float(v) for v in rp['bury'])}
    u.update(uk or {})
    s = {'hgT': hg, 'steerT': steer, 'octT': octs, 'rockT': np.zeros((1, 1, 4), F), 'coverT': cov,
         'gateT': np.ones((n, n, 4), F)}
    out = TW.phacelle(s, u)
    return out['outR'][..., 0].astype(np.float64), out['outD'][..., 2:4].astype(np.float64)


def table(lams, k, x0, seed=1):
    rows = []
    for lam in lams:
        o = int(round(math.log2(B.GULLY_LAMBDA0_M / lam)))
        ox, oy = N.lattice_offset(seed + 4242, o)
        bx = math.floor(x0 / lam)
        rows.append([(bx + ox, bx + oy, x0 / lam - bx, x0 / lam - bx), (1.0 / lam, k * lam, 1.0, -1.0)])
    t = np.zeros((1, 2 * len(rows), 4), F)
    for q, (aa, bb) in enumerate(rows):
        t[0, 2 * q], t[0, 2 * q + 1] = aa, bb
    return t


def shade(h, g, cell, s=0.5, az=225.0, el=25.0):
    hy, hx = np.gradient(h.astype(np.float64), cell)
    nx, ny = -(hx + s * g[..., 0]), -(hy + s * g[..., 1])
    L = np.sqrt(nx * nx + ny * ny + 1.0)
    A, E = math.radians(az), math.radians(el)
    return np.clip((nx * math.cos(E) * math.sin(A) + ny * math.cos(E) * math.cos(A) + math.sin(E)) / L, 0, 1)


def contour_profile(field, X, Y, r0, cell, n_theta=2048):
    """The field along the circle r = r0 (bilinear), one value per arc step of about half a cell."""
    th = np.linspace(0, TAU, n_theta, endpoint=False)
    x = r0 * np.cos(th) / cell + field.shape[1] / 2 - 0.5
    y = r0 * np.sin(th) / cell + field.shape[0] / 2 - 0.5
    i0, j0 = np.floor(x).astype(int), np.floor(y).astype(int)
    tx, ty = x - i0, y - j0
    f = field
    return ((f[j0, i0] * (1 - tx) + f[j0, i0 + 1] * tx) * (1 - ty)
            + (f[j0 + 1, i0] * (1 - tx) + f[j0 + 1, i0 + 1] * tx) * ty), TAU * r0 / n_theta


def high_pass(p, step, cut_m=96.0):
    """The profile less its running mean over cut_m (the cone's own shading round the circle)."""
    k = max(1, int(round(cut_m / step)))
    pad = np.concatenate([p[-k:], p, p[:k]])
    ker = np.ones(2 * k + 1) / (2 * k + 1)
    return p - np.convolve(pad, ker, mode='same')[k:-k]


def repetition(p):
    """The second peak of the autocorrelation of a periodic profile (the judge's repetition, in one dimension)."""
    q = p - p.mean()
    ac = np.fft.irfft(np.abs(np.fft.rfft(q)) ** 2, n=q.size)
    ac = ac / max(ac[0], 1e-12)
    k = 1
    while k < ac.size // 2 and ac[k] > 0:
        k += 1
    return float(ac[k:ac.size // 2].max()) if k < ac.size // 2 else 0.0


def octave_shares(p, step, lams):
    """The share of the profile's power in each octave band around the given wavelengths."""
    q = p - p.mean()
    P = np.abs(np.fft.rfft(q)) ** 2
    f = np.fft.rfftfreq(q.size, d=step)
    out = []
    for lam in lams:
        b = (f >= 1.0 / (lam * math.sqrt(2))) & (f < math.sqrt(2) / lam)
        out.append(float(P[b].sum()))
    tot = max(sum(out), 1e-30)
    return [v / tot for v in out]


def check_cone(save=True):
    cell = 4.0
    X, Y, r, h, dx, dy, a = cone(cell=cell)
    rp = dict(B.DEFAULTS['relief'])
    x0 = float(X[0, 0] - 0.5 * cell)
    # the old relief: the one octave a 4 m level's band held (8 m: under 3 cells, over 2 texels), k 0.08, nothing
    # varied, every gate open
    old_t = table([8.0], 0.08, x0)
    rel_old, g_old = run_phacelle(h, dx, dy, np.full_like(a, 1e9), cell, old_t,
                                  dict(rp, steer=0.6, jitter=0.0, spread=0.0))
    # the new: the spectrum from 64 m down to 2 texels (8 m)
    lams = [64.0, 32.0, 16.0, 8.0]
    new_t = table(lams, float(rp['k']), x0)
    rel_new, g_new = run_phacelle(h, dx, dy, a, cell, new_t, rp)
    flank = (r > 200.0) & (r < 500.0)
    res = {}
    # corrugation: the repetition of the shaded relief along contours on the lower flank
    reps_old, reps_new, sh_old, sh_new = [], [], [], []
    for r0 in (320.0, 380.0, 440.0):
        po, step = contour_profile(shade(h, g_old, cell), X, Y, r0, cell)
        pn, _ = contour_profile(shade(h, g_new, cell), X, Y, r0, cell)
        po, pn = high_pass(po, step), high_pass(pn, step)
        reps_old.append(repetition(po))
        reps_new.append(repetition(pn))
        sh_old.append(octave_shares(po, step, lams))
        sh_new.append(octave_shares(pn, step, lams))
    res['repetition_along_contours_old'] = [round(v, 3) for v in reps_old]
    res['repetition_along_contours_new'] = [round(v, 3) for v in reps_new]
    so, sn = np.mean(sh_old, axis=0), np.mean(sh_new, axis=0)
    res['shade_power_by_octave_old'] = [round(float(v), 3) for v in so]
    res['shade_power_by_octave_new'] = [round(float(v), 3) for v in sn]
    # the judge's repetition (surfacing_judge/measures.py: the 2-D autocorrelation's second peak of the high-passed
    # luma) on 96-texel crops of the shaded flank, three bearings
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))
    from surfacing_judge import measures as JM
    so_img, sn_img = shade(h, g_old, cell), shade(h, g_new, cell)
    rj_old, rj_new = [], []
    n = h.shape[0]
    for az in (200.0, 250.0, 300.0):
        cx = int(n / 2 + 380.0 / cell * math.cos(math.radians(az)))
        cy = int(n / 2 + 380.0 / cell * math.sin(math.radians(az)))
        box = (cx - 48, cy - 48, cx + 48, cy + 48)
        rj_old.append(JM.repetition(so_img * 255.0, box)['peak'] or 0.0)
        rj_new.append(JM.repetition(sn_img * 255.0, box)['peak'] or 0.0)
    res['repetition_2d_old'] = [round(float(v), 3) for v in rj_old]
    res['repetition_2d_new'] = [round(float(v), 3) for v in rj_new]
    # (a diagnostic, not a gate: in a 96-texel window the judge's measure sees six of the 64 m octave's wavelengths,
    # and its 6 px high-pass takes out half of them; the octave shares and the depth's tail say what the eye sees)
    res['repetition_2d_lower'] = bool(np.mean(rj_new) < np.mean(rj_old))
    res['spectrum'] = bool(float(so.max()) > 0.6 and float(sn.max()) < 0.6 and int((sn > 0.1).sum()) >= 3)
    # a few deep gullies: heavy-tailed depth on the lower flank
    dep = np.abs(rel_new[flank & (r > 300)])
    res['depth_p50_p99'] = [round(float(np.percentile(dep, 50)), 3), round(float(np.percentile(dep, 99)), 3)]
    res['heavy_tail'] = bool(np.percentile(dep, 99) > 4.0 * max(np.percentile(dep, 50), 1e-6))
    # water: the upper flank, under the catchment the coarse octaves need, carries only the fine rills: its relief
    # (metres) is a fraction of the lower flank's, where the old relief was the same everywhere
    up, low = (r > 110) & (r < 170), (r > 380) & (r < 480)
    rms = lambda a, m: round(float(np.sqrt((a[m] ** 2).mean())), 4)  # noqa: E731
    res['relief_rms_upper_lower_m'] = [rms(rel_new, up), rms(rel_new, low)]
    res['relief_rms_upper_lower_m_old'] = [rms(rel_old, up), rms(rel_old, low)]
    res['water'] = bool(res['relief_rms_upper_lower_m'][0] < 0.5 * res['relief_rms_upper_lower_m'][1])
    # sand and snow
    rel_sand, _ = run_phacelle(h, dx, dy, a, cell, new_t, rp, sand=np.full_like(h, 0.6))
    res['sand_max_relief_m'] = round(float(np.abs(rel_sand).max()), 6)
    one = table([16.0], float(rp['k']), x0)
    amp = float(rp['k']) * 16.0
    rel_bare, _ = run_phacelle(h, dx, dy, a, cell, one, rp)
    rel_snow, _ = run_phacelle(h, dx, dy, a, cell, one, rp, snow=np.full_like(h, 2.0 * amp))
    res['snow_buried'] = round(float(np.abs(rel_snow).max() / max(np.abs(rel_bare).max(), 1e-9)), 6)
    res['sand_snow'] = bool(res['sand_max_relief_m'] == 0.0 and res['snow_buried'] == 0.0)
    if save:
        try:
            from PIL import Image
            c = slice(20, -20)
            img = np.concatenate([shade(h, g_old, cell)[c, c], shade(h, g_new, cell)[c, c]], axis=1)
            Image.fromarray((img[::-1] * 255).astype(np.uint8)).save(os.path.join(OUT, 'relief_cone.png'))
        except ImportError:
            pass
    res['ok'] = bool(res['spectrum'] and res['heavy_tail'] and res['water'] and res['sand_snow'])
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {'reuse': check_reuse(), 'octaves': check_octaves(), 'cone': check_cone()}
    ok = all(v['ok'] for v in rep.values())
    with open(os.path.join(OUT, 'relief.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1)
    for k, v in rep.items():
        print(f'[test_relief] {k}: {"ok" if v["ok"] else "FAIL"} {json.dumps({q: w for q, w in v.items() if q != "ok"})}')
    print(f'[test_relief] {"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
