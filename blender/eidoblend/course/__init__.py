"""eidoblend.course: the locomotion course template (eidoverse/terrain_base.js) and three-bvh-csg's booleans.

    from eidoblend.course import build_course, course_stage, PRESETS, EXAMPLES, template, csg
    course = build_course(PRESETS['stairs_pyramid'])              # walkable steps, ramps, slabs, walls, gaps, ladders
    course_stage(bpy.context.scene, course)                        # the template's sun, ambient, backdrop, camera
    template.setup(ctx, PRESETS['ramp15'], camera_mode='three_quarter')   # + a VRM walking it, keyed

Modules: plan (the engine's course maths in three's axes, plain Python: plan_course, segment_at), builder
(build_course, Course, add_bench, add_rigid_bodies, merge_solids, engine_material), stage (course_stage,
course_world, course_sun, course_camera), template (the scene hooks: setup / render_frame / cleanup, CourseScene,
camera_pose), presets (PRESETS, EXAMPLES), csg (evaluate, Evaluator, compute_mesh_volume, union_all and the seven
operations, HOLLOW_SUBTRACTION and HOLLOW_INTERSECTION among them). Guide: tools-guides/geometry.md.
"""
from . import csg, plan, presets, template  # noqa: F401
from .builder import Course, add_bench, add_rigid_bodies, build_course, engine_material, merge_solids  # noqa: F401
from .plan import plan_course, segment_at  # noqa: F401
from .presets import EXAMPLES, PRESETS, SCENES  # noqa: F401
from .stage import course_camera, course_stage, course_sun, course_world  # noqa: F401

__all__ = ['build_course', 'Course', 'add_bench', 'add_rigid_bodies', 'merge_solids', 'engine_material',
           'plan_course', 'segment_at', 'PRESETS', 'EXAMPLES', 'SCENES', 'course_stage', 'course_world', 'course_sun',
           'course_camera', 'template', 'csg', 'plan', 'presets']
