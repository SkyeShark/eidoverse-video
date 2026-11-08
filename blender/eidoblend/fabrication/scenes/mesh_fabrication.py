"""eidoverse/examples/robotics/mesh_fabrication.scene.js as a Blender scene script: the stock-rotating CNC carving an
ordinary object (the handle sample) in wood. Needs eidoblend.fabrication.rotary (the rotary machine's own package).

    python eido_blender.py render blender/eidoblend/fabrication/scenes/mesh_fabrication.json
"""

from eidoblend.fabrication.examples import EXAMPLES

# These material-inspection examples supply their own calibrated studio lighting.
_no_auto_enhance = True


def setup(ctx):
    EXAMPLES['mesh_fabrication'](ctx.scene, width=ctx.width, height=ctx.height, fps=ctx.fps, duration=ctx.duration)
