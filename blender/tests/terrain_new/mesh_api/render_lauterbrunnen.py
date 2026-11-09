"""The mesh and API package's done-when renders (design section 11, package 5): real_place Lauterbrunnen with a
hero window around the reference's eye spot renders with no seams, and a character placed by height_at stands on
the ground.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/mesh_api/render_lauterbrunnen.py [--views eye,feet,aerial]

One make_terrain call (seven levels: 32 km at 32 m down to 500 m at 0.5 m around the eye spot), the alpine palette
and its rocks from the surfacing package; my robot body (claude_robot.vrm) stood 7.5 m in front of the eye camera,
grounded by characters.ground_vrm on Ground(fn=t.height_at), its foot points then measured against height_at and
against the rendered triangles (a ray cast). make_sky daylight with the reference rig's settings (Earth, 15:30,
cumulus, AgX Medium High Contrast, +0.5 exposure, the sun 70 degrees left of the view). 960 x 540, 16 samples.

Renders in out/mesh_api/renders/:
  lauterbrunnen_eye_alpine.png     the reference's eye camera (renders/lauterbrunnen_views.json), textured, the robot
  lauterbrunnen_eye_clay.png       the same camera in the reference rig's grey clay, beside the reference's own
  lauterbrunnen_feet_alpine.png    the robot's feet from 3 m, 0.6 m up
  lauterbrunnen_seams_clay.png     45 degrees down from 1.1 km onto the eye spot: all four hero windows' borders
                                   (500 m, 1 km, 2 km, 4 km) and the 0.5 m core cross the frame
  lauterbrunnen_seams_clay_lowsun.png   the same with the sun 8 degrees up, grazing (creases show most)
  lauterbrunnen_seams_alpine.png   the same, textured
  lauterbrunnen_*_levels.png       the eye and seam cameras with the ground coloured by ring level (unlit), to see
                                   where each seam runs in the frames above
and lauterbrunnen_renders.json (cameras, sun, foot gaps, timings).
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
REF = os.path.normpath(os.path.join(HERE, '..', 'reference'))
sys.path.insert(0, BLENDER)
sys.path.insert(0, REF)
sys.path.insert(0, HERE)
import render_references as RR  # noqa: E402
from _common import lauterbrunnen  # noqa: E402
from eidoblend.terrain import make_terrain  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402
from eidoblend.characters import load_vrm, Ground, ground_vrm, foot_points  # noqa: E402
from eidoblend.characters.ground import posed_foot_world  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api', 'renders'))
with open(os.path.join(REF, 'renders', 'lauterbrunnen_views.json')) as f:
    REF_EYE = json.load(f)['eye']
EYE_XY = tuple(REF_EYE['camera'][:2])
TARGET = tuple(REF_EYE['target'])


def log(*a):
    print('[mesh_api.render]', *a, flush=True)


def aim(cam, eye, target, lens):
    RR.place_camera(cam, eye, target)
    cam.data.lens = lens


def level_material():
    """Unlit ground coloured by eido_level (the ring's level): where each seam runs."""
    m = bpy.data.materials.new('levels')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    a = nt.nodes.new('ShaderNodeAttribute')
    a.attribute_type = 'GEOMETRY'
    a.attribute_name = 'eido_level'
    mr = nt.nodes.new('ShaderNodeMath')
    mr.operation = 'MULTIPLY'
    mr.inputs[1].default_value = 1.0 / 7.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    cols = [(0.1, 0.1, 0.1), (0.2, 0.3, 0.9), (0.1, 0.7, 0.8), (0.2, 0.8, 0.2), (0.9, 0.8, 0.1), (0.9, 0.4, 0.1),
            (0.9, 0.1, 0.3), (0.9, 0.9, 0.9)]
    cr.elements[0].color = (*cols[0], 1.0)
    cr.elements[1].position = 1.0 / 7.0 - 1e-3
    cr.elements[1].color = (*cols[1], 1.0)
    for k in range(2, 8):
        e = cr.elements.new(k / 7.0 - 1e-3)
        e.color = (*cols[k], 1.0)
    em = nt.nodes.new('ShaderNodeEmission')
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(a.outputs['Fac'], mr.inputs[0])
    nt.links.new(mr.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], o.inputs['Surface'])
    return m


