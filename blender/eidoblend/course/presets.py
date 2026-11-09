"""eidoblend.course.presets: the TERRAIN_CONFIGs the engine's locomotion scenes ran, and its course example.

PRESETS: the variant scenes that set a TERRAIN_CONFIG and evaluated the template (the engine's locomotion test
bench: stairs of three sizes, ramps of three angles, the two pyramids, a large-stairs-only course, the expanded
obstacle course and the clouds scenes' course without its dome), under the names their scenes had. Plain data:
build_course(PRESETS['ramp33']).

SCENES: the variant scenes that layered more on a preset (a camera mode, the telemetry, the character, a recolour, a
baked expression; the post effects and controller switches they also set are named in the entry, for those ports).
template.setup(ctx, variant='stairs_handcloseup') runs one.

EXAMPLES['obstacle_course']: eidoverse/examples/obstacle_course.js, the full locomotion vocabulary (walk and run over
ramps, small obstacles, two stair sizes, cover vaults, a mount and drop, a gap jump, a wall climb, a ladder, a sit-down
rest stop and a gesture while walking): its TERRAIN_CONFIG, its scene file's size, rate, duration and character, its
camera, its bench and the course direction its renderFrame scripted, as data (zones by segment index, the sit stop's
route and timing, the emote and gesture names, the ladder trigger, the follow camera's constants).
template.setup(ctx, example='obstacle_course') plays it whole (template.CourseScene.direct_example).
"""

PRESETS = {
    # the template's default (no TERRAIN_CONFIG): a 100-step staircase
    'stairs': {'type': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 100},
    'stairs_small': {'type': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 100},
    'stairs_steep': {'type': 'stairs', 'rise': 0.25, 'run': 0.30, 'num': 60},
    'ramp15': {'type': 'ramp', 'angleDeg': 15, 'horizLen': 28},
    'ramp33': {'type': 'ramp', 'angleDeg': 33, 'horizLen': 28},
    'ramp45': {'type': 'ramp', 'angleDeg': 45, 'horizLen': 18},
    'ramp_pyramid': {'type': 'ramp_pyramid', 'angleDeg': 25, 'horizLen': 8, 'plateauWidth': 2.0},
    'stairs_pyramid': {'type': 'stairs_pyramid', 'rise': 0.18, 'run': 0.28, 'numUp': 20, 'numDown': 20,
                       'plateauWidth': 2.0},
    # a long warmup, six large steps (0.22 x 0.26) up, a plateau, six down, a flat end: large risers alone
    'large_stairs_only': {'type': 'obstacle_course', 'segments': [
        {'kind': 'flat', 'length': 4.0},
        {'kind': 'stairs', 'rise': 0.22, 'run': 0.26, 'num': 6, 'dir': 'up'},
        {'kind': 'flat', 'length': 2.0},
        {'kind': 'stairs', 'rise': 0.22, 'run': 0.26, 'num': 6, 'dir': 'down'},
        {'kind': 'flat', 'length': 3.0},
    ], 'useRealStepIK': True},
    # each phase rises then descends, so the running floor never goes below 0
    'obstacle_course_expanded': {'type': 'obstacle_course', 'segments': [
        {'kind': 'flat', 'length': 2.0},
        {'kind': 'flat', 'length': 0.6},
        {'kind': 'bump', 'height': 0.06, 'depth': 0.30},
        {'kind': 'flat', 'length': 0.6},
        {'kind': 'bump', 'height': 0.10, 'depth': 0.30},
        {'kind': 'flat', 'length': 0.6},
        {'kind': 'bump', 'height': 0.15, 'depth': 0.30},
        {'kind': 'flat', 'length': 1.0},
        {'kind': 'dome', 'radius': 0.35},
        {'kind': 'flat', 'length': 1.0},
        {'kind': 'ramp', 'angleDeg': 8, 'horizLen': 2.0, 'dir': 'up'},
        {'kind': 'flat', 'length': 1.0},
        {'kind': 'ramp', 'angleDeg': 8, 'horizLen': 2.0, 'dir': 'down'},
        {'kind': 'flat', 'length': 1.5},
        {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 6, 'dir': 'up'},
        {'kind': 'flat', 'length': 1.2},
        {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 6, 'dir': 'down'},
        {'kind': 'flat', 'length': 1.5},
        {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 4, 'dir': 'up'},
        {'kind': 'flat', 'length': 1.2},
        {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 4, 'dir': 'down'},
        {'kind': 'flat', 'length': 1.5},
        {'kind': 'ramp', 'angleDeg': 22, 'horizLen': 1.5, 'dir': 'up'},
        {'kind': 'flat', 'length': 1.2},
        {'kind': 'ramp', 'angleDeg': 25, 'horizLen': 1.3, 'dir': 'down'},
        {'kind': 'flat', 'length': 1.5},
        {'kind': 'stairs', 'rise': 0.22, 'run': 0.26, 'num': 3, 'dir': 'up'},
        {'kind': 'flat', 'length': 1.2},
        {'kind': 'stairs', 'rise': 0.22, 'run': 0.26, 'num': 3, 'dir': 'down'},
        {'kind': 'flat', 'length': 3.0},
    ], 'useRealStepIK': True},
}

