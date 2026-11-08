"""Test T15: a scene built from a plan file it reads itself, never declared under "assets" (as my films build from
plans). An edit to the plan must rebuild the scene: the build records every file the script reads through Python
as one of its inputs. run_tests.py writes the plan (out/plan_stale.json), builds, builds again (reused), edits the
plan and builds a third time (rebuilt, from the new plan).
"""
import json
import os

import bpy


def setup(ctx):
    path = os.path.join(ctx.out_dir, 'plan_stale.json')
    if not os.path.exists(path):
        raise FileNotFoundError(f'{path}: run this through run_tests.py T15, which writes the plan')
    with open(path, encoding='utf-8') as f:
        plan = json.load(f)
    bpy.ops.mesh.primitive_cube_add(size=plan['cube_size'], location=(0, 0, plan['cube_size'] / 2))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.location = (0, -9, 2.5)
    cam.rotation_euler = (1.36, 0, 0)
    ctx.scene.collection.objects.link(cam)
    ctx.scene.camera = cam
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    ctx.scene.collection.objects.link(sun)
    ctx.record('plan', 'PASS', f"built from plan_stale.json: cube_size {plan['cube_size']}")
