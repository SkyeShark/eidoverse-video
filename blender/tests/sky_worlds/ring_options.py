"""The ringworld's make_ringworld options, each exercised and rendered against the default from one camera and sky.

Three parts (--only picks variants by tag; --parts day,night,build picks parts):
  day    one build at --hours (9.5, up the arc); the band's material is rebuilt per material option and rendered
  night  the same build at --night (23, horizon); the night-only options act through the keyed night values or the
         analytic night side, so each variant re-bakes, then renders
  build  the options that change the build get one make_sky each (several options per build where they act on
         different things; each of those is also checked numerically)
Every panel goes to out/ring_options/<tag>.png and a labelled sheet per part; a PASS/FAIL line per check (an option
that changes nothing on screen, or in the data it owns, fails).

    bash run_blender.sh blender/tests/sky_worlds/ring_options.py [--hours 9.5] [--night 23] [--res 640x360]
        [--parts day,night,build] [--only default,litBand_false,...]
"""
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky import ring_materials as RM  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--hours', type=float, default=9.5)
ap.add_argument('--night', type=float, default=23.0)
ap.add_argument('--res', default='640x360')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--parts', default='day,night,build')
ap.add_argument('--only', default='')
ap.add_argument('--view', default='horizon', help='the day part\'s view (horizon: the band large and near; or up)')
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'ring_options')
os.makedirs(OUT, exist_ok=True)
PARTS = set(args.parts.split(','))
ONLY = set(filter(None, args.only.split(',')))

# day: material-only variants, rebuilt on the one band
DAY = [
    ('default', {}),
    ('litBand_false', dict(litBand=False)),
    ('waves_full', dict(waves='full', waveAmp=0.55)),
    ('waves_off', dict(waves=False)),
    ('waterWhite', dict(waterWhite=True)),
    ('analyticBandNormal_false', dict(analyticBandNormal=False)),
    ('debugBand_lighting', dict(debugBand='lighting')),
    ('debugBand_basic', dict(debugBand='basic')),
    ('inscatter_off_footVeil_off', dict(inscatterEnabled=False, footVeil=False)),
    ('bandAOFloor_0.2_normalScale_3', dict(bandAOFloor=0.2, bandNormalScale=3.0)),
    ('shoreWetness_0.9', dict(shoreWetness=0.9)),
    ('lightweightWaveAmp_1.5', dict(lightweightWaveAmp=1.5)),
    ('bandAOPackedNormal', dict(bandAOPackedNormal=True)),
]
# night: options that act through the keyed night values or the analytic night side (re-bake per variant)
NIGHT = [
    ('night_default', {}),
    ('night_litBand_false', dict(litBand=False)),
    ('night_litBand_false_nightLevel_2.4_nightSat_1_tint', dict(litBand=False, nightLevel=2.4, nightSat=1.0,
                                                                nightTint=(0.25, 0.32, 0.45))),
    ('night_hazeNightLevel_0.5', dict(hazeNightLevel=0.5)),
    ('night_footWidthNight_0.4', dict(footWidthNight=0.4)),
    ('night_inscatterNightLevel_1.0', dict(inscatterNightLevel=1.0)),
]
# build: one make_sky each; (tag, opts, view, when, on-screen threshold or None). Each renders where its option shows:
# relief shadows on the far arc at night, the cloud sheet (3.5-7 km near fade) looking up the arc; an option whose
# effect is slight by nature (the prefilter) is checked in its data only
BUILD = [
    ('geometryRelief_false', dict(geometryRelief=False), 'day', 'day', 0.002),
    # the band joins its sun's blockers (checked below), but EEVEE draws no visible relief self-shadow at 5-10 km:
    # the frame is reported, not judged ('info')
    ('bandCastShadow_true', dict(bandCastShadow=True), 'horizon', 'night', 'info'),
    ('ringClouds_false', dict(ringClouds=False), 'up', 'day', 0.002),
    ('ringClouds_false_night', dict(ringClouds=False), 'up', 'night', 0.002),
    ('cloudHeight_120_terrainHeightMeters_40', dict(cloudHeight=120.0, terrainHeightMeters=40.0), 'up', 'day', 0.002),
    ('bandLights_false', dict(bandLights=False), 'day', 'day', 0.002),
    ('bandSunIntensity_8_bandShineIntensity_2', dict(bandSunIntensity=8.0, bandShineIntensity=2.0), 'day', 'day', 0.002),
    ('shoreTexels_12_cloudAtlas_1024x32_bandShadowMapSize_512',
     dict(shoreTexels=12.0, cloudAtlas=dict(width=1024, height=32), bandShadowMapSize=512), 'up', 'day', None),
    ('panelTile_8_fogWallRadius_700_localReliefBlend_0_300_around_1024_across_128',
     dict(panelTile=8.0, fogWallRadius=700.0, localReliefBlend=(0.0, 300.0), around=1024, across=128), 'horizon',
     'day', 0.002),
    ('fogWall_false', dict(fogWall=False), 'horizon', 'day', 0.001),     # a thin haze band at the horizon
    ('reliefPrefilter_false', dict(reliefPrefilter=False), 'horizon', 'night', None),
]
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)


