"""The walking course: eidoverse/examples/obstacle_course.js in the Blender edition, run through the harness.

    python eido_blender.py build  blender/examples/obstacle_course/scene.json          # the run keyed into the .blend
    python eido_blender.py render blender/examples/obstacle_course/scene.json --at 9 --at 25.5 --at 49
    python eido_blender.py render blender/examples/obstacle_course/scene.json          # the whole film

Aporia (the example's character) walks the example's course (eidoblend.course.EXAMPLES['obstacle_course']): the bump,
the 8 degree ramps and the small stairs, the low cover's vault and the 1.15 m wall's mount and drop; the run zone with
its stairs, the gap jump and the chest-high vault; the 2.2 m wall's climb and drop; a sit on the bench; a cheer while
walking; the ladder and its mantle; a salute from the top platform. The character controller
(eidoblend.characters.controller) plays every step and maneuver, keyed frame by frame; the example's follow camera
(5.2 m off, 3.4 m while she maneuvers or sits, swung to a rear three-quarter for the ladder) is keyed with it.
eidoblend.course.template does all of it: this file is the engine's pattern (the example's setup and renderFrame over
the template) and nothing more. Guides: tools-guides/geometry.md (the courses), tools-guides/controller.md.

The engine's scene asked 1280 x 720 for 62 s; the run takes 58 s, and this scene renders 960 x 540 at 16 samples
(raise both in scene.json for a final film). The telemetry of the run (the engine's LOCOMOTION_TELEMETRY) is written
to blender/examples/out/obstacle_course_telemetry.json.
"""
import os

from eidoblend.course import template

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out'))


def setup(ctx):
    template.setup(ctx, example='obstacle_course', character=ctx.assets['character_vrm'],     # scene.json's aporia.vrm
                   telemetry={'enabled': True, 'output_path': os.path.join(OUT, 'obstacle_course_telemetry.json')})


render_frame = template.render_frame
cleanup = template.cleanup
