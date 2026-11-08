"""eidoverse/examples/robotics/manufacturing.scene.js as a Blender scene script: the G430 FDM, CNC and relief CNC side
by side, an 18 s process time-lapse.

    python eido_blender.py render blender/eidoblend/fabrication/scenes/manufacturing.json
"""

from eidoblend.fabrication.examples import EXAMPLES

# These material-inspection examples supply their own calibrated studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['manufacturing'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration)
