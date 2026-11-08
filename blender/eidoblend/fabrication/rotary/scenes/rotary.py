"""eidoverse/examples/robotics/rotary.scene.js as a Blender scene script: an indexed rotary carving study in hardwood
on the cnc_rotary machine. Change the radius function (sample_rotary) to design the shape.

    python eido_blender.py render blender/eidoblend/fabrication/rotary/scenes/rotary.json

The carved stock is a VDB file sequence written beside the build output (rotary_stock_cache/, one file per frame).
"""

import os

from eidoblend.fabrication.rotary.examples import EXAMPLES

# The example supplies its own studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['rotary'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration,
                       cache_dir=os.path.join(ctx.out_dir, 'rotary_stock_cache'))
