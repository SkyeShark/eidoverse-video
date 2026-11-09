"""eidoverse/examples/obstacle_course.js through the harness: the course example whole. Its course and bench, its
character (aporia), its follow camera, and the controller directed as its renderFrame directed it: two vaults, the
mount and drop, the run zone and the gap jump, the wall climb and drop, the sit stop on the bench, the cheer gesture
while walking, the ladder and the finale salute (template.CourseScene.direct_example).

    python eido_blender.py build blender/tests/terrain_extras/course_example_scene/scene.json      (no render)
    python eido_blender.py render blender/tests/terrain_extras/course_example_scene/scene.json --at 14 --at 28 --at 47

The engine's scene file asked 1280 x 720 at 30 fps for 62 s; this one renders 960 x 540 for the 58 s the run takes.
The scene script is the engine's pattern (the example's own setup and renderFrame over the template) in Python.
"""
import os

from eidoblend.course import template

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out')


def setup(ctx):
    template.setup(ctx, example='obstacle_course',
                   telemetry={'enabled': True, 'output_path': os.path.join(OUT, 'course_example_scene_telemetry.json')})


render_frame = template.render_frame
cleanup = template.cleanup
