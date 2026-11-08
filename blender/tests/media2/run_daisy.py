"""Run the DAISY example (eidoverse/examples/daisy/) unchanged, with its outputs in this test folder.

    cd <worktree> && python -B blender/tests/media2/run_daisy.py song --upto verse2 --no-tts
    python -B blender/tests/media2/run_daisy.py captions --tag _upto_verse2 [--preview]
    python -B blender/tests/media2/run_daisy.py analyze --tag _upto_verse2

song.py, captions.py and analyze.py keep their outputs under <repo>/work/daisy/; this loads each script as a module,
points its WORK / OUT / CACHE at blender/tests/media2/out/daisy/ and calls its main() with the remaining arguments.
Nothing in the scripts changes. -B keeps __pycache__ folders out of voicebox/ and synthkit/.
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
DAISY = WORKTREE / 'eidoverse' / 'examples' / 'daisy'
WORK = HERE / 'out' / 'daisy'


def load(name):
    spec = importlib.util.spec_from_file_location(f'daisy_{name}', DAISY / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    which = sys.argv[1]
    os.environ.setdefault('NUMBA_CACHE_DIR', str(WORK / 'numba_cache'))
    m = load(which)
    if hasattr(m, 'WORK'):
        m.WORK = WORK
    if hasattr(m, 'CACHE'):
        m.CACHE = WORK / 'cache'
    m.OUT = WORK / 'out'
    m.OUT.mkdir(parents=True, exist_ok=True)
    sys.argv = [f'{which}.py', *sys.argv[2:]]
    m.main()


if __name__ == '__main__':
    main()
