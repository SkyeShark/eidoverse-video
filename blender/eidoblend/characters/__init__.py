"""eidoblend.characters: VRM characters in Blender 5.2 EEVEE (tools-guides/characters.md describes this edition).

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.characters import load_vrm, load_clip, play_vrma_default, walk_path, key_expression, Ground

    me = load_vrm('claude_robot')                                  # vrm.py: the add-on import, a handle
    play_vrma_default(me, 'still_breathe')                         # vrma.py: a stationary clip as an NLA strip
    rep = walk_path(me, load_clip(me, 'walk'), [(0, 0), (10, 0)],  # locomotion.py: planted feet over uneven ground
                    Ground(obj=terrain), face={'happy': 1.0})
    key_expression(me, 'happy', [(1, 1.0)])                        # expressions.py: shape keys + the add-on's previews

Modules: vrm (load_vrm, VRMHandle), vrma (load_clip, play_vrma, play_vrma_default), expressions (key_expression,
set_expression, scale_visemes), robot_dof (my robot body's joint limits, head and crown), ground (foot_points, Ground,
ground_vrm), locomotion (walk_path, analyze_clip, Body), performance (perform, key_face_track: a stationary clip through a
body's frame order, baked), checks (the audits), clippy (make_clippy: tools-guides/clippy.md), robotics (make_robot:
tools-guides/robotics.md; import it as eidoblend.characters.robotics). Self-contained: nothing here imports another family's
subpackage. Names follow the WebGPU API in snake_case (playVRMADefault -> play_vrma_default, groundVRM -> ground_vrm).
"""

from .expressions import key_expression, scale_visemes, set_expression  # noqa: F401
from .ground import Ground, foot_points, ground_vrm  # noqa: F401
from .locomotion import Body, analyze_clip, walk_path  # noqa: F401
from .performance import key_face_track, perform  # noqa: F401
from .vrm import VRMHandle, load_vrm  # noqa: F401
from .vrma import load_clip, play_vrma, play_vrma_default  # noqa: F401
