"""make_sky's engine options and celestial bodies, without rendering (no GPU slot needed).

Checks, one PASS/FAIL line each:
  - earthRadius reaches the sky shader as R_EARTH (sky_system.js opts.earthRadius); a radius <= 0 raises
  - the ring deck options (ringCloudBase, ringCloudThick, ringLocalHalf, ringWispCurveHalf) reshape the deck the shader
    and the cloud-shadow caster read; the environment traces the band at its own half-width (ring.info); the haze
    walls' copies for the cloud dome (order_walls_under_dome) draw each wall where it stands, from 2000 km ahead
  - stormSamples and cloudShadowSamples set the storm march and the cloud-shadow march, within the JS's bounds; the
    cloud-shadow march defaults to the main march's step count (Eanpa)
  - textures={'stars', 'moon'} replace the world's maps; an unknown key, a missing file and a moon map on the
    shieldworld raise; a float map is read linear, a colour map from sRGB
  - celestial=make_red_giant({'shield': False}) in an Earth sky: it rides the sun with the default disc off, its
    palette tints the sky, set_colors(star) reaches it, set_colors(shield) warns; a body of your own with the same
    contract compiles in; the shieldworld refuses a second body
  - sun_coverage_dim matches sunCoverageDim's formula (an independent numpy evaluation of the JS) at many ground points
    and frames, spans 1 - strength .. 1, and keys a lamp through frame_states
  - cloud_shadow_strength is bounded to 0..1 and splits the sun (the lamp keeps the share the clouds shadow, the
    clear-share twin the rest, past the caster); eido_noCloudShadow objects get the sun's twin (link_opt_outs) with the
    light-linking states the measurement in sky_options_render.py rests on; the twins keep the sun lamp's own light
    linking (its blockers, and for the clear share its receivers, child collections included)

    bash run_blender.sh blender/tests/sky/test_sky_options.py
"""
import io
import math
import os
import sys
from contextlib import redirect_stdout

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky, ASSETS  # noqa: E402
from eidoblend.sky import cloud_shadows  # noqa: E402
from eidoblend.sky.bake.baker import weather_map, load_image_rgba, write_exr  # noqa: E402
from eidoblend.sky.redgiant import make_red_giant  # noqa: E402

OUT = os.path.join(HERE, 'out', 'options_state')
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  (' + str(detail) + ')') if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


def raises(fn, kind=Exception):
    try:
        fn()
    except kind as e:
        return str(e) or True
    return False


def fresh(frames=12):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 640, 360
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, frames
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0, 0, 1.7)
    cam.rotation_euler = (math.radians(95), 0, 0)
    return sc, cam


def cache(tag):
    return os.path.join(OUT, tag)


# ---- earthRadius ----
sc, cam = fresh()
sky = make_sky(sc, camera=cam, cache_dir=cache('earth'), quality='draft', earthRadius=150000.0)
d = sky.baker().defines
check('earthRadius reaches the shader as R_EARTH', d.get('R_EARTH') == 150000.0, d.get('R_EARTH'))
sky = make_sky(sc, camera=cam, cache_dir=cache('earth'), quality='draft')
check('without it the shader keeps its 6371 km', 'R_EARTH' not in sky.baker().defines)
src = open(os.path.join(REPO, 'blender', 'eidoblend', 'sky', 'bake', 'sky.glsl'), encoding='utf-8').read()
check('sky.glsl takes R_EARTH as a define with the 6371 km default', '#ifndef R_EARTH\n#define R_EARTH 6371000.0' in src)
check('an earthRadius of 0 raises', raises(lambda: make_sky(sc, camera=cam, cache_dir=cache('x'), earthRadius=0.0),
                                           ValueError))

