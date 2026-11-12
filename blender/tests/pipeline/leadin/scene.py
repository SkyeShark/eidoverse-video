"""Test T19: a --at still of a shot with after_image matches the film's own frame. The trail is the pass's own output
a frame earlier, read back from disk (look/post/after_image.py), so a still renders its shot's frames before it, in
order, keeping only the records (the runner's capture mode). The ball's trail is the test: a still rendered alone
would show the ball with none. The stage: _ember.py.

    python eido_blender.py render blender/tests/pipeline/leadin/scene.json                       # the film
    python eido_blender.py render blender/tests/pipeline/leadin/scene.json --at 0.75 --at 1.25   # two stills
"""
import _ember

render_frame = _ember.render_frame


def setup(ctx):
    _ember.stage(ctx)
    from eidoblend.look.post import custom_effects as FX
    FX.apply_to(ctx.scene, 'after_image', {'after_image': {'damp': 0.9}})
