"""The locomotion scene template through the harness: the expanded obstacle course, my robot walked by the
controller port from the template's start over the bumps and the dome toward the first ramp, the template's
three-quarter camera keyed every frame, the telemetry written.

    python eido_blender.py build blender/tests/terrain_extras/course_scene/scene.json      (no render)
    python eido_blender.py render blender/tests/terrain_extras/course_scene/scene.json --at 4.6 --at 7.2 --at 9.5

The scene script is the engine's pattern (a TERRAIN_CONFIG, a camera mode, the template's hooks) in Python.
"""
import os

from eidoblend.course import PRESETS, template

TERRAIN_CONFIG = PRESETS['obstacle_course_expanded']
CAMERA_MODE = 'three_quarter'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out')


def setup(ctx):
    template.setup(ctx, TERRAIN_CONFIG, character='claude_robot', camera_mode=CAMERA_MODE,
                   duration=ctx.duration + 0.5,
                   telemetry={'enabled': True, 'output_path': os.path.join(OUT, 'course_scene_telemetry.json')})


render_frame = template.render_frame
cleanup = template.cleanup
