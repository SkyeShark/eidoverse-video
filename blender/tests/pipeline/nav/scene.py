"""Test T11: the navigation stack (sensors -> memory -> planner) finds its way through a room it has never seen.

A head 1.5 m up starts at (0, -4) facing +Y; the goal (0.5, 4.5) is behind a wall with a 1.2 m gap and two crates.
It senses (looking 20 degrees down: pitch +0.35, positive looks down as in robot_sensors.js), plans optimistically
(unknown is walkable), steps 0.5 m along the plan, senses again and replans when the new map blocks the old route,
until it arrives. The overlay shows what it learned (green free, red blocked) and the route it took (blue). The
scene records, against the TRUE geometry, that every point of the walk keeps the agent's full radius clear of
every obstacle (scene.nav_clearance), that it arrives (scene.nav_arrived), and that a positive pitch looks down
(scene.nav_pitch).
"""
import math

import bpy
from mathutils import Vector

from eidoblend.harness import navigation as nav

RADIUS = 0.35


def box(name, size, center, colour):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*colour, 1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
    ob.data.materials.append(m)
    return ob


def setup(ctx):
    scene = ctx.scene
    box('floor', (12, 12, 0.1), (0, 0, -0.05), (0.55, 0.55, 0.52))
    obstacles = [box('wall_left', (4.4, 0.3, 1.4), (-2.8, 1.0, 0.7), (0.75, 0.72, 0.66)),
                 box('wall_right', (4.4, 0.3, 1.4), (2.8, 1.0, 0.7), (0.75, 0.72, 0.66)),
                 box('crate_a', (0.8, 0.8, 0.7), (0.1, -1.6, 0.35), (0.45, 0.3, 0.16)),
                 box('crate_b', (0.9, 0.9, 0.9), (0.9, 3.0, 0.45), (0.45, 0.3, 0.16))]
    bpy.context.view_layer.update()

    sensors = nav.RobotSensors(scene, h_fov=110, v_fov=70, range=6, h_rays=24, v_rays=16)
    memory = nav.RobotMemory(size=14, cell_size=0.1)
    planner = nav.RobotPlanner(agent_radius=RADIUS, optimistic=True)
    look = sensors.sense((0.0, -4.0, 1.5), -math.pi / 2, 0.35)        # facing -X; the JS sign: +0.35 rad looks down
    centre = min(look['hits'], key=lambda h: abs(h['ray_yaw']) + abs(h['ray_pitch']))
    ctx.record('nav_pitch', 'PASS' if centre['dir'].z < -0.3 and centre['hit'] and centre['point'].z < 0.01 else 'WARN',
               f"sense(head, -pi/2, +0.35): the cone's centre ray points {centre['dir'].z:+.2f} in z and lands at "
               f"z {centre['point'].z:.2f} m, {centre['distance']:.2f} m away (down, on the floor, as the JS)")
    pos, goal = Vector((0.0, -4.0)), Vector((0.5, 4.5))
    walked = [pos.copy()]
    replans = 0
    path = None
    for step in range(60):
        target = Vector((path[1]['x'], path[1]['y'])) if path and len(path) > 1 else goal
        heading = math.atan2(target.x - pos.x, -(target.y - pos.y))   # 0 faces -Y, counter-clockwise
        for dh in (-0.8, 0.0, 0.8):                              # a glance left, ahead, right, 20 degrees down
            memory.apply_sensor_reading(sensors.sense((pos.x, pos.y, 1.5), heading + dh, 0.35), floor_z=0.0)
        memory.mark_standing_footprint(pos.x, pos.y, RADIUS, 0.0)
        if path is None or planner.is_path_blocked(memory, path):
            path = planner.find_path(memory, pos.x, pos.y, goal.x, goal.y)
            replans += 1
            if path is None:
                break
        nxt = Vector((path[1]['x'], path[1]['y'])) if len(path) > 1 else goal
        d = nxt - pos
        pos = pos + d.normalized() * min(0.5, d.length) if d.length > 1e-6 else pos
        walked.append(pos.copy())
        if len(path) > 1 and (pos - nxt).length < 1e-3:
            path = path[1:] if len(path) > 2 else [path[-1]]
        if (pos - goal).length < 0.15:
            break
    arrived = (pos - goal).length < 0.25
    ctx.record('nav_arrived', 'PASS' if arrived else 'WARN',
               f'walked {len(walked) - 1} steps, {replans} plan(s), ended {(pos - goal).length:.2f} m from the goal; '
               f'explored {memory.get_explored_area():.1f} m2')
    worst = math.inf
    for a, b in zip(walked, walked[1:]):
        for k in range(11):
            p = a.lerp(b, k / 10)
            for ob in obstacles:
                lo = ob.matrix_world @ Vector(ob.bound_box[0])
                hi = ob.matrix_world @ Vector(ob.bound_box[6])
                dx = max(lo.x - p.x, 0, p.x - hi.x)
                dy = max(lo.y - p.y, 0, p.y - hi.y)
                worst = min(worst, math.hypot(dx, dy))
    ok = worst >= RADIUS                                         # the body's whole radius, against the true boxes
    ctx.record('nav_clearance', 'PASS' if ok else 'WARN',
               f'closest approach to an obstacle {worst:.3f} m (agent radius {RADIUS} m, planner clearance '
               f'{planner.clearance(memory):.2f} m centre to centre, cell {memory.cell_size} m)')

    route = [{'x': p.x, 'y': p.y, 'z': 0.0} for p in walked]
    nav.debug_overlay(memory, route, z=0.012)
    timing = nav.timed_route(route, speed=1.2)
    ctx.log(f'route: {len(route)} points, {timing[-1][0]:.1f} s at 1.2 m/s')

    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'SUN'))
    key.data.energy, key.data.angle = 3.0, math.radians(8)
    key.rotation_euler = (math.radians(40), 0, math.radians(30))
    scene.collection.objects.link(key)
    w = bpy.data.worlds.new('grey')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.25, 0.27, 0.3, 1)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 28
    cam.location = (5.5, -8.0, 9.0)
    cam.rotation_euler = (Vector((0.0, 0.3, 0.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
