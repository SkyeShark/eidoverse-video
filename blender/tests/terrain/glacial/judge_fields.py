"""Judge what gen.py made, in plain Python: the judge package's verdict beside the reference, the level seams, and a
sheet of hillshades, trough cross-sections and the trunk's long profile beside the reference's.

    python blender/tests/terrain/glacial/judge_fields.py <out_dir> <tag> [<tag> ...]

Per tag: <tag>_verdict.json (numbers, bands, verdict), <tag>_seams.json (each child level against its parent: |dh| on
the edge ring <= 0.05 m, slope jump <= 3 degrees) and <tag>_sheet.png:
  row 1  the reference's hillshade, the generated main level's (north up), the trough / floor / wall masks over it,
         the coarsest level with the glacial centrelines' footprint
  row 2  five cross-sections of the trunk, reference (grey) and generated (blue), heights above each section's
         floor, the same scales; the trunk's long profile (floor height against distance from its head)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import matplotlib  # noqa: E402

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.terrain.core import grid as Gd  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
from judge import family as FA  # noqa: E402
from judge import judge, refs  # noqa: E402


def levels_of(path):
    d = np.load(path)
    out = []
    i = 0
    while f'L{i}_window' in d.files:
        w = d[f'L{i}_window']
        f = {k[len(f'L{i}_'):]: d[k] for k in d.files if k.startswith(f'L{i}_') and not k.endswith('_window')}
        out.append(dict(x0=w[0], y0=w[1], side=w[2], cell=w[3], n=int(w[4]), fields=f))
        i += 1
    return out


def seams(levels):
    rows = []
    for c in levels[1:]:
        # the parent: the level whose window holds this one with twice its cell
        p = next(q for q in levels if abs(q['cell'] - 2 * c['cell']) < 1e-6 * c['cell'])
        i0 = int(round((c['x0'] - p['x0']) / p['cell']))
        j0 = int(round((c['y0'] - p['y0']) / p['cell']))
        m = int(round(c['side'] / p['cell']))
        up = Gd.crop_upsample2(p['fields']['h'], i0, j0, m, 'catmull').astype(np.float64)
        hc = np.asarray(c['fields']['h'], np.float64)
        ring = np.zeros(hc.shape, bool)
        ring[0, :] = ring[-1, :] = ring[:, 0] = ring[:, -1] = True
        dh = float(np.abs(hc - up)[ring].max())
        sc = Gd.slope_deg(hc, c['cell'])
        sp = Gd.slope_deg(up, c['cell'])
        ring2 = np.zeros(hc.shape, bool)
        ring2[1, 1:-1] = ring2[-2, 1:-1] = ring2[1:-1, 1] = ring2[1:-1, -2] = True
        jump = float(np.abs(sc - sp)[ring | ring2].max())
        rows.append(dict(child_cell_m=float(c['cell']), edge_max_dh_m=dh, edge_slope_jump_deg=jump,
                         ok=dh <= 0.05 and jump <= 3.0))
    return rows


def shade(h, cell):
    return IO.hillshade(np.asarray(h, np.float64), cell)[::-1]           # north up


def trunk_sections(h, cell, n=5, half=3000.0):
    """[(offsets, heights above the section's floor)] across the trunk at n stations, and the trunk's long profile
    (distance from its head m, floor height m)."""
    area, recv, _ = FA.drainage(h, cell)
    path = FA.trunk(h, cell, area, recv)
    if not path:
        return [], None
    hs = FA.blur(h, 1.0)
    hw = max(3, int(150 / cell))
    secs = []
    for c, d in FA.stations(path, n, 0.15, 0.85, half_window=hw):
        t, z = FA.section(hs, cell, c, d, half)
        secs.append((t, z - z.min()))
    p = np.asarray(path, np.float64)
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))]) * cell
    zl = FA.sample(hs, p[:, 0], p[:, 1])
    return secs, (s, zl)


def sheet(tag, out_dir, ref, levels, lines, path):
    d = np.load(os.path.join(out_dir, tag + '.npz'))
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    base = float(d['base_elevation_m']) if 'base_elevation_m' in d.files else 0.0
    main = next(lv for lv in levels if abs(lv['side'] - h.shape[0] * cell) < 1e-3 * lv['side'])
    fig = plt.figure(figsize=(26, 15), dpi=72)
    gs = fig.add_gridspec(3, 5, height_ratios=[1.25, 0.8, 0.8])
    ext_r = [-ref.extent / 2, ref.extent / 2] * 2
    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(shade(ref.h, ref.pixel), cmap='gray', extent=ext_r)
    ax.set_title(f'reference: {ref.name} ({ref.pixel:g} m)')
    ext_g = [main['x0'], main['x0'] + main['side'], main['y0'], main['y0'] + main['side']]
    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(shade(h, cell), cmap='gray', extent=ext_g)
    ax.set_title(f'generated main level ({cell:.3g} m)')
    ax = fig.add_subplot(gs[0, 2])
    ax.imshow(shade(h, cell), cmap='gray', extent=ext_g)
    f = main['fields']
    if 'trough' in f:
        rgba = np.zeros(h.shape + (4,))
        rgba[..., 0] = np.clip(f.get('trough_wall', 0 * h), 0, 1)
        rgba[..., 2] = np.clip(f.get('trough_floor', 0 * h), 0, 1)
        rgba[..., 1] = 0.3 * np.clip(f['trough'], 0, 1)
        rgba[..., 3] = 0.45 * np.clip(f['trough'], 0, 1)
        ax.imshow(rgba[::-1], extent=ext_g)
    ax.set_title('trough masks: walls red, floor blue')
    l0 = levels[0]
    ax = fig.add_subplot(gs[0, 3])
    ext0 = [l0['x0'], l0['x0'] + l0['side'], l0['y0'], l0['y0'] + l0['side']]
    ax.imshow(shade(l0['fields']['h'], l0['cell']), cmap='gray', extent=ext0)
    if 'ice' in l0['fields']:
        ice = np.asarray(l0['fields']['ice'], np.float64)
        ov = np.zeros(ice.shape + (4,))
        ov[..., 2] = 1.0
        ov[..., 3] = 0.5 * np.clip(ice / 300.0, 0, 1)
        ax.imshow(ov[::-1], extent=ext0)
    ax.plot([ext_g[0], ext_g[1], ext_g[1], ext_g[0], ext_g[0]], [ext_g[2], ext_g[2], ext_g[3], ext_g[3], ext_g[2]],
            'y-', lw=1)
    ax.set_title(f"coarsest level ({l0['cell']:.3g} m), ice thickness blue")
    ax = fig.add_subplot(gs[0, 4])
    ax.axis('off')
    ax.text(0, 1, '\n'.join(lines), va='top', family='monospace', fontsize=10)
    rs, rl = trunk_sections(ref.h, ref.pixel)
    gsx, gl = trunk_sections(h, cell)
    top = max([z.max() for _, z in rs + gsx] + [100.0])
    for k in range(5):
        ax = fig.add_subplot(gs[1, k])
        if k < len(rs):
            ax.plot(rs[k][0], rs[k][1], color='0.45', lw=1.5, label='reference')
        if k < len(gsx):
            ax.plot(gsx[k][0], gsx[k][1], color='tab:blue', lw=1.5, label='generated')
        ax.set_ylim(0, top * 1.05)
        ax.set_xlim(-3000, 3000)
        ax.set_aspect('equal')
        ax.grid(alpha=0.3)
        ax.set_title(f'section {k + 1} of 5 across the trunk (m, true scale)')
        if k == 0:
            ax.legend(loc='upper left')
    ax = fig.add_subplot(gs[2, 0:3])
    if rl is not None:
        ax.plot(rl[0], rl[1], color='0.45', label=f'reference trunk floor (m)')
    if gl is not None:
        ax.plot(gl[0], gl[1] + base, color='tab:blue', label='generated trunk floor (altitude, m)')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_title('the trunk long profile, from its head')
    ax = fig.add_subplot(gs[2, 3:5])
    for name, hh, px, col in (('reference', ref.h, ref.pixel, '0.45'), ('generated', h, cell, 'tab:blue')):
        s = Gd.slope_deg(hh, px).ravel()
        ax.hist(s, bins=90, range=(0, 90), histtype='step', density=True, color=col, label=name)
    ax.legend()
    ax.set_title('slope histogram (degrees)')
    fig.suptitle(tag, fontsize=16)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def main():
    out_dir, tags = sys.argv[1], sys.argv[2:]
    for tag in tags:
        rec = json.load(open(os.path.join(out_dir, tag + '_record.json'), encoding='utf-8'))
        ref_name = rec.get('reference') or 'lauterbrunnen'
        ref = refs.load(ref_name)
        field = os.path.join(out_dir, tag + '.npz')
        v = judge(field, ref_name, label=tag)
        v.save(os.path.join(out_dir, tag + '_verdict.json'))
        print(v.table(), flush=True)
        lines = [f"verdict vs {ref_name}: {'PASS' if v.passed else 'FAIL'} ({len(v.failures)} failures)"]
        for r in v.rows:
            if r['passed'] is None:
                continue
            g, rr = r['gen'], r['ref']
            num = isinstance(g, (int, float)) and isinstance(rr, (int, float)) and math.isfinite(g)
            lines.append(f"{'PASS' if r['passed'] else 'FAIL'} {r['metric']}: " +
                         (f"{g:.4g} (ref {rr:.4g})" if num else f'{g} (ref {rr})'))
        levels = levels_of(os.path.join(out_dir, tag + '_levels.npz'))
        sm = seams(levels)
        json.dump(sm, open(os.path.join(out_dir, tag + '_seams.json'), 'w'), indent=1)
        lines.append('seams: ' + ', '.join(f"{r['child_cell_m']:.3g} m {r['edge_max_dh_m']:.3f}/"
                                          f"{r['edge_slope_jump_deg']:.1f}" for r in sm))
        lines.append(f"run {rec['seconds']} s")
        print('\n'.join(lines[-2:]))
        print(sheet(tag, out_dir, ref, levels, lines, os.path.join(out_dir, tag + '_sheet.png')))


main()
