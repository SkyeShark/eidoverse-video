"""Test T19, its second half: the era looks' CRT phosphor persistence reads the last few frames back (seven at 24 fps,
era_looks.persist_frames), never its own output, so a --at still renders only those frames before it. The stage:
_ember.py.

    python eido_blender.py render blender/tests/pipeline/leadin/scene_crt.json --at 0.75 --at 1.25
"""
import _ember

render_frame = _ember.render_frame


def setup(ctx):
    _ember.stage(ctx)
    from eidoblend.look.post import custom_effects as FX
    FX.apply_to(ctx.scene, 'era_looks', {'era_looks': {'phosphor': 1.0}})
