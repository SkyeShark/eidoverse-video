"""Every render of this test folder in ONE Blender run (one GPU-slot booking): the film-scale heroes, the operator
gallery (grey and shaded), every option arm, and the probes. Generate the CPU caches first (hero_scenes.py,
variant_scenes.py, render_probes.py --generate) so the slot is spent rendering.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \\
        bash run_blender.sh <worktree>/blender/tests/terrain_ekigar/render_all.py [--parts heroes,gallery,variants,probes]
"""
import os
import runpy
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)

from eidoblend.common import script_args  # noqa: E402

args = script_args()
# film-scale shots first, then the per-operator sets: a run cut short still leaves the shots that matter most
parts = args[args.index('--parts') + 1].split(',') if '--parts' in args else ['heroes', 'probes', 'gallery',
                                                                              'variants']
SCRIPTS = {'heroes': 'render_heroes.py', 'gallery': 'render_gallery.py', 'variants': 'render_variants.py',
           'probes': 'render_probes.py'}
argv0 = list(sys.argv)
for part in parts:
    t0 = time.time()
    # each script reads its own arguments after '--': none, so it renders everything it owns
    sys.argv = argv0[:argv0.index('--') + 1] if '--' in argv0 else argv0[:1]
    try:
        runpy.run_path(os.path.join(HERE, SCRIPTS[part]), run_name='__main__')
        print(f'[render_all] {part} done in {time.time() - t0:.0f}s', flush=True)
    except SystemExit:
        print(f'[render_all] {part} exited in {time.time() - t0:.0f}s', flush=True)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print(f'[render_all] {part} FAILED after {time.time() - t0:.0f}s', flush=True)
sys.argv = argv0
