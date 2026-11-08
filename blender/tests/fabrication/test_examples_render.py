"""The relief and mesh_fabrication examples built and rendered (the manufacturing example has test_fabrication_render).

  relief            EXAMPLES['relief']: roughing then finishing the original crest in hardwood, its own framed camera,
                    rendered at 3, 10, 18 and 25 s
  mesh_fabrication  EXAMPLES['mesh_fabrication']: the rotary CNC carving the handle sample (needs the rotary package),
                    keyed and rendered at three frames only (its stock writes one VDB file per keyed frame)

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/fabrication/test_examples_render.py
        [-- --no-render] [-- --only relief|mesh_fabrication]
"""
import os
import shutil
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402

from eidoblend.common import script_args  # noqa: E402
from eidoblend.fabrication.examples import EXAMPLES  # noqa: E402

args = script_args()
RENDER = '--no-render' not in args
ONLY = args[args.index('--only') + 1] if '--only' in args else None


def still(scene, name, frame):
    scene.eevee.taa_render_samples = 16
    scene.render.image_settings.file_format = 'PNG'
    if RENDER:
        U.render_still(scene, os.path.join(U.OUT, name), frame)


if ONLY in (None, 'relief'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    rec = EXAMPLES['relief'](sc, width=960, height=540)
    job = rec['jobs'][0]
    U.check('relief example: built and keyed', sc.frame_end == sc.frame_start + 26 * 24 - 1,
            f"{len(job.program['points'])} points, stages {[s['name'] for s in job.program['stages']]}, "
            f'{job.physical_duration / 60:.1f} min physical in 24 s')
    for t in (3, 10, 18, 25):
        still(sc, f'example_relief_t{t:02d}.png', sc.frame_start + t * 24)

if ONLY in (None, 'mesh_fabrication'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    cache = os.path.join(U.OUT, 'mesh_fabrication_stock_cache')
    shutil.rmtree(cache, ignore_errors=True)
    frames = [1 + 2 * 24, 1 + 14 * 24, 1 + 29 * 24]
    try:
        rec = EXAMPLES['mesh_fabrication'](sc, frames=frames, cache_dir=cache, width=640, height=450)
        rj = rec['jobs'][0]
        U.check('mesh_fabrication example: built through the rotary package', True,
                f"{getattr(rj, 'physical_duration', 0) / 60:.1f} min physical, frames {rec['frames']}")
        for f in frames:
            still(sc, f'example_mesh_fabrication_f{f:03d}.png', f)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        U.check('mesh_fabrication example: built through the rotary package', False, str(e)[:300])
ok = U.summary('examples')
sys.exit(0 if ok else 1)
