"""The robot-body example: eidoverse/examples/claude_robot.js in the Blender edition, run through the harness.

    python eido_blender.py build  blender/examples/claude_robot/scene.json          # every frame keyed into the .blend
    python eido_blender.py render blender/examples/claude_robot/scene.json --at 2.1 --at 3.85 --at 6.8
    python eido_blender.py render blender/examples/claude_robot/scene.json          # the whole film

The robot body (eidoverse/assets/vrms/claude_robot.vrm) plays the stock idle through its hardware limits for 8 s at
30 fps: the OLED face runs through a blink, happy, a spoken "hello" one vowel at a time, surprised and relaxed, the
eyes look left then right, the head and the crown's petals follow the face, and the camera eases in from the whole
body to the head and shoulders, in the example's own studio (its equirect softboxes, the key and rim lights, the dark
floor disc, the bloom on the face only). eidoblend.characters.robot.example.claude_robot_example() makes all of it,
each frame performed and keyed; this file is the runner's shape around it and nothing more, at the example's own
rate and length (scene.json says the same: 30 fps, 8 s). The body's files are read, never changed.
Guide: tools-guides/robot-body.md.

The example renders 960 x 540 at 16 samples, its look the look family's probe preset (raise both in scene.json for
a final film).
"""
from eidoblend.characters.robot import example


def setup(ctx):
    if (ctx.fps, ctx.duration) != (example.FPS, example.DURATION):
        ctx.record('example_length', 'WARN', f'scene.json asks {ctx.fps} fps for {ctx.duration} s; the example is '
                                             f'{example.FPS} fps for {example.DURATION} s, and plays that')
    example.claude_robot_example(ctx.scene, fps=example.FPS, duration=example.DURATION)