def scene(view):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, H = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.eevee.use_raytracing = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.render.fps = 24
    sc.frame_start = sc.frame_end = 1
    sc.render.image_settings.file_format = 'PNG'
    g = bpy.data.materials.new('ground')
    g.use_nodes = True
    g.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.15, 0.12, 1)
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=600, fill_type='NGON')
    bpy.context.object.data.materials.append(g)
    cd = bpy.data.cameras.new('cam')
    cd.lens_unit = 'FOV'
    cd.angle = math.radians(62)
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    aim(cam, view)
    return sc, cam


def aim(cam, view):
    cam.location = (0, 0, 1.7)
    pitch = 55.0 if view == 'up' else 6.0
    cam.rotation_euler = (math.radians(90 + pitch), 0, 0)


def render(sc, tag):
    path = os.path.join(OUT, '%s.png' % tag)
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    print('[ring_options] %s rendered in %.1fs, mean %s' % (tag, time.time() - t0, px.mean((0, 1)).round(3)),
          flush=True)
    return px


def build(opts, tag, hours, view):
    sc, cam = scene(view)
    sky = make_sky(sc, camera=cam, world='ringworld', hours=hours, clouds='cumulus', quality='draft',
                   cache_dir=os.path.join(OUT, 'cache_' + tag), ring=dict(opts))
    sky.bake(log=lambda *a: None)
    return sc, cam, sky


def band_mask(basic, default):
    """The band's pixels: where the flat-red debug material changes the frame (AgX and the band's light make the red
    pinkish, so a colour threshold misses it; the difference does not)."""
    return (np.abs(basic - default).sum(-1) > 0.08) & (basic[..., 0] > basic[..., 2])


def rebuild_band(ring, opts):
    """The band's material for these options; litBand=False also takes the band's lamps away, as the JS builds none."""
    ring.opts = opts
    RM.band_material(ring, ring.band, authored=ring.authored_band)
    for lamp in (ring.band_sun, ring.band_shine):
        if lamp is not None:
            lamp.hide_render = not RM.opt_on(opts, 'litBand', True)


# options whose mark is a thin strip of the band at this distance (the wet shoreline): a lower bar, still above noise
SUBTLE = {'shoreWetness_0.9': 0.0005}


def compare(shots, base_tag, mask, part):
    base = shots[base_tag]
    for tag, img in shots.items():
        if tag in (base_tag, 'debugBand_basic'):
            continue
        region = mask if (mask is not None and mask.any()) else np.ones(base.shape[:2], bool)
        if img.shape != base.shape:
            continue
        d = np.abs(img - base)[region].mean()
        bar = SUBTLE.get(tag, 0.002)
        check('%s: %s changes the band on screen' % (part, tag), d > bar,
              'mean |delta| over the band %.4f, bar %.4f' % (d, bar))