# ---- sample counts ----
for opts, want in ((dict(), (12, 60)), (dict(stormSamples=24, cloudShadowSamples=40), (24, 40)),
                   (dict(stormSamples=2, cloudShadowSamples=10), (4, 32)), (dict(cloudShadowSamples=200), (12, 64))):
    sky = make_sky(sc, camera=cam, cache_dir=cache('earth'), quality='draft', **opts)
    d = sky.baker().defines
    got = (d['N_STORM_STEPS'], d['N_CLOUD_SHADOW'])
    check('stormSamples / cloudShadowSamples %s -> storm march %d, cloud-shadow march %d (passes %d)'
          % (opts or 'defaults', want[0], want[1], d['N_STORM_PASSES']), got == want and d['N_STORM_PASSES'] == 2, got)

# ---- textures ----
moon_alt = os.path.join(ASSETS, 'celestial', 'rock_giant.png')
sky = make_sky(sc, camera=cam, cache_dir=cache('earth'), quality='draft', textures={'moon': 'celestial/rock_giant.png'})
bk = sky.baker()
check("textures={'moon': ...} replaces the world's moon map (a path under eidoverse/assets/sky/ works)",
      os.path.normcase(bk.paths['moon']) == os.path.normcase(moon_alt)
      and bk.paths['stars'].endswith('starmap_tycho_4k.jpg'), bk.paths)
check('an unknown texture key raises and names the valid ones',
      "'stars' and 'moon'" in str(raises(lambda: make_sky(sc, camera=cam, cache_dir=cache('x'),
                                                          textures={'hdri': moon_alt}), ValueError)))
check('a missing texture file raises',
      raises(lambda: make_sky(sc, camera=cam, cache_dir=cache('x'), textures={'stars': 'C:/no/such/stars.png'}),
             FileNotFoundError))
check("the shieldworld refuses a moon map (its moon is the shattered cluster)",
      raises(lambda: make_sky(sc, camera=cam, world='shieldworld', cache_dir=cache('x'),
                              textures={'moon': moon_alt}), ValueError))
# a float star map is linear as stored; an 8-bit one is decoded from sRGB
arr = np.zeros((4, 8, 4), np.float32)
arr[..., :3] = 0.5
arr[..., 3] = 1.0
exr = os.path.join(OUT, 'grey_0.5.exr')
write_exr(exr, arr, half=False)
lin = load_image_rgba(exr, srgb=True)
png = os.path.join(OUT, 'grey_128.png')
im = bpy.data.images.new('grey_128', 8, 4, alpha=True)
im.pixels.foreach_set(np.full(8 * 4 * 4, 128 / 255.0, np.float32))
im.filepath_raw, im.file_format = png, 'PNG'
im.save()
bpy.data.images.remove(im)
dec = load_image_rgba(png, srgb=True)
check('texture maps: an EXR is read linear, a PNG decoded from sRGB',
      abs(float(lin[0, 0, 0]) - 0.5) < 1e-6 and abs(float(dec[0, 0, 0]) - 0.2158605) < 2e-3,
      'exr %.4f png %.4f' % (lin[0, 0, 0], dec[0, 0, 0]))

# ---- celestial bodies ----
rg = make_red_giant({'shield': False})
sky = make_sky(sc, camera=cam, cache_dir=cache('earth_rg'), hours=17.0, quality='draft', celestial=rg)
d = sky.baker().defines
check('a red giant without its shield in an Earth sky: the celestial hook compiles in, no shield',
      d.get('HAS_CELESTIAL') == 1 and 'HAS_SHIELD' not in d and 'shadeStar' in sky.baker().celestial_src)
check("its palette tint goes into the sky's options", sky.sky.opts.get('paletteTint') == rg.palette_tint)
sky.update(0.0)
U = sky.sky.U
check('it rides the sun: starDir is the sun, the default disc and glow lobes are off',
      U['starDir'] == tuple(sky.sky.sun_dir) and U['sunDiscI'] == 0.0 and U['sunGlowI'] == 0.0)
buf = io.StringIO()
with redirect_stdout(buf):
    sky.set_colors({'star': (1.0, 0.8, 0.8), 'shield': (1, 0, 0)})
