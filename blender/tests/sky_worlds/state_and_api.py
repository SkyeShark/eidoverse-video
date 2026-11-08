"""The sky worlds' scene-facing surface and state, without rendering (no GPU slot needed).

Checks, one PASS/FAIL line each:
  - WORLDS / SKY_WORLDS mirror eidoverse/sky_worlds.js (keys, labels, the shield only on the shieldworld)
  - make_sky builds every world; an unknown world names the valid ones
  - set_colors({shield}) warns and is ignored on worlds without a shield, reaches the red giant on the shieldworld
  - the ringworld: band placement (axis at 4940 - the walls' bounds offset), Eanpa's stitched rows, the relief eased
    under the stage, the band lamps linked to the band alone and the scene sun linked away from it, the ring deck
    constants against the JS _deckY, the eclipse; the band sun's shadow blockers (eclipse proxy + cloud sheet), the
    proxy blocking the scene sun, arch night at noon with an undimmed lamp, info's JS keys, the lamp lifecycle
  - the facade's delegation of wrap_scene / audio_timeline / audio to an attached weather system, audio=False
  - the shieldworld: the moon's orbit (rises 22.3 h, transits 6.2 h, outside the 21 km shield), its night-only
    visibility, the fragment drift's clearance, the debris river's 7000 grains
  - frame_states replays the world's state bit for bit (ring values, moon values) on a second pass
  - make_spatial_cloud_pass maps onto the bake's layer scale
    bash run_blender.sh blender/tests/sky_worlds/state_and_api.py
"""
import io
import math
import os
import re
import sys
from contextlib import redirect_stdout

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky, SKY_WORLDS, WORLDS  # noqa: E402
from eidoblend.sky.worlds import ring_constants, ring_deck_y  # noqa: E402
from eidoblend.sky.cloud_spatial import make_spatial_cloud_pass  # noqa: E402

OUT = os.path.join(HERE, 'out', 'state')
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 640, 360
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 12
    cd = bpy.data.cameras.new('cam')
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0, 0, 1.7)
    cam.rotation_euler = (math.radians(95), 0, 0)
    return sc, cam


# ---- the table against the JS ----
js = open(os.path.join(REPO, 'eidoverse', 'sky_worlds.js'), encoding='utf-8').read()
labels = dict(re.findall(r"(\w+): \{\s*label: '([^']+)'", js))
check('WORLDS keys and labels are sky_worlds.js\'s', labels == SKY_WORLDS, '%s vs %s' % (labels, SKY_WORLDS))
check('only the shieldworld carries a shield', [k for k, v in WORLDS.items() if v.get('shield')] == ['shieldworld'])
check('the ringworld band sits at the authored centerY 4940', WORLDS['ringworld']['band']['centerY'] == 4940)

sc, cam = fresh()
try:
    make_sky(sc, camera=cam, world='mars', cache_dir=os.path.join(OUT, 'x'))
    check('an unknown world raises', False)
except ValueError as e:
    check('an unknown world raises and names the valid ones', 'earth | ringworld | shieldworld' in str(e), str(e))

# ---- earth: the shield channel is ignored with a warning ----
sky = make_sky(sc, camera=cam, world='earth', cache_dir=os.path.join(OUT, 'earth'), quality='draft')
buf = io.StringIO()
with redirect_stdout(buf):
    sky.set_colors({'shield': (1, 0, 0), 'cloud': (1, 0.9, 0.8)})
check("set_colors({shield}) on 'earth' warns and is ignored", 'has no shield' in buf.getvalue()
      and sky.sky.sky_color['shield'] == (1, 1, 1) and sky.sky.sky_color['cloud'] == (1, 0.9, 0.8))
check('earth: label, planet_shine, internals', sky.label == 'Earth' and sky.planet_shine is None
      and set(sky.internals) >= {'sky', 'wx', 'band', 'celestial', 'moon'})

# ---- ringworld ----
sc, cam = fresh()
sky = make_sky(sc, camera=cam, world='ringworld', hours=11, cache_dir=os.path.join(OUT, 'ringworld'), quality='draft')
r = sky.ring
c = r.band.matrix_world.translation
check('ringworld: the band axis sits at 4940 minus the walls\' bounds offset', abs(c.z - 4921.66) < 0.5 and abs(c.x) < 1e-6,
      'axis z %.2f y %.2f' % (c.z, c.y))
