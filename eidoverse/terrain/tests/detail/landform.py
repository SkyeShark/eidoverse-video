"""The Blender detail package's landform numbers on the port's real_place runs (PORT_PLAN.md 8.2 row P12: "on real_place
Lauterbrunnen the hero levels add detail without moving the landform (main metrics within 1 %)"), by the Blender
package's own code: blender/tests/terrain/detail/sheets.py landform() and landform_vs(), imported and run as they are
(no second implementation). And the port's hero levels against the Blender edition's own run of the same variant.

    <Blender's python> -I eidoverse/terrain/tests/detail/landform.py <port detail save> <port upsampled save>
        [--blender <Blender's detail save>] [--out <json>]

A save is a Terrain.save base path (<base>.npz and <base>.json). Numbers:
  landform           each hero level box-averaged to the main level's 8 m pixel against the main level in the same
                     window (sheets.landform)
  landform_vs        the detail's own effect: each hero level at the main pixel with the detail stages against the
                     same level without them (the upsampled variant), with the Blender package's acceptance rule:
                     slope percentiles within max(1 %, 0.25 deg), relief within 1 %, the hypsometric integral within
                     0.01, and the main level identical (sheets.landform_vs)
  vs_blender         with --blender: per level, the port's h against Blender's (RMS and p99 |dh| over the level's
                     relief, the largest |dh|), and Blender's own landform_vs on its run, beside the port's
Run with Blender's own Python (numpy 2.3.4; plan C6). The Blender edition is found as tests/parity/_blender.py finds it
and is only read (no bytecode is written into it).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

import numpy as np  # noqa: E402


def load_save(base):
    """(plan [Level], fields [{'h': ...}], info) of a Terrain.save."""
    from eidoblend.terrain.core.levels import Level
    with open(base + '.json', encoding='utf-8') as f:
        meta = json.load(f)
    plan = [Level.from_dict(d) for d in meta['plan']]
    fields = []
    with np.load(base + '.npz') as z:
        for lv in plan:
            fields.append({'h': np.asarray(z[f'L{lv.index}__f__h'])})
    return plan, fields, meta


def vs(plan, a, b):
    out = {}
    for lv in plan:
        ha, hb = np.asarray(a[lv.index]['h'], np.float64), np.asarray(b[lv.index]['h'], np.float64)
        d = ha - hb
        relief = float(np.ptp(hb)) or 1.0
        out[lv.index] = dict(role=lv.role, cell=lv.cell, rms_over_relief=float(np.sqrt(np.mean(d * d)) / relief),
                             p99_over_relief=float(np.percentile(np.abs(d), 99) / relief), max_abs_m=float(np.abs(d).max()),
                             bit_identical=bool(np.array_equal(ha, hb)))
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('detail')
    ap.add_argument('upsampled')
    ap.add_argument('--blender', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args(B.script_args())
    root = B.bare_terrain_package()
    for p in (os.path.join(root, 'blender', 'tests', 'terrain', 'core'), os.path.join(root, 'blender', 'tests', 'terrain', 'detail')):
        if p not in sys.path:
            sys.path.insert(0, p)
    import sheets as S                                       # the Blender detail package's numbers, as they are
    plan, det, meta = load_save(a.detail)
    plan_u, ups, _ = load_save(a.upsampled)
    if [lv.to_dict() for lv in plan] != [lv.to_dict() for lv in plan_u]:
        sys.exit('landform: the two saves have different plans')
    out = dict(port=dict(landform=S.landform(plan, det), landform_vs=S.landform_vs(plan, det, ups)),
               saves=dict(detail=a.detail, upsampled=a.upsampled), versions=B.versions())
    if a.blender:
        plan_b, bl, _ = load_save(a.blender)
        if [lv.to_dict() for lv in plan_b] != [lv.to_dict() for lv in plan]:
            out['vs_blender'] = 'the plans differ'
        else:
            out['vs_blender'] = vs(plan, det, bl)
            out['blender'] = dict(landform=S.landform(plan, bl), landform_vs=S.landform_vs(plan, bl, ups))
    txt = json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(txt)
    lv_ = out['port']['landform_vs']
    print(f"[landform] port detail vs upsampled: {'PASS' if lv_['ok'] else 'FAIL'}; main level identical "
          f"{lv_['main_level_identical']}", flush=True)
    for i, row in lv_.items():
        if isinstance(row, dict):
            print(f"[landform]   L{i}: " + ', '.join(f"{k.replace('slope_deg_', '')} {r['diff']:+.2f}" for k, r in row.items()
                                                    if k.startswith('slope')) +
                  f", relief {row['relief_m']['rel'] * 100:+.2f}%, HI {row['hypsometric_integral']['diff']:+.4f}, "
                  f"rms dh {row['rms_dh_m']:.2f} m, {'ok' if row['ok'] else 'OVER'}", flush=True)
    if isinstance(out.get('vs_blender'), dict):
        for i, r in out['vs_blender'].items():
            print(f"[landform]   vs Blender L{i} ({r['role']} {r['cell']} m): RMS {r['rms_over_relief']:.2e} of relief, "
                  f"p99 {r['p99_over_relief']:.2e}, max {r['max_abs_m']:.3f} m{' (identical)' if r['bit_identical'] else ''}",
                  flush=True)
    sys.exit(0 if lv_['ok'] else 1)


if __name__ == '__main__':
    main()