check('set_colors(star) recolours it; set_colors(shield) warns (no shield) and is ignored',
      rg.star_tint == (1.0, 0.8, 0.8) and 'has no shield' in buf.getvalue() and rg.shield_color != (1.0, 0.0, 0.0))
check('the shieldworld refuses a second celestial body',
      raises(lambda: make_sky(sc, camera=cam, world='shieldworld', cache_dir=cache('x'), celestial=rg), ValueError))
check('celestial= refuses an object without celestial_glsl()',
      raises(lambda: make_sky(sc, camera=cam, cache_dir=cache('x'), celestial=object()), ValueError))


class Planet:
    """A body of your own: only celestial_glsl() is required (a gas giant disc at a fixed direction)."""

    def celestial_glsl(self):
        return ('vec3 celestial(vec3 dir, vec3 col) {\n'
                '    float c = dot(dir, normalize(vec3(0.3, 0.35, -0.88)));\n'
                '    return c > 0.985 ? mix(col, vec3(0.8, 0.6, 0.4), smoothstep(0.985, 0.986, c)) : col;\n'
                '}\n')


sky = make_sky(sc, camera=cam, cache_dir=cache('earth_planet'), quality='draft', celestial=Planet())
d = sky.baker().defines
sky.update(0.0)
check('a body of your own with only celestial_glsl(): the hook compiles in, the sun keeps its disc, no shield',
      d.get('HAS_CELESTIAL') == 1 and 'vec3 celestial(' in sky.baker().celestial_src and sky.sky.U['sunDiscI'] > 0
      and not sky._has_shield())

# ---- ring deck ----
sc, cam = fresh()
sky = make_sky(sc, camera=cam, world='ringworld', hours=11, cache_dir=cache('ringworld'), quality='draft',
               ringCloudBase=620.0, ringCloudThick=360.0, ringLocalHalf=3000.0, ringWispCurveHalf=1200.0)
d = sky.baker().defines
check('the ring deck options reshape the deck the shader marches',
      (d['RING_BASE'], d['RING_THICK'], d['RING_LOCAL_HALF'], d['RING_WISP_CURVE_HALF']) == (620.0, 360.0, 3000.0, 1200.0)
      and d['RING_SLAB_LO'] == 600.0, (d['RING_BASE'], d['RING_THICK'], d['RING_LOCAL_HALF'], d['RING_WISP_CURVE_HALF']))
frames = [dict(U=dict(sky.sky.U)) for _ in sky.frame_states(1, 2)]
check("the cloud-shadow caster reads the reshaped deck (under its base, the band's twin at its top)",
      abs(cloud_shadows.caster_height_for(frames) - 0.9 * 620.0) < 1e-6
      and abs(cloud_shadows.deck_top_for(frames) - (620.0 + 360.0)) < 1e-6)
check("the environment traces the band at the ring's own size (info radius and halfWidth)",
      d['RING_HALF_W'] == float(sky.ring.info['halfWidth']) == 483.0 and d['RING_BAND_R'] == 5000.0)
check('a ring deck option of 0 raises',
      raises(lambda: make_sky(sc, camera=cam, world='ringworld', cache_dir=cache('x'), ringCloudThick=0.0),
             ValueError))
# the haze walls under the cloud dome: copies riding 2000 km down the view axis draw each wall where it stands
copies = sky.ring.order_walls_under_dome(cam, on=True)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
worst = 0.0
for c in copies:
    src = bpy.data.objects[c.name[:-len('_under_dome')]]
    a = np.array([src.matrix_world @ v.co for v in src.evaluated_get(dg).data.vertices])
    ce = c.evaluated_get(dg)
    b = np.array([ce.matrix_world @ v.co for v in ce.data.vertices])
    worst = max(worst, float(np.abs(a - b).max()) if len(a) == len(b) and len(a) else 1e9)
    dist = (c.matrix_world.translation - cam.matrix_world.translation).length
