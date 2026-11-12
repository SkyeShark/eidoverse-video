"""make_sky's engine options and celestial bodies, rendered: what each one does on screen.

    bash run_blender.sh blender/tests/sky/sky_options_render.py [--parts planet,ring,storm,shadowmarch,textures,
        celestial,shadows] [--res 960x540] [--samples 16] [--quality film]

Every part writes its renders and a labelled sheet (sheet_<part>.png) to blender/tests/sky/out/options/, and prints
one PASS/FAIL line per numeric check (a PASS is not a look: open the sheets).
  planet       earthRadius: a cumulus deck on Earth (6371 km), a 10 km and a 3 km planet; as the planet shrinks the
               deck curves down to the horizon, so the low clouds come near (big cells down to the horizon, where
               Earth's flatten into far streaks)
  ring         ringCloudBase / ringCloudThick: the ringworld's deck along the arc, as authored and lifted to 900 m
               and 500 m thick
  storm        stormSamples 4 / 12 / 32 under the darkstorm canopy, looking low where the rays graze the storm layer:
               12 (the JS's) lands near 32, 4 smears a speckled band along the horizon (sheet_storm_horizon.png
               lifts that band three times for the eye)
  shadowmarch  cloudShadowSamples 32 / 64: the cloud-shadow maps of one cumulus sky, side by side (GPU, no render)
  textures     textures={'stars', 'moon'}: Earth at midnight, its own Tycho stars and moon against a scene's own star
               map (generated here: a magenta-and-teal band of dense stars) and the ringworld's rock giant as the moon
  celestial    celestial=: a red giant without its shield as Earth's sun near sunset and in the ringworld's morning
               sky, against their own suns; a body of the scene's own (a banded gas giant) in an Earth afternoon
  shadows      cloud_shadow_strength 1 and 0.5 against shadows=False, two white spheres in one cloud shadow, the right
               one marked eido_noCloudShadow, with a pillar throwing its ordinary shadow across it
"""
import argparse
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky import palette as P  # noqa: E402
from eidoblend.sky import cloud_shadows  # noqa: E402
from eidoblend.sky.redgiant import make_red_giant  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--parts', default='planet,ring,storm,shadowmarch,textures,celestial,shadows')
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--quality', default='film')
ap.add_argument('--exposure', type=float, default=0.6)
args = ap.parse_args(argv)
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'options')
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  (' + str(detail) + ')') if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


def material(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def sphere(name, loc, radius, mat):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=radius)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    return ob


