"""The surface data's cost against the design's budget (SURFACING_DESIGN.md 5.4, package 1, item 5; section 7), from
what bake_cases.py and gpu_suite.py recorded:

    python blender/tests/terrain/surface_data/cost.py

Per case: the cold bake per level (s per 1024^2 cells: budget 15 s) and in all (budget 90 s for a seven-level film
terrain), its three largest parts, the cache hit, the palette bake (C and P: budget 30 s), the atlas files made, a
cache hit with its images loaded from the files (budget 10 s), and the disk the case's cache folder holds (budget
1.2 GB per terrain). The numbers are recorded, not enforced: on a shared machine they say as much about the other
jobs as about the bake. Writes out/surface_data/cost.json and prints a table.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cases as C  # noqa: E402

BUDGET = dict(per_1024_s=15.0, film_cold_s=90.0, hit_with_images_s=10.0, palette_s=30.0, atlas_files_s=60.0,
              disk_gb=1.2)


def _disk(folder):
    if not os.path.isdir(folder):
        return None
    return sum(os.path.getsize(os.path.join(folder, f)) for f in os.listdir(folder)
               if os.path.isfile(os.path.join(folder, f)))


def main():
    rows = {}
    for p in sorted(glob.glob(os.path.join(C.OUT, 'bake_*.json'))):
        name = os.path.basename(p)[len('bake_'):-len('.json')]
        if name not in C.CASES:
            continue
        d = json.load(open(p, encoding='utf-8'))
        cold = d['runs'][0]
        lv = cold.get('levels') or []
        cells = []
        for spec, tm in zip(d['levels'], lv):
            n = int(spec.split(' x')[1].split(',')[0])
            parts = {k: v for k, v in tm.items() if k != 'total' and isinstance(v, (int, float)) and
                     not k.endswith(('passes', 'iterations'))}
            top = sorted(parts.items(), key=lambda kv: -kv[1])[:3]
            cells.append(dict(n=n, total=tm.get('total'), per_1024=round(tm.get('total', 0) * (1024.0 / n) ** 2, 2),
                              top=[(k, round(v, 2)) for k, v in top]))
        disk = _disk(os.path.join(C.OUT, 'cache', name))
        rec = dict(levels=len(lv), cold_s=cold.get('bake'), cold_with_save_s=cold.get('seconds'),
                   hit_s=d['runs'][-1]['seconds'], per_level=cells,
                   disk_gb=None if disk is None else round(disk / 1e9, 3))
        pb = cold.get('palette')
        if isinstance(pb, dict):                          # bake_cases.py --palette: the palette bake, cold
            rec.update(palette_s=pb.get('seconds'), palette_C_s=pb.get('C_seconds'), palette_P=pb.get('P'),
                       palette_P_s=pb.get('P_seconds'))
        pp = os.path.join(C.OUT, f'palette_{name}.json')
        if os.path.exists(pp):
            q = json.load(open(pp, encoding='utf-8'))
            if 'palette_s' not in rec:
                rec['palette_s'] = q.get('bake_seconds')
            rec.update(images_s=q.get('images_seconds'), hit_with_images_s=q.get('hit_with_images_seconds'),
                       memory_mb=round(sum((q.get('memory_mb') or {}).values()), 1) if q.get('memory_mb') else None)
        rows[name] = rec
    with open(os.path.join(C.OUT, 'cost.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(budget=BUDGET, cases=rows), f, indent=1)
    print(f"{'case':18s} {'levels':>6s} {'cold s':>8s} {'max/1024^2':>10s} {'hit s':>6s} {'palette s':>9s} "
          f"{'images s':>8s} {'hit+img s':>9s} {'MB':>6s} {'disk GB':>7s}")
    for name, r in rows.items():
        mx = max((c['per_1024'] for c in r['per_level']), default=0)
        print(f"{name:18s} {r['levels']:6d} {r['cold_s'] or 0:8.1f} {mx:10.1f} {r['hit_s']:6.1f} "
              f"{r.get('palette_s') or 0:9.1f} {r.get('images_s') or 0:8.1f} {r.get('hit_with_images_s') or 0:9.1f} "
              f"{r.get('memory_mb') or 0:6.0f} {r.get('disk_gb') or 0:7.2f}")
    for name, r in rows.items():
        worst = max(r['per_level'], key=lambda c: c['total'] or 0, default=None)
        if worst:
            print(f"  {name}: slowest level {worst['total']:.1f} s ({worst['n']}^2), its largest parts {worst['top']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
