"""run_scene.py <job.json>: the script eido_blender.py runs inside headless Blender (through run_blender.sh).

    bash run_blender.sh blender/eidoblend/harness/run_scene.py <job.json>

Bytecode stays off, so the package writes no __pycache__ into the repository. Blender's exit code is the run's own:
0 rendered, 1 failed, 3 refused (a hand-edited .blend), 2 bad arguments.
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))

from eidoblend import common  # noqa: E402
from eidoblend.harness import runner  # noqa: E402

sys.exit(runner.main(common.script_args()))