check('order_walls_under_dome: each wall drawn by a copy whose origin rides 2000 km ahead, its surface where the wall '
      'stands (the walls out of the render)', len(copies) == 2 and worst < 0.5 and dist > 1.9e6
      and all(bpy.data.objects[c.name[:-len('_under_dome')]].hide_render for c in copies),
      'largest vertex offset %.3f m' % worst)
sky.ring.order_walls_under_dome(cam, on=False)
check('without the dome the copies go and the walls render themselves',
      not [o for o in bpy.data.objects if o.name.endswith('_under_dome')]
      and not sky.ring.fog_wall.hide_render and not sky.ring.rain_wall.hide_render)

# ---- sun_coverage_dim ----
sc, cam = fresh(48)
sky = make_sky(sc, camera=cam, cache_dir=cache('coverage'), hours=15.0, clouds='cumulus', quality='draft',
               weather_fx=False)
wm = weather_map()[..., 0].astype(np.float64)


def js_sun_coverage_dim(U, x3, z3, strength=0.7):
    """sky_system.js sunCoverageDim(x, z, strength) with its weatherAt, in numpy: an independent reference."""
    Ld = U['cloudLightDir']
    dy = max(0.12, Ld[1])
    t = U['cloudStart'] / dy
    xx, zz = x3 + Ld[0] * t, z3 + Ld[2] * t
    sc_ = 0.00005 * U['wScale']
    dr = U['cloudDisplacement']
    uu = ((-((zz - dr[2]) * sc_)) % 1.0) * 512
    vv = ((-((xx - dr[0]) * sc_)) % 1.0) * 512
    x0, y0 = int(math.floor(uu)) % 512, int(math.floor(vv)) % 512
    x1, y1 = (x0 + 1) % 512, (y0 + 1) % 512
    fx, fy = uu - math.floor(uu), vv - math.floor(vv)
    val = (wm[y0, x0] * (1 - fx) + wm[y0, x1] * fx) * (1 - fy) + (wm[y1, x0] * (1 - fx) + wm[y1, x1] * fx) * fy
    cov = max(0.0, min(2.0, (val - U['largeT']) * U['largeA']))
    return 1.0 - min(1.0, max(0.0, (cov - 0.35) / 1.05)) * strength


rng = np.random.default_rng(7)
pts = rng.uniform(-6000.0, 6000.0, (40, 2))
worst, vals = 0.0, []
for f, t, _L in sky.frame_states(1, 48):
    if f % 12:
        continue
    for x, y in pts:
        a = sky.sun_coverage_dim(x, y)
        b = js_sun_coverage_dim(sky.sky.U, x, -y)
        worst = max(worst, abs(a - b))
        vals.append(a)
vals = np.array(vals)
check('sun_coverage_dim is sunCoverageDim at 160 ground points over four frames (the weather map is float32 here)',
      worst < 1e-6, '%.2e' % worst)
check('it spans the clear and the covered ground: 1 - strength .. 1 (0.3 .. 1 at the default 0.7)',
      vals.min() >= 0.3 - 1e-12 and vals.max() <= 1.0 and vals.max() - vals.min() > 0.3,
      'min %.3f max %.3f' % (vals.min(), vals.max()))
sky.update(0.0)
check('strength 0 is always 1; strength 1 reaches 0 under full cover',
      all(sky.sun_coverage_dim(x, y, strength=0.0) == 1.0 for x, y in pts[:10])
      and min(sky.sun_coverage_dim(x, y, strength=1.0) for x, y in pts) < 0.05)
lamp = bpy.data.objects.new('street_lamp', bpy.data.lights.new('street_lamp', 'SPOT'))
sc.collection.objects.link(lamp)
lamp.location = tuple(pts[int(np.argmax(np.ptp(vals.reshape(4, 40), axis=0)))]) + (6.0,)
for f, t, _L in sky.frame_states():
    lamp.data.energy = 800.0 * sky.sun_coverage_dim(lamp.location.x, lamp.location.y)
    lamp.data.keyframe_insert('energy', frame=f)