def render(sc, cam, name, sky_root, sun_obj=None, hours=None):
    d = Vector(cam.matrix_world.col[2][:3]) * -1.0                # the view direction
    hd = math.atan2(d.y, d.x) + math.radians(RR.SUN_LEFT_DEG)
    sun_xy = (math.cos(hd), math.sin(hd))
    cache = os.path.join(sky_root, name)
    os.makedirs(cache, exist_ok=True)
    t0 = time.time()
    hours = RR.SUN_ELEV_HOURS if hours is None else hours
    sky = make_sky(sc, camera=cam, world='earth', hours=hours, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy), sun=sun_obj)
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)
    log(f'{name}.png {time.time() - t0:.1f} s')
    return sky, dict(camera=list(cam.location), lens_mm=cam.data.lens, sun_dir=list(sky.sun_dir),
                     seconds=round(time.time() - t0, 1))


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    views = (argv[argv.index('--views') + 1] if '--views' in argv else 'eye,feet,aerial').split(',')
    os.makedirs(OUT, exist_ok=True)
    rec = {}
    sc = RR.new_scene((960, 540), 16, RR.EXPOSURE)
    t0 = time.time()
    # the robot stands 7.5 m in front of the eye camera, 1.2 m right of the sight line, facing the camera
    ex, ey = EYE_XY
    dx, dy = TARGET[0] - ex, TARGET[1] - ey
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    rx, ry = ex + 14.0 * ux + 1.6 * uy, ey + 14.0 * uy - 1.6 * ux
    recipe, off = lauterbrunnen()
    t = make_terrain(recipe, params={'dem': 'lauterbrunnen'}, focus=[EYE_XY, (rx, ry)], seed=1,
                     name='lauterbrunnen', dress=True)
    rec['terrain'] = dict(levels=[str(lv) for lv in t.levels], triangles=t.ring.triangle_count,
                          seconds=t.info['seconds'], palette=t.info['palette'],
                          rocks=(t.rocks or {}).get('count'), skipped_stages=t.info['skipped_stages'],
                          stages_switched_off=off)
    alpine = list(t.obj.data.materials)
    clay = S.clay_material('lauterbrunnen_clay')
    levels = level_material()
    # the character
    face = math.degrees(math.atan2(ex - rx, -(ey - ry)))           # 0 faces -Y: turn it to face the camera
    h = load_vrm('claude_robot', location=(rx, ry, float(t.height_at(rx, ry))), rotation=face)
    shift = ground_vrm(h, Ground(fn=t.height_at))
    feet = foot_points(h)
    gaps = {}
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(t.obj, dg)
    for side in ('left', 'right'):
        P = posed_foot_world(h, feet, side)
        if not len(P):
            continue
        g = P[:, 2] - t.height_at(P[:, 0], P[:, 1])
        low = P[int(np.argmin(g))]
        hit = tree.ray_cast(Vector((low[0], low[1], low[2] + 2.0)), Vector((0.0, 0.0, -1.0)))
        gaps[side] = dict(points=int(len(P)), min_gap_m=float(g.min()), max_gap_m=float(g.max()),
                          lowest_point_above_rendered_ground_m=(float(low[2] - hit[0].z) if hit[0] else None))
    rec['robot'] = dict(at=[rx, ry], facing_deg=face, ground_vrm_shift_m=shift, feet=gaps)
    log(f'robot at ({rx:.1f}, {ry:.1f}), ground_vrm shift {shift:+.4f} m, feet {gaps}')
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.05, 60000.0
    sky_root = tempfile.mkdtemp(prefix='mesh_api_sky_')
    sun = None
    eye_z = float(t.height_at(ex, ey)) + RR.EYE_HEIGHT
    if 'eye' in views:
        aim(cam, (ex, ey, eye_z), TARGET, REF_EYE['lens_mm'])
        sky, rec['eye_alpine'] = render(sc, cam, 'lauterbrunnen_eye_alpine', sky_root)
        sun = sky.sun if hasattr(sky, 'sun') else None
        t.obj.data.materials.clear()
        t.obj.data.materials.append(clay)
        rocks_vis = None
        if t.rocks:
            rocks_vis = t.rocks['collection']
            rocks_vis.hide_render = True                      # the reference's clay has no rocks
        _sky, rec['eye_clay'] = render(sc, cam, 'lauterbrunnen_eye_clay', sky_root, sun)
        t.obj.data.materials.clear()
        t.obj.data.materials.append(levels)
        _sky, rec['eye_levels'] = render(sc, cam, 'lauterbrunnen_eye_levels', sky_root, sun)
        if rocks_vis is not None:
            rocks_vis.hide_render = False
        t.obj.data.materials.clear()
        for m in alpine:
            t.obj.data.materials.append(m)
    if 'feet' in views:
        fx, fy = rx - 3.0 * ux + 0.8 * uy, ry - 3.0 * uy - 0.8 * ux
        aim(cam, (fx, fy, float(t.height_at(fx, fy)) + 0.6), (rx, ry, float(t.height_at(rx, ry)) + 0.15), 40.0)
        sky, rec['feet_alpine'] = render(sc, cam, 'lauterbrunnen_feet_alpine', sky_root, sun)
        sun = sun or getattr(sky, 'sun', None)
    if 'aerial' in views:
        back = 1100.0 * math.cos(math.radians(45))
        cx, cy = ex - back * ux, ey - back * uy
        aim(cam, (cx, cy, eye_z + 1100.0 * math.sin(math.radians(45))), (ex, ey, eye_z), 35.0)
        t.obj.data.materials.clear()
        t.obj.data.materials.append(clay)
        sky, rec['seams_clay'] = render(sc, cam, 'lauterbrunnen_seams_clay', sky_root, sun)
        sun = sun or getattr(sky, 'sun', None)
        _sky, rec['seams_clay_lowsun'] = render(sc, cam, 'lauterbrunnen_seams_clay_lowsun', sky_root, sun,
                                                hours=17.3)
        t.obj.data.materials.clear()
        t.obj.data.materials.append(levels)
        _sky, rec['seams_levels'] = render(sc, cam, 'lauterbrunnen_seams_levels', sky_root, sun)
        t.obj.data.materials.clear()
        for m in alpine:
            t.obj.data.materials.append(m)
        _sky, rec['seams_alpine'] = render(sc, cam, 'lauterbrunnen_seams_alpine', sky_root, sun)
    if 'tile' in views:                                   # the reference rig's 45-degree aerial over the whole tile
        with open(os.path.join(REF, 'renders', 'lauterbrunnen_views.json')) as f:
            ra = json.load(f)['aerial']
        aim(cam, tuple(ra['camera']), tuple(ra['target']), ra['lens_mm'])
        cam.data.clip_start, cam.data.clip_end = 20.0, 120000.0
        t.obj.data.materials.clear()
        t.obj.data.materials.append(clay)
        sky, rec['tile_clay'] = render(sc, cam, 'lauterbrunnen_tile_clay', sky_root, sun)
        sun = sun or getattr(sky, 'sun', None)
        t.obj.data.materials.clear()
        t.obj.data.materials.append(levels)
        _sky, rec['tile_levels'] = render(sc, cam, 'lauterbrunnen_tile_levels', sky_root, sun)
        t.obj.data.materials.clear()
        for m in alpine:
            t.obj.data.materials.append(m)
    shutil.rmtree(sky_root, ignore_errors=True)
    rec['seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, 'lauterbrunnen_renders.json'), 'w') as f:
        json.dump(rec, f, indent=1, default=str)
    log('done', rec['seconds'], 's')


main()
