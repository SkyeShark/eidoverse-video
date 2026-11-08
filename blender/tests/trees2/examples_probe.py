"""The app's two example scenes in Blender (seedthree.scene.examples), rendered.

    bash run_blender.sh blender/tests/trees2/examples_probe.py [species ...]

reference_turntable (scripts/reference: the eidoverse reference turntable) for each
species given (default paperBirch and weepingWillow): its three probe frames, left
three-quarter, front, right three-quarter. example_scene (src/api/example-eidoverse-
scene.js): frames 1 and the last. Checks the framing (the crown fits the frame with
the 12 % margin), the keyed camera path and the scene parts.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.trees import raw  # noqa: E402


def main():
    a = S.args()
    species = [x for x in a if not x.startswith('-')] or ['paperBirch', 'weepingWillow']
    raw()
    from seedthree.scene.examples import reference_turntable, example_scene, REFERENCE_SPECIES
    for sp in species:
        scene = S.reset()
        shot = reference_turntable(species=sp, seed=1, width=640, height=640, samples=16)
        cam = shot['camera']
        S.check('%s reference: one of the reference species' % sp, sp in REFERENCE_SPECIES)
        S.check('%s reference: keyed camera path' % sp, cam.animation_data is not None and cam.animation_data.action is not None)
        angles = []
        for f in shot['probe_frames']:
            scene.frame_set(f)
            c = shot['tree']['stats']['boundingBoxWorld']
            ctr = (Vector(c['min']) + Vector(c['max'])) / 2
            d = cam.matrix_world.translation - ctr
            angles.append(math.degrees(math.atan2(d.x, -d.y)))
            S.render(scene, os.path.join(S.OUT, 'reference_%s_seed1_f%02d.png' % (sp, f)))
        S.check('%s reference: -38 -> +68 degrees around the crown' % sp,
                abs(angles[0] + 38) < 1 and abs(angles[-1] - 68) < 1, ' '.join('%.1f' % x for x in angles))
    scene = S.reset()
    ex = example_scene(width=960, height=540, seconds=8.0, samples=16)
    S.check('example scene: white oak seed 42', ex['tree']['object'].get('seedthree_seed') == 42)
    for f in (1, ex['frames']):
        scene.frame_set(f)
        S.render(scene, os.path.join(S.OUT, 'example_scene_f%03d.png' % f))
    cam = ex['camera']
    scene.frame_set(1)
    p1 = cam.matrix_world.translation.copy()
    scene.frame_set(ex['frames'])
    p2 = cam.matrix_world.translation.copy()
    r1, r2 = Vector((p1.x, p1.y)).length, Vector((p2.x, p2.y)).length
    S.check('example scene: the camera circles at 24 m, 6.5 m up', abs(r1 - 24) < 0.01 and abs(r2 - 24) < 0.01
            and abs(p1.z - 6.5) < 0.01, 'r %.2f / %.2f, z %.2f' % (r1, r2, p1.z))
    S.summary('examples_probe')


main()
