"""Design section 3, checked: Ekigar's port and the old noise make_terrain are gone, the parts that moved are in the
new package, the tools for built geometry are kept, and nothing in the toolkit, its guides or the tests still reaches
for what was deleted. Plain Python (no Blender):

    python blender/tests/terrain/integration/test_deletions.py

Prints PASS / FAIL per check; exit code 1 on a failure.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(TN, '..', '..', '..'))
TERRAIN = os.path.join(ROOT, 'blender', 'eidoblend', 'terrain')

GONE = ['blender/eidoblend/terrain/ekigar', 'blender/eidoblend/terrain/heightfield.py',
        'blender/eidoblend/terrain/_noise.py', 'blender/tests/terrain_ekigar', 'blender/tests/terrain_new',
        'blender/tests/terrain/test_parity.py', 'blender/tests/terrain/parity_dump.mjs',
        'blender/tests/terrain/test_meadow.py', 'blender/tests/terrain/shimmer_metric.py',
        'tools-guides/_drafts/terrain-ekigar-core.md']

# what moved, and the name that shows it arrived (design section 3's "move" rows)
MOVED = [('core/world_noise.py', ('def hash2', 'def lattice_noise', 'def snap_freq')),
         ('solvers/hydro.py', ('def fill_depressions', 'def route', 'def accumulate')),
         ('masks.py', ("'height'", "'aspect'", "'peaks'", "'occlusion'")),
         ('build/mesh.py', ('def height_at',)),
         ('build/water.py', ('def lake_geometry', 'def lake_objects')),
         ('solvers/impact.py', ('def impact_crater', 'def op_impact_crater')),
         ('solvers/detail.py', ('def op_planation', 'def phacelle_noise')),
         ('core/io.py', ('def export_heightmap', 'def read_heightmap', 'png16', 'r32')),
         ('build/surfacing.py', ('def pack_set', "detile_patch", "'Auto'"))]
KEPT = ['surface_layers.py', 'relief.py', 'loft.py', '_pbr.py', '_nodes.py']
MOVED_TESTS = ['blender/tests/terrain/surfacing/shimmer_metric.py', 'blender/tests/terrain/surfacing/test_shimmer.py']

# a reference to deleted code: an import of it, or a path into it
DEAD = re.compile(r'terrain[./]ekigar|from \.ekigar|import ekigar|terrain[./]heightfield|from \.heightfield|'
                  r'import heightfield|terrain[./]_noise\b|terrain_new|terrain_ekigar|_ekigar_load|'
                  r'_drafts/terrain-ekigar|terrain/parity_dump\.mjs|test_meadow\.py|terrain/test_parity\.py')
# inside the terrain package, its own relative imports of the deleted modules
DEAD_IN_TERRAIN = re.compile(r'from \.+_noise import|from \.+ import .*\b_noise\b|from \.+heightfield|'
                             r'import _noise\b')
SCAN = ['blender/eidoblend', 'blender/tests', 'blender/examples', 'tools-guides', 'docs', 'AGENTS.md', 'README.md',
        'blender/README.md', 'eido_blender.py']
# records of how the design was made (the triage of Ekigar's port and the research), the design itself, and the
# outputs: they describe the deleted code by name on purpose
RECORDS = ('blender/tests/terrain/triage/', 'blender/tests/terrain/research/', 'blender/tests/terrain/DESIGN.md',
           'blender/tests/terrain/integration/test_deletions.py', '/out/', '/__pycache__/')
TEXT = ('.py', '.md', '.json', '.mjs', '.js', '.glsl', '.sh', '.txt', '.yaml', '.toml')

fails = []


def check(name, ok, detail=''):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f': {detail}' if detail else ''), flush=True)
    if not ok:
        fails.append(name)


def main():
    still = [p for p in GONE if os.path.exists(os.path.join(ROOT, p))]
    check('deleted: Ekigar\'s port, the old noise make_terrain, their tests and draft guide', not still,
          ', '.join(still) if still else f'{len(GONE)} paths gone')
    for rel, names in MOVED:
        p = os.path.join(TERRAIN, rel)
        src = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
        missing = [n for n in names if n.lower() not in src.lower()]
        check(f'moved into terrain/{rel}', src and not missing,
              f'missing {missing}' if missing else ', '.join(n.replace('def ', '') for n in names))
    gone = [k for k in KEPT if not os.path.exists(os.path.join(TERRAIN, k))]
    check('kept: the tools for built geometry', not gone, ', '.join(gone) if gone else ', '.join(KEPT))
    lost = [p for p in MOVED_TESTS if not os.path.exists(os.path.join(ROOT, p))]
    check('moved: the shimmer probe and its metric into tests/terrain/surfacing', not lost, ', '.join(lost))
    hits = []
    for top in SCAN:
        base = os.path.join(ROOT, top)
        files = [base] if os.path.isfile(base) else [os.path.join(dp, f) for dp, dn, fn in os.walk(base) for f in fn]
        for f in files:
            rel = os.path.relpath(f, ROOT).replace(os.sep, '/')
            if not f.endswith(TEXT) or any(r in '/' + rel for r in RECORDS):
                continue
            try:
                text = open(f, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            in_terrain = rel.startswith('blender/eidoblend/terrain/')
            for i, line in enumerate(text.splitlines(), 1):
                if DEAD.search(line) or (in_terrain and DEAD_IN_TERRAIN.search(line)):
                    hits.append(f'{rel}:{i}: {line.strip()[:120]}')
    check('nothing in the toolkit, guides, docs or tests reaches for the deleted code', not hits,
          ('; '.join(hits[:6]) + (f' (+{len(hits) - 6} more)' if len(hits) > 6 else '')) if hits else
          f"scanned {', '.join(SCAN)}")
    print(f'{len(fails)} FAIL' if fails else 'all PASS', flush=True)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
