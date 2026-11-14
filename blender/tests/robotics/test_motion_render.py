"""The kit's motion samples, rendered: every clip on the robots that carry it (walk, the three runs, grasp, drive,
drive-circle, stock-setup, flight, fold, rotors, filament-feed, and 'joints' on every family whose joints sample moves
something different), keyed with play() over a short range and rendered at one to three times each, in the kit's
studio. Checks: play() keyed the clip (moving objects, LINEAR keys) and every still was written.

The dispenser's 'filament-feed' drives the live filament, which the fabrication port installs at load (its
kit_installer in INSTALLERS): a dispenser's load imports the port itself, as the WebGPU loader always runs
installFilament; the import below only reports early when the port is missing.

    out/motion/<robot>_<clip>_t<seconds>.png      480 x 270
    out/motion_render.json

    bash run_blender.sh blender/tests/robotics/test_motion_render.py [-- ids...]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters.robotics import frame_camera, make_robot, studio  # noqa: E402
from eidoblend.characters.robotics.studio import make_camera, world_box  # noqa: E402

OUT = os.path.join(K.OUT, 'motion')
os.makedirs(OUT, exist_ok=True)
FPS = 24
# (robot, clip, seconds to render, camera direction in Blender axes or None for the inspector's)
CASES = [
    ('humanoid', 'walk', (2.0, 6.0), None), ('humanoid', 'run-circle', (1.0, 3.0), None),
    ('humanoid', 'grasp', (0.5, 3.0), 'hand'), ('quadruped', 'run-straight', (0.6, 1.4), None),
    ('quadruped', 'walk', (2.0,), None), ('mantis', 'drive-circle', (0.0, 6.0), None),
    ('rover', 'drive', (2.0, 6.0), None), ('drone', 'flight', (4.5, 7.0), None), ('drone', 'fold', (3.0, 6.0), None),
    ('payloads/arm_hand', 'joints', (2.0, 6.0), None), ('payloads/drone_hand', 'grasp', (3.0,), None),
    ('scara', 'joints', (2.0, 7.0), None), ('fdm', 'joints', (3.0,), None), ('cnc_rotary', 'stock-setup', (2.0, 8.0), None),
    ('arm', 'joints', (1.0, 5.0), None),
    # the rest of the clips, and 'joints' on the families whose joints sample moves its own modules
    ('humanoid', 'run-figure_eight', (2.0, 5.0), None), ('humanoid', 'run-straight', (0.8,), None),
    ('quadruped', 'run-circle', (1.5,), None), ('quadruped', 'run-figure_eight', (2.5,), None),
    ('drone', 'rotors', (0.0, 0.1), 'rotor'), ('platforms/survey', 'flight', (4.5,), None),
    ('payloads/drone_clamp', 'fold', (6.0,), None), ('mantis', 'grasp', (3.0,), None), ('mantis', 'drive', (4.0,), None),
    ('mantis', 'joints', (3.0,), None), ('camera', 'joints', (3.0, 9.0), None), ('face', 'joints', (3.0, 9.0), None),
    ('interaction/antenna', 'joints', (6.0,), None), ('linear', 'joints', (3.0, 9.0), None),
    ('rotary', 'joints', (3.0,), None), ('gripper', 'joints', (1.0, 6.0), None), ('hand', 'grasp', (1.5, 3.0), None),
    ('humanoid_modules/pelvis', 'joints', (3.0,), None), ('humanoid_modules/left_leg', 'joints', (6.0,), None),
    ('payloads/arm_clamp', 'joints', (3.0,), None), ('payloads/rover_arm', 'drive', (4.0,), None),
    ('mobility/tracks', 'drive', (4.0,), None), ('cnc', 'joints', (3.0,), None), ('cnc_relief', 'joints', (6.0,), None),
    ('gantry', 'joints', (3.0,), None), ('rotary_fixture', 'stock-setup', (3.0,), None),
    ('filament_spool', 'filament-feed', (0.0, 8.0), 'reel'),
]
ONLY = [a for a in K.argv() if not a.startswith('--')]
try:                                              # the live filament (filament-feed): the fabrication port's installer
    import eidoblend.fabrication  # noqa: E402,F401
    FABRICATION = True
except Exception:  # noqa: BLE001
    FABRICATION = False
    traceback.print_exc()


def sweep_box(r, clip, times):
    boxes = []
    for t in list(times) + [0.0]:
        r.sample(clip, t)
        boxes.append(world_box([r.group]))
    return boxes


def main():
    sc = K.clean_scene(FPS)
    K.probe_render(sc, (480, 270), 12)
    studio(sc)
    cam = make_camera(35, 'motion camera', sc)
    sc.camera = cam
    rec = {}
    for rid, clip, times, view in CASES:
        if ONLY and rid not in ONLY:
            continue
        try:
            r = make_robot(rid, scene=sc)
            if clip not in r.clips:
                K.check(f'{rid}: has the {clip} sample', False, f'{r.clips}')
                r.dispose()
                continue
            last = int(max(times) * FPS) + 2
            sc.frame_start, sc.frame_end = 1, last
            if view in ('hand', 'rotor', 'reel'):
                key = {'hand': 'hand_base', 'rotor': 'air_rotor_0', 'reel': 'filament_reel'}[view]
                node = r.roots[[n for n in r.roots if n.endswith(key)][0]]
                r.sample(clip, max(times))
                bpy.context.view_layer.update()
                direction = {'hand': (0.6, -1.2, 0.5), 'rotor': (0.5, -0.9, 1.3), 'reel': (-0.9, -1.5, 0.55)}[view]
                frame_camera(cam, [node], direction=direction, margin={'hand': 1.3, 'rotor': 1.6, 'reel': 1.8}[view])
            else:
                frame_camera(cam, sweep_box(r, clip, times), direction=(0.9, -1.5, 0.55), margin=1.1)
            p = r.play(clip, frame_start=1, frame_end=last, scene=sc)
            K.check(f'{rid} {clip}: play() keyed {len(p["objects"])} moving objects over frames 1..{last}',
                    len(p['objects']) > 0)
            for t in times:
                f = 1 + int(round(t * FPS))
                path = os.path.join(OUT, f"{K.safe(rid)}_{clip}_t{t:g}.png")
                K.check(f'{rid} {clip} t={t:g}: still', K.still(sc, cam, f, path))
            rec[f'{rid}|{clip}'] = {'keyed': len(p['objects']), 'times': list(times)}
            r.dispose()
        except Exception:  # noqa: BLE001
            K.check(f'{rid} {clip}', False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('motion_render', {'cases': rec})


main()