def sheet(shots, name):
    """A labelled contact sheet with Blender's own image API (the label is the file name list printed below)."""
    names = list(shots)
    if not names:
        return
    h, w = shots[names[0]].shape[:2]
    cols = 4
    rows = (len(names) + cols - 1) // cols
    big = np.zeros((rows * h, cols * w, 3), np.float32)
    for i, n in enumerate(names):
        r = rows - 1 - i // cols                 # Blender pixel rows run bottom-up: the first row at the top
        big[r * h:(r + 1) * h, (i % cols) * w:(i % cols + 1) * w] = shots[n]
    im = bpy.data.images.new(name, big.shape[1], big.shape[0])
    px = np.ones((big.shape[0], big.shape[1], 4), np.float32)
    px[..., :3] = big
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = os.path.join(OUT, name + '.png')
    im.file_format = 'PNG'
    im.save()
    print('[ring_options] %s: %s' % (name, ', '.join(names)), flush=True)


t_all = time.time()
# ---- day: material variants on one build ----
if 'day' in PARTS:
    sc, cam, sky = build({}, 'day', args.hours, args.view)
    ring = sky.ring
    base_opts = dict(ring.opts)
    shots = {}
    for tag, opts in DAY:
        if ONLY and tag not in ONLY and tag not in ('default', 'debugBand_basic'):
            continue
        rebuild_band(ring, dict(base_opts, **opts))
        shots[tag] = render(sc, tag)
    rebuild_band(ring, base_opts)
    mask = band_mask(shots['debugBand_basic'], shots['default']) if 'debugBand_basic' in shots else None
    if mask is not None:
        check('day: debugBand=basic paints the band flat red', mask.mean() > 0.01,
              'band covers %.1f%% of the frame' % (100 * mask.mean()))
    if 'debugBand_lighting' in shots and mask is not None and mask.any():
        L = shots['debugBand_lighting'][mask]
        check('day: debugBand=lighting shows the terminator in red, planetshine visibility in green',
              L[:, 0].max() > 0.2, 'band red p50 %.3f, green p50 %.3f, blue p50 %.3f' % tuple(np.median(L, 0)))
    compare(shots, 'default', mask, 'day')
    sheet(shots, 'sheet_day')
    # ---- night: keyed values, a re-bake per variant ----
    if 'night' in PARTS:
        aim(cam, 'horizon')
        sky.set_time(args.night)
        nshots = {}
        for tag, opts in NIGHT:
            if ONLY and tag not in ONLY and tag != 'night_default':
                continue
            rebuild_band(ring, dict(base_opts, **opts))
            sky.bake(log=lambda *a: None)
            nshots[tag] = render(sc, tag)
            if tag == 'night_footWidthNight_0.4':
                fw = ring.last['foot_w']
                check('night: footWidthNight keys the foot veil width', abs(fw - 0.4) < 0.05, 'foot_w %.3f' % fw)
            if tag == 'night_inscatterNightLevel_1.0':
                check('night: inscatterNightLevel keys the inscatter floor', ring.last['insc_night'] > 0.95,
                      'insc_night %.3f' % ring.last['insc_night'])
            if tag == 'night_hazeNightLevel_0.5':
                hz = max(ring.last['haze'])
                check('night: hazeNightLevel lifts the night haze floor', hz > 0.3, 'haze peak %.3f' % hz)
        rebuild_band(ring, base_opts)
        compare(nshots, 'night_default', None, 'night')
        sheet(nshots, 'sheet_night')
