"""A CUSTOM celestial cluster (the WebGPU guide's "Custom celestial clusters" example): make_shattered_moon outside the
shieldworld, placed by the scene.

    eval(Deno.readTextFileSync('eidoverse/asteroid_moon.js'));
    const cluster = await makeShatteredMoon({ glbBytes: ASSETS.fragments, spread: 1.75 });
    scene.add(cluster.group);
    cluster.uniforms.sunDir.value.copy(sunDirection).normalize();
    cluster.update(t);                                  // in renderFrame(t)

Part A, no sky: the cluster alone on black, its group animated by the scene, lit through cluster.uniforms and keyed by
cluster.bake(). Part B, in an Earth twilight sky: sky.attach_cluster(cluster) lights it with the sky's true sun, marches
its accretion dust in the sky shader and composites the sky's clouds over it; rendered with and without the cluster.
Checks: the fragments drift and tumble, the scene's own group animation survives both bakes, the dust follows the hero
fragment's world position, the sky compiles the dust, the cluster shows in the frame.

    bash run_blender.sh blender/tests/sky_worlds/custom_cluster.py [--res 640x360] [--clouds cumulus]
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky import palette as P  # noqa: E402
from eidoblend.sky.asteroid_moon import make_shattered_moon  # noqa: E402
from eidoblend.sky.world_nodes import _fcurves  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='640x360')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--clouds', default='cirrus', help='the second Part B sky, after the clear one')
ap.add_argument('--hours', type=float, default=18.6)
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'cluster')
os.makedirs(OUT, exist_ok=True)
GLB = os.path.join(REPO, 'eidoverse', 'assets', 'sky', 'celestial', 'asteroid_cluster_v3.glb')
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)
    return ok


def scene_base(frames):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, H = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    return sc


def camera(sc, loc, target, fov_deg, clip_end):
    from mathutils import Vector
    cd = bpy.data.cameras.new('cam')
    cd.lens_unit = 'FOV'
    cd.angle = math.radians(fov_deg)
    cd.clip_start = 0.1
    cd.clip_end = clip_end
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = loc
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y')
    return cam


def render(sc, name, frame=1):
    sc.frame_set(frame)
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    return px


def key_group_path(g, frames, start, end):
    """The scene's own animation of the cluster's group: a slow slide (LINEAR)."""
    g.location = start
    g.keyframe_insert('location', frame=1)
    g.location = end
    g.keyframe_insert('location', frame=frames)
    for fc in group_fcurves(g):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def group_fcurves(g):
    ad = g.animation_data
    return _fcurves(ad) if ad and ad.action else []


# ------------------------------------------------------------------ Part A: the cluster alone, no sky ---
FR = 48
sc = scene_base(FR)
world = bpy.data.worlds.new('black')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
sc.world = world
cluster = make_shattered_moon(sc, GLB, spread=1.75, scale=1.0)
fm = cluster.motion
extent = max(float(np.linalg.norm(b)) + r for b, r in zip(fm.base_positions, fm.radii))
print('[custom_cluster] %d fragments, cluster extent %.2f units, hero r %.2f' % (len(cluster.pieces), extent,
                                                                                  fm.radii[fm.hero_index]), flush=True)
key_group_path(cluster.group, FR, (0.0, 0.0, 0.0), (0.3 * extent, 0.0, 0.0))
cam = camera(sc, (0.0, -3.2 * extent, 0.25 * extent), (0.0, 0.0, 0.0), 40.0, 100.0 * extent)
vals = cluster.bake(sun_dir=P.norm3((1.0, -0.35, 0.45)))
check('A: the scene keeps its own animation of the group (bake keys the fragments, not the group)',
      len(group_fcurves(cluster.group)) == 3, '%d location curves' % len(group_fcurves(cluster.group)))
p0 = np.array(vals[0]['pieces'])
p1 = np.array(vals[-1]['pieces'])
q0 = np.array(vals[0]['quats'])
q1 = np.array(vals[-1]['quats'])
check('A: the fragments drift (bounded) and tumble over %d frames' % FR,
      np.abs(p1 - p0).max() > 1e-5 and np.abs(q1 - q0).max() > 1e-4,
      'max drift %.5f, max quaternion change %.5f' % (np.abs(p1 - p0).max(), np.abs(q1 - q0).max()))
check('A: no two fragment envelopes touch', fm.stats['minimumEnvelopeClearance'] >= fm.stats['clearance'] - 1e-6,
      'clearance %.4f' % fm.stats['minimumEnvelopeClearance'])
hero = cluster.pieces[fm.hero_index]
sc.frame_set(FR)
hp_b = cluster.group.matrix_world @ hero.location
org_b = P.three_to_blender(vals[-1]['U']['dustOrigin'])
check('A: the dust origin follows the hero fragment through the scene-animated group',
      max(abs(a - b) for a, b in zip(hp_b, org_b)) < 1e-3 * extent,
      'hero %s dust %s' % (tuple(round(c, 3) for c in hp_b), tuple(round(c, 3) for c in org_b)))
img = render(sc, 'cluster_alone_f01', 1)
lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
check('A: the lit fragments show on black', (lum > 0.05).mean() > 0.01, 'lit pixels %.3f' % (lum > 0.05).mean())
render(sc, 'cluster_alone_f%02d' % FR, FR)

# ------------------------------------------------- Part B: the same cluster in an Earth twilight sky ---
# a clear sky for the checks; then args.clouds, whose deck the overlay lays over the cluster (to look at: in this
# direction a cumulus deck can hide it completely, which is the overlay working)
for clouds in ('clear', args.clouds):
    sc = scene_base(2)
    bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, 0))
    ground = bpy.context.object
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.12, 0.10, 0.08, 1)
    ground.data.materials.append(gm)
    sun3, _moon3, _az, el = P.sun_moon_at(args.hours)
    s_b = P.three_to_blender(sun3)
    side = P.norm3((-s_b[1], s_b[0], 0.0))                  # 90 degrees round from the sun: a half-lit phase
    elev = math.radians(24.0)
    d = P.norm3((side[0] * math.cos(elev), side[1] * math.cos(elev), math.sin(elev)))
    DIST, SCALE = 33000.0, 1400.0
    cluster = make_shattered_moon(sc, GLB, spread=1.75, scale=SCALE)
    c0 = tuple(c * DIST for c in d)
    key_group_path(cluster.group, 2, c0, tuple(c0[i] + (300.0, 0.0, 0.0)[i] for i in range(3)))
    cam = camera(sc, (0.0, 0.0, 1.7), c0, 34.0, 60000.0)
    sky = make_sky(sc, camera=cam, world='earth', hours=args.hours, clouds=clouds, quality='draft',
                   cache_dir=os.path.join(OUT, 'cache_earth_cluster_%s' % clouds))
    sky.attach_cluster(cluster)
    frames = sky.bake(log=lambda *a: None)
    tag = 'cluster_earth_%05.2f_%s' % (args.hours, clouds)
    if clouds == 'clear':
        bk = sky.baker()
        check('B: the sky shader compiles the attached cluster\'s dust', bk.has('HAS_DUST') and bool(bk.dust_src))
        check('B: the scene keeps its own animation of the group through the sky bake',
              len(group_fcurves(cluster.group)) == 3, '%d location curves' % len(group_fcurves(cluster.group)))
        mv = frames[-1]['moon']
        check('B: the cluster is lit by the sky\'s true sun', max(abs(a - b) for a, b in zip(
            P.three_to_blender(mv['sun_dir3']), P.three_to_blender(P.norm3(sky.sky.sun_dir)))) < 1e-6,
              'sun elevation %.1f deg' % math.degrees(el))
        sc.frame_set(frames[-1]['frame'])
        hero = cluster.pieces[cluster.motion.hero_index]
        hp_b = cluster.group.matrix_world @ hero.location
        org_b = P.three_to_blender(mv['U']['dustOrigin'])
        check('B: the dust origin sits on the hero fragment (world)',
              max(abs(a - b) for a, b in zip(hp_b, org_b)) < 1.0,
              'hero %s dust %s' % (tuple(round(c) for c in hp_b), tuple(round(c) for c in org_b)))
    with_c = render(sc, tag, 1)
    for ob in list(cluster.pieces) + [cluster.specks]:
        ob.hide_render = True
    without = render(sc, tag + '_fragments_hidden', 1)
    changed = float((np.abs(with_c - without).sum(-1) > 0.03).mean())
    if clouds == 'clear':
        check('B: the fragments and debris river show in a clear twilight sky', changed > 0.003,
              'changed pixels %.4f' % changed)
    else:
        print('[custom_cluster] %s: the fragments change %.4f of the frame through the deck' % (clouds, changed),
              flush=True)
print('PASS custom_cluster all' if ok_all else 'FAIL custom_cluster some')