e = []
for f in (1, 48):
    sc.frame_set(f)
    e.append(lamp.data.energy)
check('keyed through frame_states: a lamp follows the sun behind the drifting clouds',
      abs(e[0] - e[1]) > 1.0, 'energy %.1f at frame 1, %.1f at frame 48' % tuple(e))

# ---- cloud shadow strength and the opt-out ----
check('cloud_shadow_strength outside 0..1 raises',
      raises(lambda: make_sky(sc, camera=cam, cache_dir=cache('x'), cloud_shadow_strength=1.5), ValueError))
sc, cam = fresh(4)
sky = make_sky(sc, camera=cam, cache_dir=cache('optout'), hours=15.0, quality='draft', cloud_shadow_strength=0.5)
check('cloud_shadow_strength is the sky\'s, the shader uniform stays at 1 (the shield\'s own cloud occlusion)',
      sky.cloud_shadow_strength == 0.5 and sky.sky.U['cloudShadowStrength'] == 1.0)
bpy.ops.mesh.primitive_uv_sphere_add(location=(4, 10, 1))
kept = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(location=(-4, 10, 1))
out = bpy.context.object
out[cloud_shadows.OPT_OUT] = 1
caster = cloud_shadows._caster_object(sc, cloud_shadows.EXTENT)            # what bake_and_key makes
twin = cloud_shadows.link_opt_outs(sky, log=lambda *a: None)


def states(coll):
    return {o.name: co.light_linking.link_state for o, co in zip(coll.objects, coll.collection_objects)} if coll else {}


bpy.context.view_layer.update()
ll, tl = sky.sun.light_linking, twin.light_linking if twin else None
check("an eido_noCloudShadow object: the sun lamp's receivers leave it out, the sun's twin lights it alone, and the "
      "twin's blockers leave the caster out",
      twin is not None and states(ll.receiver_collection) == {out.name: 'EXCLUDE'}
      and states(tl.receiver_collection) == {out.name: 'INCLUDE'}
      and states(tl.blocker_collection) == {caster.name: 'EXCLUDE'}, '%s / %s / %s' % (
          states(ll.receiver_collection), states(tl.receiver_collection), tl and states(tl.blocker_collection)))
check("the twin is the sun's own light data, parented with no offset (it carries every key the lamp gets)",
      twin.data == sky.sun.data and twin.parent == sky.sun and twin.matrix_world == sky.sun.matrix_world)
del out[cloud_shadows.OPT_OUT]
twin = cloud_shadows.link_opt_outs(sky, log=lambda *a: None)
check('unmarked again: the twin goes and the sun lamp lights the object again',
      twin is None and cloud_shadows.CLEAR_SUN not in bpy.data.objects and states(ll.receiver_collection) == {})
# strength 0.5 splits the sun: the lamp keeps half and takes the cloud shadow, a twin carries the other half past it
frames = [dict(frame=1, lights=dict(sun_intensity=4.0, sun_color=(1.0, 0.9, 0.8), key_dir=(0.0, 0.6, 0.8))),
          dict(frame=2, lights=dict(sun_intensity=2.0, sun_color=(1.0, 0.8, 0.7), key_dir=(0.0, 0.5, 0.86)))]
sky._key_sun(frames)
share = cloud_shadows.key_clear_share(sky, frames, log=lambda *a: None)
got = []
for f in (1, 2):
    sc.frame_set(f)
    got.append((round(sky.sun.data.energy, 6), round(share.data.energy, 6)))
check('cloud_shadow_strength 0.5: the sun lamp keeps half, the clear-share twin the other half, past the caster',
      share is not None and got == [(2.0, 2.0), (1.0, 1.0)] and share.parent == sky.sun
      and states(share.light_linking.blocker_collection) == {caster.name: 'EXCLUDE'}
      and share.light_linking.receiver_collection is None and tuple(share.data.color) == tuple(sky.sun.data.color), got)