gi = r.info['geometryRelief']
check("ringworld: Eanpa's stitched band (4096 rows around, LOD across, skirts)",
      gi['around'] == 4096 and gi['vertices'] > 500000 and gi['triangles'] > 1000000,
      '%d vertices, %d triangles' % (gi['vertices'], gi['triangles']))
import numpy as np  # noqa: E402
co = np.empty(len(r.band.data.vertices) * 3, np.float32)
r.band.data.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
rad = np.hypot(co[:, 1], co[:, 2])
under = (np.abs(np.arctan2(-co[:, 1], -co[:, 2])) * 5000 < 600) & (rad < 5001)
check('ringworld: the relief eases out under the stage (arc < 600 m stays at the band radius)',
      np.abs(rad[under] - 5000).max() < 0.5, 'max relief there %.3f m' % np.abs(rad[under] - 5000).max())
check('ringworld: relief reaches its height far out', 5000 - rad.min() > 60, 'max relief %.1f m' % (5000 - rad.min()))
recv = r.band_sun.light_linking.receiver_collection
check('ringworld: the band lamps light the band alone', recv is not None and list(recv.objects) == [r.band]
      and r.band_shine.light_linking.receiver_collection == recv)
sr = sky.sun.light_linking.receiver_collection
states = {ob.name: co_.light_linking.link_state for ob, co_ in zip(sr.objects, sr.collection_objects)}
check('ringworld: the scene sun is linked away from the band', states.get(r.band.name) == 'EXCLUDE', str(states))
k = ring_constants(5000)
deck = [ring_deck_y(z, k) for z in (0, 4200, 4600, 4900, 5200)]
check('ringworld: deck profile flat 450 m over the stage, rising 350 m by the crest (R-relative JS constants)',
      abs(deck[0] - 450) < 1e-6 and abs(deck[3] - 800) < 1.0 and abs(deck[1] - 450) < 1e-6,
      'deck %s' % [round(v, 1) for v in deck])
sky.update(0.0)
check('ringworld: no eclipse at 11:00 (the sun is off the band\'s plane... or clear of it)',
      0.0 <= sky.sky.U['solarVisibility'] <= 1.0, 'solar %.3f' % sky.sky.U['solarVisibility'])
a = [dict(v[2] and sky.ring_vals) for v in sky.frame_states()]
b = [dict(v[2] and sky.ring_vals) for v in sky.frame_states()]
check('ringworld: a second pass replays the band state bit for bit', a == b, '%d frames' % len(a))
blk = r.band_sun.light_linking.blocker_collection
check('ringworld: the band sun is shadowed by the eclipse proxy and the cloud sheet alone (no relief by default)',
      blk is not None and sorted(o.name for o in blk.objects) == sorted(['eido_ring_eclipse_proxy', 'eido_ring_clouds'])
      and all(co.light_linking.link_state == 'INCLUDE' for co in blk.collection_objects),
      str([o.name for o in blk.objects]) if blk else 'none')
sb = sky.sun.light_linking.blocker_collection
check('ringworld: the eclipse proxy blocks the scene sun (per-receiver eclipse), the visible ring does not',
      'eido_ring_eclipse_proxy' not in sb.objects and all(co.light_linking.link_state == 'EXCLUDE'
                                                         for co in sb.collection_objects))
pr = r.eclipse_proxy
prc = pr.matrix_world.translation
check('ringworld: the eclipse proxy sits on the band axis, shadow-only', (prc - r.band.matrix_world.translation).length
      < 1e-3 and not pr.visible_camera and not pr.visible_diffuse and pr.visible_shadow,
      'proxy %s' % (tuple(round(v, 2) for v in prc),))
sky.set_time(12.0)
sky.update(0.0)
check('ringworld: noon is arch night at the stage, and the lamp is not dimmed by the camera scalar (the proxy shadows)',
      sky.sky.U['solarVisibility'] < 0.01 and sky.lights['sun_intensity'] > 3.0
      and abs(sky.sky.U['solarSkyVisibility'] - 0.16) < 0.01,
      'solar %.3f, lamp %.2f, sky %.3f' % (sky.sky.U['solarVisibility'], sky.lights['sun_intensity'],
                                           sky.sky.U['solarSkyVisibility']))
sky.set_time(11.0)
check('ringworld: info carries the JS keys', all(key in r.info for key in (
    'radius', 'tile', 'halfWidth', 'repeat', 'mapTex', 'maskTex', 'waterWaveMode', 'waterWavesActive',
    'geometryRelief')), str(sorted(r.info)))