# ---- build variants ----
def read_png(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return px


if 'build' in PARTS:
    bshots = {}
    refs = {}

    def reference(view, when):
        """The default build's frame for this view and time: the day / night parts' defaults when they match,
        else a default build rendered here once."""
        key = (view, when)
        if key not in refs:
            known = {(args.view, 'day'): 'default.png', ('horizon', 'night'): 'night_default.png'}
            path = os.path.join(OUT, known.get(key, 'build_default_%s_%s.png' % (view, when)))
            if key not in known or not os.path.exists(path):
                s_, c_, k_ = build({}, 'ref_%s_%s' % key, args.hours if when == 'day' else args.night, view)
                render(s_, os.path.splitext(os.path.basename(path))[0])
            refs[key] = read_png(path)
        return refs[key]

    for tag, opts, view, when, thresh in BUILD:
        if ONLY and tag not in ONLY:
            continue
        view = args.view if view == 'day' else view
        ref = reference(view, when) if thresh is not None else None
        sc, cam, sky = build(opts, tag, args.hours if when == 'day' else args.night, view)
        r = sky.ring
        bshots[tag] = render(sc, tag)
        if ref is not None and ref.shape == bshots[tag].shape:
            d = np.abs(bshots[tag] - ref).mean()
            if thresh == 'info':
                print('INFO build: %s against the default (%s view, %s): mean |delta| %.4f' % (tag, view, when, d),
                      flush=True)
            else:
                check('build: %s changes the frame against the default (%s view, %s)' % (tag, view, when),
                      d > thresh, 'mean |delta| %.4f' % d)
        if tag == 'geometryRelief_false':
            check('build: geometryRelief=False keeps the GLB terrain mesh',
                  len(r.band.data.vertices) < 10000 and r.authored_band, '%d vertices' % len(r.band.data.vertices))
        if tag.startswith('cloudHeight_120'):
            co = np.empty(len(r.clouds.data.vertices) * 3, np.float32)
            r.clouds.data.vertices.foreach_get('co', co)
            rad = np.hypot(co[1::3], co[2::3]).mean()
            gi = r.info['geometryRelief']
            check('build: cloudHeight=120 puts the sheet 120 m above the band; terrainHeightMeters=40 caps the relief',
                  abs(rad - 4880.0) < 1.0 and abs(gi['max_height'] - 40.0) < 0.5,
                  'sheet radius %.1f, relief max %.1f m' % (rad, gi['max_height']))
        if tag == 'bandCastShadow_true':
            names = sorted(o.name for o in r.band_sun.light_linking.blocker_collection.objects)
            check('build: bandCastShadow adds the band and walls to the band sun\'s blockers',
                  'eido_ring_band' in names and 'eido_ring_walls' in names, str(names))
        if tag == 'bandLights_false':
            check('build: bandLights=False builds no band lamps', r.band_sun is None and r.band_shine is None
                  and 'eido_ring_band_sun' not in bpy.data.objects)
        if tag.startswith('bandSunIntensity_8'):
            check('build: bandSunIntensity / bandShineIntensity set the lamps',
                  abs(r.band_sun.data.energy - 8.0) < 1e-6 and abs(r.band_shine.data.energy - 2.0) < 1e-6)
        if tag.startswith('shoreTexels_12'):
            ok = (os.path.basename(r.mask_soft_path) == 'ring_landmask_soft_12.exr'
                  and r.info['cloudAtlas'] == (1024, 32) and os.path.exists(r.cloud_field_path)
                  and abs(r.band_sun.data.shadow_maximum_resolution - 11500.0 / 512) < 1e-3)
            check('build: shoreTexels / cloudAtlas / bandShadowMapSize reach their caches and the lamp', ok,
                  '%s, atlas %s, texel %.2f m' % (os.path.basename(r.mask_soft_path), r.info['cloudAtlas'],
                                                  r.band_sun.data.shadow_maximum_resolution))
        if tag.startswith('panelTile_8'):
            gi = r.info['geometryRelief']
            co = np.empty(len(r.fog_wall.data.vertices) * 3, np.float32)
            r.fog_wall.data.vertices.foreach_get('co', co)
            fr = np.hypot(co[0::3], co[1::3]).mean()
            check('build: panelTile, fogWallRadius, localReliefBlend, around/across reach the build',
                  r.tile == 8.0 and abs(fr - 700.0) < 1.0 and gi['around'] == 1024 and gi['across'] == 128
                  and tuple(gi['local_relief_blend']) == (0.0, 300.0),
                  'tile %g, fog wall r %.1f, rows %d x %d' % (r.tile, fr, gi['around'], gi['across']))
        if tag == 'fogWall_false':
            check('build: fogWall=False drops the fog boundary and the rain wall',
                  r.fog_wall is None and r.rain_wall is None)
        if tag == 'reliefPrefilter_false':
            check('build: reliefPrefilter=False samples the raw relief', r.info['geometryRelief']['prefilter'] is False)
    # the visible build options against the day default (same camera for the 'up' builds)
    sheet(bshots, 'sheet_build')
print('[ring_options] all in %.1fs' % (time.time() - t_all))
print('PASS ring_options all' if ok_all else 'FAIL ring_options some')