def stage(ground=True, lens=24.0):
    """A fresh scene: an 8 km dull ground, a camera, EEVEE with ray tracing and fast GI, AgX."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.eevee.use_raytracing = True
    sc.eevee.use_fast_gi = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = args.exposure
    sc.render.fps = 24
    sc.frame_start = sc.frame_end = 1
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    if ground:
        me = bpy.data.meshes.new('ground')
        me.from_pydata([(-4000, -4000, 0), (4000, -4000, 0), (4000, 4000, 0), (-4000, 4000, 0)], [], [(0, 1, 2, 3)])
        me.materials.append(material('ground', (0.10, 0.11, 0.07), 0.9))
        sc.collection.objects.link(bpy.data.objects.new('ground', me))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = lens
    cam.data.clip_end = 20000.0
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def aim(cam, loc, d=None, yaw=None, pitch=0.0):
    """Point the camera from loc along Blender direction d, or at a heading yaw (deg from +y toward -x) and pitch."""
    cam.location = loc
    if d is None:
        y, p = math.radians(yaw), math.radians(pitch)
        d = (-math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), math.sin(p))
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = Vector(d).normalized().to_track_quat('-Z', 'Y')


def shot(sc, path, log=False, **kw):
    """make_sky with these options, a one-frame bake, a render; returns (sky, path)."""
    t0 = time.time()
    sky = make_sky(sc, camera=sc.camera, cache_dir=os.path.join(OUT, '_cache', os.path.basename(path)[:-4]),
                   quality=args.quality, **kw)
    sky.bake(1, 1, log=print if log else (lambda *a: None))
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[options] %s (%.1fs)' % (os.path.basename(path), time.time() - t0), flush=True)
    return sky, path


def img(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGB')).astype(np.float64) / 255.0


def sheet(name, items, cols=2):
    """items: [(path, label)] -> out/options/sheet_<name>.png."""
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert('RGB') for p, _ in items]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    out = Image.new('RGB', (w * cols, h * rows), (0, 0, 0))
    for i, (im, (_p, label)) in enumerate(zip(ims, items)):
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 8 + 7 * len(label), 20), fill=(0, 0, 0))
        d.text((6, 4), label, fill=(255, 255, 255))
        out.paste(im, ((i % cols) * w, (i // cols) * h))
    p = os.path.join(OUT, 'sheet_%s.png' % name)
    out.save(p)
    print('[options] sheet', p, flush=True)


def heading_away_from_sun(sky, offset):
    sd = sky.sun_dir
    return math.degrees(math.atan2(-sd[0], sd[1])) + offset


parts = args.parts.split(',')

# ---- planet: earthRadius ----
if 'planet' in parts:
    items, skies = [], []
    for tag, R in (('earth_6371km', None), ('planet_10km', 10000.0), ('planet_3km', 3000.0)):
        sc, cam = stage(lens=18.0)
        kw = dict(hours=15.0, clouds='cumulus')
        if R:
            kw['earthRadius'] = R
        probe = make_sky(sc, camera=cam, cache_dir=os.path.join(OUT, '_cache', 'probe'), quality='draft', shadows=False,
                         weather_fx=False, **kw)
        yaw = heading_away_from_sun(probe, 100.0)
        bpy.data.objects.remove(probe.sun, do_unlink=True)
        aim(cam, (0, 0, 1.7), yaw=yaw, pitch=16.0)
        sky, p = shot(sc, os.path.join(OUT, 'planet_%s.png' % tag), shadows=False, **kw)
        skies.append(img(p)[:int(H * 0.70)])                    # the sky, from the horizon up
        items.append((p, '%s: earthRadius %s' % (tag, R or 'default')))
    d10, d3 = (float(np.abs(s - skies[0]).mean()) for s in skies[1:])
    # on a small planet the deck curves down to the horizon, so the low clouds come near: big cells down to the
    # horizon where Earth's flatten into far streaks; the change grows as the planet shrinks
    check('earthRadius: the deck changes with the planet, more for the smaller one (10 km, 3 km against Earth)',
          d3 > d10 > 0.002, 'sky mean |diff| %.4f, %.4f' % (d10, d3))
    sheet('planet', items, cols=3)

# ---- ring: the deck's shape ----
if 'ring' in parts:
    items, imgs = [], []
    for tag, kw in (('authored', {}), ('lifted_900m_500m', dict(ringCloudBase=900.0, ringCloudThick=500.0))):
        sc, cam = stage(lens=20.0)
        aim(cam, (0, 0, 1.7), yaw=0.0, pitch=12.0)             # along the ring (+y), where the deck climbs the arc
        sky, p = shot(sc, os.path.join(OUT, 'ring_%s.png' % tag), world='ringworld', hours=10.0, clouds='cumulus',
                      weather_fx=False, **kw)
        imgs.append(img(p))
        items.append((p, 'ringworld deck %s' % tag))
    diff = float(np.abs(imgs[0] - imgs[1]).mean())
    check('the lifted, thicker deck changes the ringworld sky', diff > 0.004, 'mean |diff| %.4f' % diff)
    sheet('ring', items)

# ---- storm: stormSamples ----
if 'storm' in parts:
    items, imgs = [], []
    for n in (4, 12, 32):
        sc, cam = stage(lens=35.0)
        aim(cam, (0, 0, 1.7), yaw=30.0, pitch=7.0)                # low: grazing rays, where the step count shows
        sky, p = shot(sc, os.path.join(OUT, 'storm_samples_%02d.png' % n), hours=15.0, weather='darkstorm',
                      stormSamples=n, weather_fx=False, shadows=False)
        imgs.append(img(p))
        items.append((p, 'darkstorm, stormSamples %d' % n))
    d4, d12 = (float(np.abs(i - imgs[2]).mean()) for i in imgs[:2])
    check('stormSamples: 12 (the JS default) lands nearer 32 than 4 does', d12 < d4 and d4 > 0.0005,
          'mean |diff| against 32: 4 -> %.4f, 12 -> %.4f' % (d4, d12))
    sheet('storm', items, cols=3)
    # the horizon band, lifted three times for the eye (the storm is near black): where the step count shows
    from PIL import Image, ImageDraw
    y0, y1 = int(H * 0.28), int(H * 0.69)
    band = Image.new('RGB', (W, (y1 - y0) * 3))
    for k, (a_, n) in enumerate(zip(imgs, (4, 12, 32))):
        im = Image.fromarray((np.clip((a_[y0:y1] - 0.1) * 3.0, 0, 1) * 255).astype(np.uint8))
        ImageDraw.Draw(im).text((6, 4), 'stormSamples %d, lifted x3' % n, fill=(255, 255, 0))
        band.paste(im, (0, k * (y1 - y0)))
    band.save(os.path.join(OUT, 'sheet_storm_horizon.png'))

# ---- shadowmarch: cloudShadowSamples ----
if 'shadowmarch' in parts:
    maps = []
    for n in (32, 64):
        sc, cam = stage()
        aim(cam, (0, 0, 1.7), yaw=0.0, pitch=5.0)
        sky = make_sky(sc, camera=cam, hours=15.0, clouds='cumulus', cache_dir=os.path.join(OUT, '_cache', 'march'),
                       quality=args.quality, cloudShadowSamples=n, weather_fx=False)
        for _f, _t, _L in sky.frame_states(1, 1):
            org = P.blender_to_three(tuple(cam.location))
            maps.append(sky.baker().shadow_map(sky.sky.U, 512, (org[0], 0.0, org[2]), 6144.0)[..., 0])
    d = np.abs(maps[0] - maps[1])
    check('cloudShadowSamples 32 / 64: the same shadows, the finer march differs only at the edges',
          0.0 < float(d.mean()) < 0.02 and float(maps[1].min()) < 0.6,
          'mean |diff| %.4f, max %.3f, darkest %.2f' % (d.mean(), d.max(), maps[1].min()))
    from PIL import Image, ImageDraw
    pair = np.concatenate([maps[0][::-1], np.ones((512, 8)), maps[1][::-1]], axis=1)
    im = Image.fromarray((np.clip(pair, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)).convert('RGB')
    d = ImageDraw.Draw(im)
    for x0, n in ((0, 32), (520, 64)):
        label = 'cloud-shadow map, cloudShadowSamples %d (6144 m square)' % n
        d.rectangle((x0, 0, x0 + 8 + 6 * len(label), 18), fill=(0, 0, 0))
        d.text((x0 + 4, 3), label, fill=(255, 255, 0))
    im.save(os.path.join(OUT, 'sheet_shadowmarch.png'))

# ---- textures: the scene's own star and moon maps ----
if 'textures' in parts:
    from PIL import Image
    rng = np.random.default_rng(11)
    sw, sh = 2048, 1024
    stars = np.zeros((sh, sw, 3), np.float64)
    v, u = np.mgrid[0:sh, 0:sw] / np.array([sh, sw])[:, None, None]
    band = np.exp(-((v - 0.5 - 0.22 * np.sin(u * 2 * np.pi)) / 0.07) ** 2)          # a winding band across the sky
    tint = np.stack([0.9 * band + 0.1, 0.25 * band + 0.55 * band * (u > 0.5), 0.8 * band], axis=-1)
    n = 40000
    ys, xs = rng.integers(0, sh, n), rng.integers(0, sw, n)
    keep = rng.random(n) < (0.12 + 0.88 * band[ys, xs])                              # dense in the band
    bright = rng.random(n)[keep] ** 2 * 0.8 + 0.2
    stars[ys[keep], xs[keep]] = tint[ys[keep], xs[keep]] * bright[:, None] * 2.0 + bright[:, None] * 0.5
    stars += tint * 0.45 * band[..., None]                                          # the band's own glow
    star_png = os.path.join(OUT, 'scene_starmap.png')
    Image.fromarray((np.clip(stars, 0, 1) * 255).astype(np.uint8)).save(star_png)
    items, imgs = [], []
    # the moon at 6 degrees (moonAngularDeg) so the map reads: at Earth's 0.55 the disc is a faint glow (its edge
    # smoothstep spans 0.0004 in cos, about 2.4 degrees, as in the JS)
    for tag, tex, lens, target in (('stars_tycho', None, 16.0, 'up'), ('stars_scene', {'stars': star_png}, 16.0, 'up'),
                                   ('moon_luna', None, 60.0, 'moon'),
                                   ('moon_rock_giant', {'moon': 'celestial/rock_giant.png'}, 60.0, 'moon')):
        sc, cam = stage(lens=lens)
        probe = make_sky(sc, camera=cam, hours=0.0, clouds='clear', cache_dir=os.path.join(OUT, '_cache', 'probe'),
                         quality='draft', shadows=False, weather_fx=False)
        md = probe.moon_dir
        bpy.data.objects.remove(probe.sun, do_unlink=True)
        if target == 'moon':
            aim(cam, (0, 0, 1.7), d=md)
        else:
            # 25 degrees up toward Blender +y: the band of the scene's map crests there, 40 degrees up (the sky reads
            # its equirect with v = acos(three y) / pi, the image's bottom row at the zenith)
            aim(cam, (0, 0, 1.7), d=(0.0, 1.0, math.tan(math.radians(25.0))))
        sky, p = shot(sc, os.path.join(OUT, 'textures_%s.png' % tag), hours=0.0, clouds='clear', textures=tex,
                      weather_fx=False, **({'moonAngularDeg': 6.0} if target == 'moon' else {}))
        imgs.append(img(p))
        items.append((p, '%s%s' % (tag, '' if tex is None else ' (textures=)')))
    ds = float(np.abs(imgs[0] - imgs[1]).mean())
    dm = float(np.abs(imgs[2] - imgs[3]).mean())
    check("textures: the scene's star map replaces the Tycho stars, and its moon map the moon",
          ds > 0.002 and dm > 0.002, 'stars mean |diff| %.4f, moon %.4f' % (ds, dm))
    sheet('textures', items)

# ---- celestial bodies ----
PLANET_DIR3 = (0.30, 0.35, -0.88)


class GasGiant:
    """A body of the scene's own (make_sky(celestial=...)): a banded gas giant hung at a fixed direction, lit by the
    sky's sun. Only celestial_glsl() is required; it reads the sky shader's uniforms (uSunDir, uHorizon, uZenith,
    uSunColor), in three.js space. A lit body that is not a star adds its light to the air in front of it, the sky's
    own gradient (as the sky's moon does in sky.glsl's bgBody), so its night side takes the sky's colour by day and
    hides the stars behind it by night."""

    def __init__(self, direction3=PLANET_DIR3, radius_deg=7.0):
        n = math.sqrt(sum(c * c for c in direction3))
        self.d = tuple(c / n for c in direction3)
        self.cos_r = math.cos(math.radians(radius_deg))

    def celestial_glsl(self):
        return '''
const vec3 GG_DIR = vec3(%r, %r, %r);
const float GG_COS = %r;
vec3 celestial(vec3 dir, vec3 col) {
    float c = dot(dir, GG_DIR);
    if (c < GG_COS - 0.002) return col;
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), GG_DIR));
    vec3 up = cross(GG_DIR, right);
    float sinR = sqrt(1.0 - GG_COS * GG_COS);
    vec2 q = vec2(dot(dir, right), dot(dir, up)) / sinR;
    float r = length(q);
    vec3 n = normalize(right * q.x + up * q.y - GG_DIR * sqrt(max(1.0 - r * r, 0.0)));
    float lat = q.y * 0.94 + q.x * 0.34;
    float bands = 0.5 + 0.5 * sin(lat * 19.0 + sin(q.x * 4.0 + lat * 7.0) * 0.8);
    vec3 albedo = mix(vec3(0.62, 0.40, 0.24), vec3(0.93, 0.84, 0.68), bands);
    float upK = pow(clamp(dir.y * 1.35 + 0.02, 0.0, 1.0), 0.55);
    vec3 air = mix(uHorizon, uZenith, upK) + uSunColor * pow(max(dot(dir, uSunDir), 0.0), 6.0) * 0.35 * (1.0 - upK);
    vec3 planet = air + albedo * max(dot(n, uSunDir), 0.0) * 1.4;
    return mix(col, planet, 1.0 - smoothstep(0.985, 1.0, r));
}
''' % (self.d + (self.cos_r,))


if 'celestial' in parts:
    items = []
    pairs = []
    for world, hours, lens in (('earth', 17.2, 24.0), ('ringworld', 9.5, 24.0)):
        row = []
        for tag, cel in (('own_sun', None), ('red_giant', 'rg')):
            sc, cam = stage(lens=lens)
            probe = make_sky(sc, camera=cam, world='earth', hours=hours, clouds='clear', quality='draft',
                             cache_dir=os.path.join(OUT, '_cache', 'probe'), shadows=False, weather_fx=False,
                             **({'noonAzimuth': math.pi / 2} if world == 'ringworld' else {}))
            sd = probe.sun_dir
            bpy.data.objects.remove(probe.sun, do_unlink=True)
            aim(cam, (0, 0, 1.7), d=(sd[0], sd[1], max(sd[2], 0.06) + 0.04))
            sky, p = shot(sc, os.path.join(OUT, 'celestial_%s_%s.png' % (world, tag)), world=world, hours=hours,
                          clouds='cumulus', weather_fx=False,
                          celestial=make_red_giant({'shield': False}) if cel else None)
            row.append(img(p))
            items.append((p, '%s %s' % (world, 'red giant (no shield)' if cel else 'its own sun')))
        pairs.append(float(np.abs(row[0] - row[1]).mean()))
    check('a red giant in the Earth and the ringworld skies replaces their suns on screen',
          min(pairs) > 0.01, 'mean |diff| earth %.3f, ringworld %.3f' % tuple(pairs))
    sc, cam = stage(lens=35.0)
    aim(cam, (0, 0, 1.7), d=P.three_to_blender(GasGiant().d))
    sky, p = shot(sc, os.path.join(OUT, 'celestial_earth_gas_giant.png'), hours=15.0, clouds='cirrus',
                  celestial=GasGiant(), weather_fx=False)
    a = img(p)
    cx, cy = W // 2, H // 2
    centre, ring = a[cy - 20:cy + 20, cx - 20:cx + 20].mean(axis=(0, 1)), a[cy - 20:cy + 20, 20:60].mean(axis=(0, 1))
    check('a body of the scene\'s own shows where it hangs (a warm disc at the frame centre, the sky at the side)',
          centre[0] - centre[2] > ring[0] - ring[2] + 0.05 and abs(float((centre - ring).mean())) > 0.03,
          'centre %s, side %s' % (np.round(centre, 3), np.round(ring, 3)))
    # the disc, 7 degrees in radius about the frame centre; its night side shows the sky's own colour by day
    yy, xx = np.mgrid[0:H, 0:W]
    rpx = math.tan(math.radians(7.0)) / math.tan(cam.data.angle_x / 2.0) * W / 2.0
    disc = (xx + 0.5 - W / 2.0) ** 2 + (yy + 0.5 - H / 2.0) ** 2 < (0.95 * rpx) ** 2
    darkest_disc, darkest_side = float(a[disc].mean(axis=1).min()), float(a[cy - 60:cy + 60, 10:80].mean(axis=2).min())
    check("its night side takes the sky's colour, as a body seen through the air does (nothing in the disc darker than "
          'the sky beside it)', darkest_disc > darkest_side - 0.04,
          'darkest in the disc %.3f, beside it %.3f' % (darkest_disc, darkest_side))
    items.append((p, 'earth with a gas giant of its own (celestial=)'))
    sheet('celestial', items)

# ---- shadows: strength and the opt-out ----
if 'shadows' in parts:
    sc, cam = stage(lens=35.0)
    probe = make_sky(sc, camera=cam, hours=16.0, clouds='cumulus', quality='draft',
                     cache_dir=os.path.join(OUT, '_cache', 'probe'), weather_fx=False)
    bk = probe.baker()
    for _f, _t, _L in probe.frame_states(1, 1):
        U = dict(probe.sky.U)
    tmap = bk.shadow_map(U, 512, (0.0, 0.0, 0.0), 6144.0)[..., 0]
    sd = probe.sun_dir
    bpy.data.objects.remove(probe.sun, do_unlink=True)
    # a shadowed ground spot 60-400 m out with shadowed ground around it (pixel j, i -> three x, z)
    best = None
    for j in range(8, 504, 2):
        for i in range(8, 504, 2):
            x3, z3 = (i + 0.5) / 512 * 6144 - 3072, -((j + 0.5) / 512 * 6144 - 3072)
            dist = math.hypot(x3, z3)
            if 60 < dist < 400 and tmap[j - 2:j + 3, i - 2:i + 3].max() < 0.35:
                if best is None or tmap[j, i] < best[0]:
                    best = (float(tmap[j, i]), x3, z3)
    check('a cloud shadow lies near the stage (for the spheres to stand in)', best is not None,
          best and 'transmittance %.2f at (%.0f, %.0f)' % (best[0], best[1], -best[2]))
    if best:
        spot = Vector((best[1], -best[2], 0.0))                     # the Blender ground point
        s = Vector((sd[0], sd[1], 0.0)).normalized()                 # toward the sun, on the ground
        q = Vector((-s.y, s.x, 0.0))                                 # across the sun: the spheres never shade each other
        white = material('white', (0.8, 0.8, 0.8), 0.6)
        a_ob = sphere('sphere_shadowed', tuple(spot - q * 1.8 + Vector((0, 0, 1.0))), 1.0, white)
        b_ob = sphere('sphere_no_cloud_shadow', tuple(spot + q * 1.8 + Vector((0, 0, 1.0))), 1.0, white)
        b_ob[cloud_shadows.OPT_OUT] = 1
        # a pillar between the sun and the marked sphere: its ordinary shadow must still fall across it
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=tuple(b_ob.location + s * 3.0 + Vector((0, 0, 1.0))))
        pillar = bpy.context.object
        pillar.scale = (0.25, 0.25, 4.0)
        pillar.data.materials.append(material('pillar', (0.3, 0.3, 0.3), 0.8))
        eye = spot + (s * 0.6 + q * 0.8) * 13.0 + Vector((0.0, 0.0, 3.0))     # on the sun's side: the lit flanks
        aim(cam, tuple(eye), d=tuple(spot + Vector((0, 0, 0.8)) - eye))
        g_pt = spot + s * 4.0 + q * 2.5                              # sunlit ground, clear of every object's shadow
        sc.view_layers[0].update()
        renders, sun_ob = {}, None
        for tag, kw in (('no_cloud_shadows', dict(shadows=False)), ('strength_1', {}),
                        ('strength_0.5', dict(cloud_shadow_strength=0.5))):
            sky, p = shot(sc, os.path.join(OUT, 'shadows_%s.png' % tag), hours=16.0, clouds='cumulus',
                          weather_fx=False, sun=sun_ob, **kw)
            sun_ob = sky.sun                                          # one sun lamp, re-keyed by each bake
            renders[tag] = (img(p), p)

        def patch(ob, a):
            """The sphere's sun-facing flank, in pixels: its centre pushed half a radius toward the sun."""
            c = world_to_camera_view(sc, cam, ob.location + Vector((sd[0], sd[1], sd[2])).normalized() * 0.5)
            px, py = int(c.x * W), int((1 - c.y) * H)
            return float(a[py - 4:py + 5, px - 4:px + 5].mean())

        gp = world_to_camera_view(sc, cam, g_pt)
        gx, gy = int(gp.x * W), int((1 - gp.y) * H)
        v = {t: (patch(a_ob, r[0]), patch(b_ob, r[0]), float(r[0][gy - 6:gy + 7, gx - 6:gx + 7].mean()))
             for t, r in renders.items()}
        print('[options] lit flank (shadowed sphere, opted-out sphere, ground): %s'
              % {t: tuple(round(x, 3) for x in vv) for t, vv in v.items()}, flush=True)
        off, s1, s5 = v['no_cloud_shadows'], v['strength_1'], v['strength_0.5']
        check('the cloud shadow darkens the plain sphere and the ground', s1[0] < off[0] - 0.05 and s1[2] < off[2] - 0.03)
        check('eido_noCloudShadow: the marked sphere keeps the sun as with no cloud overhead', abs(s1[1] - off[1]) < 0.02,
              '%.3f against %.3f' % (s1[1], off[1]))
        check('cloud_shadow_strength 0.5: lighter than full strength, darker than none (sphere and ground)',
              s1[0] < s5[0] < off[0] and s1[2] < s5[2] < off[2])
        sheet('shadows', [(renders[t][1], label) for t, label in (
            ('no_cloud_shadows', 'shadows=False'), ('strength_1', 'cloud shadows (right sphere: eido_noCloudShadow)'),
            ('strength_0.5', 'cloud_shadow_strength=0.5'))], cols=3)
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
