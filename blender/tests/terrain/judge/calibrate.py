"""Calibrate the bands on the references (DESIGN.md section 10 item 3: "the judge calibrates the anisotropy and
spectrum bands by running every reference through itself") and write bands.json:

  spectrum_slope_tol (per reference)  max(0.5, 2 x the standard deviation of the spectrum slope over the
                                      reference's four quadrants): the design's 0.5 wherever the landform allows it,
                                      wider where the real place itself varies that much (a coast half sea, a radar
                                      dune field)
  anisotropy_4_plus / _8_plus         the median over the references of how far a quadrant's A4 (A8) rises above
                                      the whole tile's: the natural spread of the grid-direction anisotropy. The band
                                      is A <= max(1.5 x the reference's, the reference's + this). The design's "1.5 x
                                      the largest over all the references" would be A4 <= 0.73 (the Namib linear
                                      dunes' real north-south grain is 0.49), which no combed generator would fail;
                                      per reference, a combed range fails against the San Gabriels (A4 0.024)
  references.<name>                   its own numbers at its pixel (generic and family), and which of the design's
                                      absolute family ranges the real place falls outside of

    python blender/tests/terrain/judge/calibrate.py          # plain Python, ~1 minute
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

from judge import bands as B, family as F, generic as G, refs  # noqa: E402
from eidoblend.terrain.core import metrics as M  # noqa: E402


def quadrant_stats(h, cell):
    n = h.shape[0] // 2
    whole = M.metrics(h, cell, with_depressions=False)
    q = [M.metrics(h[j:j + n, i:i + n], cell, with_depressions=False) for j in (0, n) for i in (0, n)]
    return whole, q


def main():
    t0 = time.time()
    out = dict(
        about='The judge\'s calibrated bands (blender/tests/terrain/judge/calibrate.py wrote this; bands.py holds '
              'the specs, the design\'s section 10 item 3 and 4, copied below for reading). The judge reads the '
              'calibration from here.',
        made=time.strftime('%Y-%m-%d %H:%M'),
        generic_specs={k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()}
                       for k, v in B.GENERIC.items()},
        family_specs={f: {k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()}
                          for k, v in d.items()} for f, d in B.FAMILY.items()},
        calibration={}, references={})
    rise4, rise8 = [], []
    for name in refs.names():
        ref = refs.load(name)
        whole, q = quadrant_stats(ref.h, ref.pixel)
        qs = [x['spectrum_slope'] for x in q]
        tol = max(0.5, 2.0 * float(np.std(qs)))
        rise4.append(max(0.0, max(x['anisotropy_4'] for x in q) - whole['anisotropy_4']))
        rise8.append(max(0.0, max(x['anisotropy_8'] for x in q) - whole['anisotropy_8']))
        nums = G.numbers(ref.h, ref.pixel, ref.lake_mask())
        fam = F.family_numbers(ref.family, ref.h, ref.pixel, sea_level=ref.sea_level)
        outside = []
        for key, spec in B.FAMILY.get(ref.family, {}).items():
            r = B.evaluate(key, spec, fam.get(key), fam.get(key))
            if r.get('note'):
                outside.append(f"{key} {B._fmt(fam.get(key))} (design {spec.get('range') or spec.get('min') or spec.get('max')})")
        out['references'][name] = dict(
            family=ref.family, pixel_m=ref.pixel, extent_m=ref.extent, soft_native_m=ref.native_m if ref.soft else None,
            calibration=dict(spectrum_slope_tol=round(tol, 3)),
            quadrant_spectrum_slopes=[round(v, 3) for v in qs],
            numbers={k: (round(v, 5) if isinstance(v, float) else v) for k, v in nums.items()
                     if not isinstance(v, list)},
            family_numbers={k: (round(v, 4) if isinstance(v, float) else v) for k, v in fam.items()
                            if k not in ('cones', 'notch_heights_m', 'u_exponents', 'benches', 'flank_slopes')},
            outside_design_range=outside)
        print(f'[calibrate] {name:24s} spectrum slope {whole["spectrum_slope"]:6.2f} tol {tol:.2f}  '
              f'A4 rise {rise4[-1]:.3f} A8 rise {rise8[-1]:.3f}' + (f'  outside: {"; ".join(outside)}' if outside else ''),
              flush=True)
    out['calibration'] = dict(anisotropy_4_plus=round(float(np.median(rise4)), 4),
                              anisotropy_8_plus=round(float(np.median(rise8)), 4),
                              how='the median over the references of max(0, the largest quadrant\'s anisotropy - '
                                  'the whole tile\'s)')
    with open(B.BANDS_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    print(f'[calibrate] wrote {B.BANDS_JSON}: anisotropy allowances A4 +{out["calibration"]["anisotropy_4_plus"]}, '
          f'A8 +{out["calibration"]["anisotropy_8_plus"]} ({time.time() - t0:.0f}s)')


if __name__ == '__main__':
    main()