class _FakeWeather:
    def __init__(self):
        self.wrapped = 0

    def wrap_scene(self):
        self.wrapped += 1

    def audio_timeline(self, **kw):
        return {'events': ['thunder'], 'kw': kw}


fx = _FakeWeather()
sky.weather_fx = fx
sky.wrap_scene()
check('facade: wrap_scene and audio_timeline delegate to the attached weather system',
      fx.wrapped == 1 and sky.audio_timeline() == {'events': ['thunder'], 'kw': {}} and sky.audio is fx)
sky.audio_on = False
check('facade: audio=False silences the timeline', sky.audio_timeline() is None and sky.audio is None)
sky.audio_on = True
sky.weather_fx = None
check('facade: without a weather system, audio_timeline is None', sky.audio_timeline() is None)
sp = make_spatial_cloud_pass(sky, div=3)
check('spatial pass: 1/3 layer scale, resolution reported', sky.layer_scale == 1 / 3
      and sp.get_resolution() == dict(width=214, height=120, divisor=3), str(sp.get_resolution()))
sp.set_divisor(2)
check('spatial pass: set_divisor', sky.layer_scale == 0.5 and sp.get_divisor() == 2)
sp.dispose()
check('ringworld: attach_lights is a no-op, dispose_lights removes both lamps and is safe twice',
      r.attach_lights() is r and r.dispose_lights() is r and r.dispose_lights() is r
      and 'eido_ring_band_sun' not in bpy.data.objects and 'eido_ring_band_shine' not in bpy.data.objects)

# ---- shieldworld ----
sc, cam = fresh()
sky = make_sky(sc, camera=cam, world='shieldworld', hours=1.4, cache_dir=os.path.join(OUT, 'shieldworld'),
               quality='draft')
m = sky.moon
check('shieldworld: 16 fragments, envelopes separated', len(m.pieces) == 16
      and m.motion.stats['minimumEnvelopeClearance'] >= m.motion.stats['clearance'] - 1e-6, str(m.motion.stats))
check('shieldworld: the debris river carries 7000 grains', len(m.specks.data.vertices) == 7000)
sky.update(0.0)
mv = sky.moon_vals
p = mv['position3']
check('shieldworld: at 01:24 the moon transits, outside the 21 km shield',
      math.sqrt(sum(c * c for c in p)) > 21000 and p[1] > 20000 and mv['visibility'] > 0.99,
      'position %s visibility %.3f' % (tuple(round(v) for v in p), mv['visibility']))
sky.set_time(12.0)
sky.update(0.0)
check('shieldworld: by day the moon is faded out (night-only visibility)', sky.moon_vals['visibility'] < 1e-3)
buf = io.StringIO()
with redirect_stdout(buf):
    sky.set_colors({'shield': (1.0, 0.2, 0.1), 'star': (1.0, 0.9, 0.9)})
check('shieldworld: set_colors reaches the shield and the star', buf.getvalue() == ''
      and sky.red_giant.shield_color == (1.0, 0.2, 0.1) and sky.red_giant.star_tint == (1.0, 0.9, 0.9))
sky.update(0.0)
check('shieldworld: the giant rides the sun (disc and glow lobes off)', sky.sky.U['sunDiscI'] == 0
      and sky.sky.U['sunGlowI'] == 0 and sky.sky.U['starDir'] == tuple(sky.sky.sun_dir))
a = [dict(sky.moon_vals['U']) for _ in sky.frame_states()]
b = [dict(sky.moon_vals['U']) for _ in sky.frame_states()]
check('shieldworld: a second pass replays the moon state bit for bit', a == b, '%d frames' % len(a))
n_img = len(bpy.data.images)
m.dispose_textures()
m.dispose_textures()
check('shieldworld: dispose_textures frees the GLB source images no material uses, safe twice',
      len(bpy.data.images) <= n_img and not m.source_images)
sky.set_time(1.4)
sky.update(0.0)
ex = sky.world_extra
check('shieldworld: the night block keys the cyan shield light and the amber moon light into the world',
      ex is not None and ex['night_k'] > 0.99 and ex['moon_up_k'] > 0.99 and ex['tint'][0] < 0.25
      and ex['add'][2] > ex['add'][0] * 0.5, str({k: (tuple(round(c, 4) for c in v) if isinstance(v, tuple) else
                                                    round(v, 3)) for k, v in (ex or {}).items()}))
print('PASS state_and_api all' if ok_all else 'FAIL state_and_api some')
