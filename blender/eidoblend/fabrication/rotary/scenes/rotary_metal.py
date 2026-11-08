"""eidoverse/examples/robotics/rotary_metal.scene.js as a Blender scene script: aluminium rotary milling, setup, eight
seconds at physical cutting speed, then a time-lapse finish. Change material to 'brass' for its appearance and rates.

    python eido_blender.py render blender/eidoblend/fabrication/rotary/scenes/rotary_metal.json

The carved stock is a VDB file sequence written beside the build output (rotary_metal_cache/, one file per frame).
"""

import os

from eidoblend.fabrication.rotary.examples import EXAMPLES

# The example supplies its own studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['rotary_metal'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration,
                             log=ctx.log, cache_dir=os.path.join(ctx.out_dir, 'rotary_metal_cache'))
