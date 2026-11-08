"""eidoverse/examples/robotics/motion.scene.js as a Blender scene script: the assembled humanoid and quadruped running
their circles, the payload drone flying, the tracked arm driving.

    python eido_blender.py render blender/eidoblend/characters/robotics/scenes/motion.json
"""

from eidoblend.characters.robotics.examples import EXAMPLES

# These material-inspection examples supply their own calibrated studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['motion'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration)