# the clouds scenes' course: the expanded course without its dome (and the flat after it)
PRESETS['obstacle_course_claude_clouds'] = {
    'type': 'obstacle_course',
    'segments': [s for i, s in enumerate(PRESETS['obstacle_course_expanded']['segments']) if i not in (8, 9)],
    'useRealStepIK': True}

# the variant scenes: a preset plus what their scripts set on top of the template (camera mode, telemetry, the
# character, a recolour, a baked expression, the noik scene's foot IK switched off). template.setup(ctx,
# variant='stairs_claude_clouds') runs one. The clouds scenes' volumetric clouds and shafts post effect came from the
# POC scenes' effects library and is not ported (named in the entry). useRealStepIK rides along in the configs as the
# scenes set it: nothing in the engine reads it.
_CLOUDS_LOOK = {'obstacle': {'color': 0x4ab8c0}, 'ground': {'color': 0x183848, 'metalness': 0.8, 'roughness': 0.35}}
SCENES = {
    'stairs_handcloseup': {'config': PRESETS['stairs_pyramid'], 'camera_mode': 'hands_closeup'},
    'stairs_claude_clouds': {'config': PRESETS['stairs_pyramid'], 'camera_mode': 'three_quarter',
                             'character': 'claude', 'materials': _CLOUDS_LOOK,
                             'expressions': {'catface': 1.0, 'lookHappy': 1.0, 'raised': 1.0},
                             'post': 'volumetric_clouds'},
    'stairs_claude_clouds_runtime': {'config': PRESETS['stairs_pyramid'], 'camera_mode': 'three_quarter',
                                     'character': 'claude', 'materials': _CLOUDS_LOOK,
                                     'expressions': {'catface': 1.0, 'lookHappy': 1.0, 'raised': 1.0},
                                     'post': 'volumetric_clouds', 'duration': 6.0},
    'obstacle_course_claude_clouds': {'config': PRESETS['obstacle_course_claude_clouds'],
                                      'camera_mode': 'three_quarter', 'character': 'claude',
                                      'materials': _CLOUDS_LOOK, 'post': 'volumetric_clouds'},
    'stairs_pyramid_realstep': {'config': dict(PRESETS['stairs_pyramid'], useRealStepIK=True)},
    'stairs_pyramid_noik': {'config': dict(PRESETS['stairs_pyramid'], useRealStepIK=True), 'foot_ik': False},
    'obstacle_course_telemetry': {'config': PRESETS['obstacle_course_expanded'],
                                  'telemetry': {'enabled': True, 'sample_every': 1, 'include_frames': True}},
}

