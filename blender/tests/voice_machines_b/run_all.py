"""Every voice-machines-b test in one Blender process (one GPU slot for all the stills):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/run_all.py                 # checks
    bash run_blender.sh <this> --render                                                                        # + stills
    ... run_all.py --render --only voder,tandem                                                                 # a subset
    (--render: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

The parity dumps the checks compare against (the WebGPU modules' logic, and three r184's own geometries):
    deno run --no-config --no-lock -A parity_dump.mjs out/parity_js.json
    deno run --no-config --no-lock -A geometry_parity_dump.mjs <main checkout>/node_modules/three/build out/geometry_js.json
"""
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

TESTS = ['test_kit_geometry', 'test_voder', 'test_mainframe', 'test_teletype', 'test_two_teletypes', 'test_speakspell',
         'test_tandem', 'test_dark_room_and_back_views', 'test_museum_reload']


def main():
    render = '--render' in sys.argv
    only = None
    if '--only' in sys.argv:
        only = {f'test_{x}' if not x.startswith('test_') else x for x in sys.argv[sys.argv.index('--only') + 1].split(',')}
    for name in TESTS:
        if only and name not in only:
            continue
        try:
            importlib.import_module(name).run(render=render)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            S.check(f'{name}: ran to the end', False, 'raised (traceback above)')
    n_fail = S.summary('voice_machines_b')
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