sky.cloud_shadow_strength = 1.0
check('at strength 1 there is no clear-share twin', cloud_shadows.key_clear_share(sky, frames, log=lambda *a: None)
      is None and cloud_shadows.CLEAR_SHARE_SUN not in bpy.data.objects
      and cloud_shadows.CLEAR_SHARE_SUN not in bpy.data.lights)


# the twins keep the sun lamp's own light linking: a painted backdrop the scene's sun does not light (a child
# collection of its receivers) and a prop that casts no sun shadow (its blockers), at strength 0.5 with one opt-out
def child_states(coll):
    return {c.name: cc.light_linking.link_state for c, cc in zip(coll.children, coll.collection_children)} if coll else {}


sc, cam = fresh(4)
sky = make_sky(sc, camera=cam, cache_dir=cache('linked_sun'), hours=15.0, quality='draft', cloud_shadow_strength=0.5,
               weather_fx=False)
bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0, 40, 10))
backdrop = bpy.context.object
painted = bpy.data.collections.new('painted_backdrops')
sc.collection.children.link(painted)
painted.objects.link(backdrop)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2, 8, 0.5))
prop = bpy.context.object
bpy.ops.mesh.primitive_uv_sphere_add(location=(-2, 8, 1))
opt = bpy.context.object
opt[cloud_shadows.OPT_OUT] = 1
own_recv, own_blk = bpy.data.collections.new('scene_sun_receivers'), bpy.data.collections.new('scene_sun_blockers')
own_recv.children.link(painted)
own_recv.collection_children[0].light_linking.link_state = 'EXCLUDE'
own_blk.objects.link(prop)
own_blk.collection_objects[0].light_linking.link_state = 'EXCLUDE'
sky.sun.light_linking.receiver_collection, sky.sun.light_linking.blocker_collection = own_recv, own_blk
caster = cloud_shadows._caster_object(sc, cloud_shadows.EXTENT)
cloud_shadows.link_opt_outs(sky, log=lambda *a: None)
sky._key_sun(frames)
cloud_shadows.key_clear_share(sky, frames, log=lambda *a: None)
clear_sun, share = bpy.data.objects[cloud_shadows.CLEAR_SUN], bpy.data.objects[cloud_shadows.CLEAR_SHARE_SUN]
blk_want = {prop.name: 'EXCLUDE', caster.name: 'EXCLUDE'}
check("the twins' blockers are the sun lamp's own with the caster left out (a prop the scene keeps from casting)",
      states(clear_sun.light_linking.blocker_collection) == blk_want
      and states(share.light_linking.blocker_collection) == blk_want, states(share.light_linking.blocker_collection))
sr = share.light_linking.receiver_collection
check("the clear share lights what the sun lamp lights: its receivers copy the lamp's (the painted backdrop's "
      "collection left out) but not the opt-out's entry, which takes the clear share too",
      sr is not None and child_states(sr) == {'painted_backdrops': 'EXCLUDE'} and states(sr) == {}
      and states(sky.sun.light_linking.receiver_collection) == {opt.name: 'EXCLUDE'}
      and child_states(sky.sun.light_linking.receiver_collection) == {'painted_backdrops': 'EXCLUDE'},
      '%s %s' % (states(sr), child_states(sr)))
del opt[cloud_shadows.OPT_OUT]
cloud_shadows.link_opt_outs(sky, log=lambda *a: None)
sky.cloud_shadow_strength = 1.0
cloud_shadows.key_clear_share(sky, frames, log=lambda *a: None)
check("with no twin left, the twins' collections go and the sun lamp's own linking is as the scene set it",
      cloud_shadows.CASTER_EXCLUDED not in bpy.data.collections
      and cloud_shadows.CLEAR_SHARE_SUN + '_receivers' not in bpy.data.collections
      and states(own_recv) == {} and child_states(own_recv) == {'painted_backdrops': 'EXCLUDE'}
      and states(own_blk) == {prop.name: 'EXCLUDE'})
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