_COURSE_SEGMENTS = [
    {'kind': 'flat', 'length': 2.2},                                    # 0  walk start
    {'kind': 'bump', 'height': 0.10, 'depth': 0.30},                    # 1  small obstacle step-over
    {'kind': 'flat', 'length': 1.2},                                    # 2
    {'kind': 'ramp', 'angleDeg': 8, 'horizLen': 2.0, 'dir': 'up'},      # 3  ramp up
    {'kind': 'flat', 'length': 1.0},                                    # 4
    {'kind': 'ramp', 'angleDeg': 8, 'horizLen': 2.0, 'dir': 'down'},    # 5  ramp down
    {'kind': 'flat', 'length': 1.2},                                    # 6
    {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 5, 'dir': 'up'},     # 7  small stairs up
    {'kind': 'flat', 'length': 1.0},                                    # 8
    {'kind': 'stairs', 'rise': 0.10, 'run': 0.30, 'num': 5, 'dir': 'down'},   # 9  small stairs down
    {'kind': 'flat', 'length': 1.4},                                    # 10
    {'kind': 'wall', 'height': 0.55, 'depth': 0.30},                    # 11 walk VAULT (low cover)
    {'kind': 'flat', 'length': 1.8},                                    # 12
    {'kind': 'wall', 'height': 1.15, 'depth': 1.90},                    # 13 MOUNT + top walk + drop -> fall-land
    {'kind': 'flat', 'length': 2.0},                                    # 14 recovery
    {'kind': 'flat', 'length': 1.8},                                    # 15 <- RUN starts here
    {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 5, 'dir': 'up'},     # 16 stairs run up
    {'kind': 'flat', 'length': 1.4},                                    # 17 raised slab
    {'kind': 'gap', 'length': 1.1},                                     # 18 run GAP JUMP
    {'kind': 'flat', 'length': 1.6},                                    # 19 raised slab
    {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 5, 'dir': 'down'},   # 20 stairs run down
    {'kind': 'flat', 'length': 1.6},                                    # 21
    {'kind': 'wall', 'height': 0.85, 'depth': 0.35},                    # 22 run VAULT (chest cover)
    {'kind': 'flat', 'length': 2.2},                                    # 23 <- RUN ends at the end of this
    {'kind': 'wall', 'height': 2.20, 'depth': 2.40},                    # 24 CLIMB WALL (hang to mantle) + drop
    {'kind': 'flat', 'length': 1.6},                                    # 25 recovery walk
    {'kind': 'flat', 'length': 1.6},                                    # 26 SIT STOP: bench at the middle
    {'kind': 'flat', 'length': 1.9},                                    # 27 GESTURE while walking
    {'kind': 'ladder', 'height': 2.5, 'depth': 0.5},                    # 28 LADDER (explicit climbLadder)
    {'kind': 'flat', 'length': 2.4},                                    # 29 finale platform -> salute
]

EXAMPLES = {
    'obstacle_course': {
        'config': {'type': 'obstacle_course', 'segments': _COURSE_SEGMENTS},
        # its scene file (obstacle_course.json): 1280 x 720, 30 fps, 62 s, the character aporia.vrm
        'size': (1280, 720), 'fps': 30, 'duration': 62.0, 'character': 'aporia',
        # the CAMERA_MODE global it set (terrain_base's camera); its own renderFrame drew through the follow camera
        'camera_mode': 'three_quarter', 'render_camera': 'follow',
        # the course direction its renderFrame scripted, by segment index
        'zones': {'run': (15, 23), 'sit': 26, 'gesture': 27, 'ladder': 28, 'finale': 29},
        # the bench: a solid 1.1 x 0.45 x 0.5 m box (three's x, y, z) in the sit segment's middle, colour 0x7a5a3a
        'bench': {'segment': 26, 'size': (1.1, 0.45, 0.5), 'color': 0x7a5a3a, 'roughness': 0.8},
        # the walk-around before sitting: waypoints (three x, z offset from the bench's z) that route past the
        # bench's side and rejoin the line just beyond it, then a square-up and stand_to_sit back onto the pan
        'sit_route': [(0.92, 0.95), (0.88, -0.05), (0.0, -0.46)],
        'sit_timing': {'settle': 0.45, 'sit_down': 2.9, 'hold': 2.2, 'stand_up': 2.3, 'reverse_speed': 1.25},
        'gesture': {'name': 'cheer', 'weight': 2.75, 'stop_before_end': 0.9},
        'ladder': {'trigger': 0.55, 'height': 2.5},
        # the salute 0.7 s after she stops, toward the camera; the film holds 1 s after it
        'finale': {'emote': 'salute', 'delay': 0.7, 'fade_in': 0.35, 'hold': 1.0},
        # its follow camera: a full side view (radius 5.2 m, 3.4 m while maneuvering or sitting, damped at 2.5) that
        # swings to a rear three-quarter (46 degrees, damped at 1.8) from 2.2 m before the ladder
        'camera': {'radius': 5.2, 'radius_close': 3.4, 'radius_damp': 2.5, 'ladder_angle_deg': 46.0,
                   'angle_damp': 1.8, 'ladder_lead': 2.2, 'height': 0.45, 'height_per_radius': 0.07,
                   'look_drop': 0.30},
    },
}
