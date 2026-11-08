"""eidoverse/examples/robotics/mantis.scene.js as a Blender scene script: the maximal shared-kit build, the tracked MANTIS
with its articulated payloads, driving its circle with the camera carried along.

    python eido_blender.py render blender/eidoblend/characters/robotics/scenes/mantis.json
"""

from eidoblend.characters.robotics.examples import EXAMPLES

# These material-inspection examples supply their own calibrated studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['mantis'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration)
