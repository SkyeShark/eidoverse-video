"""eidoverse/examples/robotics/assembly.scene.js as a Blender scene script: a new assembly made through interface
frames, with shared assets (the backbone, the stereo camera and the pan/tilt face playing their 'joints' samples).

    python eido_blender.py render blender/eidoblend/characters/robotics/scenes/assembly.json
"""

from eidoblend.characters.robotics.examples import EXAMPLES

# These material-inspection examples supply their own calibrated studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['assembly'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration)
