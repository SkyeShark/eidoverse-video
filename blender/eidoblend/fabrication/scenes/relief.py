"""eidoverse/examples/robotics/relief.scene.js as a Blender scene script: a close study of three-axis carving,
roughing then finishing the original flowing crest in hardwood over 24 s.

    python eido_blender.py render blender/eidoblend/fabrication/scenes/relief.json
"""

from eidoblend.fabrication.examples import EXAMPLES

# These material-inspection examples supply their own calibrated studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['relief'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration)
