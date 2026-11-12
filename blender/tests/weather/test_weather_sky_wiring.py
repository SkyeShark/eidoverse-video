"""make_sky's own weather and the weather without a sky, without rendering (no GPU slot needed).

sky_worlds.js builds makeWeatherSystem inside makeSky and wraps the scene; make_sky(weather_fx=None) builds
eidoblend.weather's system as soon as its direction names a weather that rains, strikes or wets, and its bake() hands
over to the weather's. makeWeatherSystem({scene, sky: null}) runs with every sky access guarded:
make_weather_system(scene, None) runs on the weather's own clock. Checks, one PASS/FAIL line each:
  - which weathers build it (the weather argument, set_weather, transition_to), weather_fx True / False / a dict
  - the scene's materials are wrapped at build; the system is the sky's (owned), and one the scene attaches replaces it
  - Sky.bake hands the bake to the weather with its own options, wrapping the materials the scene gained since
    make_sky (an eido_dry object stays dry); the weather's bake bakes the sky (flagged, so the sky does not hand
    back) and keys the rain, the shader values and the audio contract
  - without a sky: no sun lamp, no world change, the generators' Sky input at 0, the rain on every column with its
    base colour and light (the rain colour still applies), no storm canopy, no lightning in any weather, wetness
    rising, the clock refusing a sky bake, and the errors for an unsaved .blend without cache_dir or no camera

    bash run_blender.sh blender/tests/weather/test_weather_sky_wiring.py
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.weather import make_weather_system  # noqa: E402
from eidoblend.weather.system import WeatherFX  # noqa: E402
from eidoblend.weather.frame import WATER_BASE  # noqa: E402

OUT = os.path.join(HERE, 'out', 'sky_wiring')
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


def principled(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1.0)
    return m


def fresh(frames=48):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, frames
    bpy.ops.mesh.primitive_plane_add(size=60.0)
    ground = bpy.context.object
    ground.name = 'ground'
    ground.data.materials.append(principled('ground_asphalt', (0.08, 0.08, 0.085)))
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(3.0, 8.0, 1.0))
    box = bpy.context.object
    box.name = 'box'
    box.data.materials.append(principled('box_paint', (0.6, 0.2, 0.1)))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0.0, -6.0, 1.6)
    cam.rotation_euler = (math.radians(88.0), 0.0, 0.0)
    return sc, cam


def wrapped(name):
    return bool(bpy.data.materials[name].get('eido_wet_wrapped'))


def cache(tag):
    return os.path.join(OUT, tag)


# ---- which weathers build it ----
sc, cam = fresh()
for weather, want in (('storm', True), ('darkstorm', True), ('rain', True), ('sunshower', True), ('cyclone', True),
                      ('drizzle', True), ('overcast', True), ('fair', False), ('clear', False), (None, False)):
    sky = make_sky(sc, camera=cam, hours=15.0, weather=weather, cache_dir=cache('which'), quality='draft')
    got = isinstance(sky.weather_fx, WeatherFX)
    check('make_sky(weather=%r) %s its weather' % (weather, 'builds' if want else 'leaves out'), got == want)
    if sky.weather_fx is not None:
        sky.weather_fx.dispose()
sky = make_sky(sc, camera=cam, hours=15.0, cache_dir=cache('later'), quality='draft')
check('a sky with no weather yet has none', sky.weather_fx is None)
sky.set_weather('fair', at=2.0)
check('set_weather(fair) does not build it', sky.weather_fx is None)
sky.transition_to('rain', 1.0, 20.0, at=10.0)
fx = sky.weather_fx
check('transition_to(rain, at=10) builds it at the call, owned by the sky', isinstance(fx, WeatherFX) and fx.owned_by_sky)
check("it wrapped the scene's materials for wetness", wrapped('ground_asphalt') and wrapped('box_paint'))
fx.dispose()
sky = make_sky(sc, camera=cam, hours=15.0, weather='storm', cache_dir=cache('off'), quality='draft', weather_fx=False)
check('weather_fx=False: a storm sky without a weather system', sky.weather_fx is None and not wrapped('ground_asphalt'))
sky.transition_to('darkstorm', at=1.0)
check('weather_fx=False: a later storm call builds none either', sky.weather_fx is None)
sky = make_sky(sc, camera=cam, hours=15.0, weather='clear', cache_dir=cache('true'), quality='draft', weather_fx=True)
check('weather_fx=True builds it in a clear sky', isinstance(sky.weather_fx, WeatherFX))
sky.weather_fx.dispose()
sky = make_sky(sc, camera=cam, hours=15.0, weather='rain', cache_dir=cache('dict'), quality='draft',
               weather_fx=dict(rain_count=3000, splash_count=0, puddles=0.5, rain_cells='column'))
o = sky.weather_fx.opts
check('weather_fx={...}: the options reach make_weather_system',
      (o['rain_count'], o['splash_count'], o['puddles'], sky.weather_fx.rain_cells) == (3000, 0, 0.5, 'column'), o)
check('weather_fx of another kind raises',
      raises(lambda: make_sky(sc, camera=cam, cache_dir=cache('x'), weather_fx='yes'), ValueError))
own = sky.weather_fx
mine = make_weather_system(sc, sky, moisture=False, log=lambda *a: None)
check("make_weather_system on that sky replaces the sky's own (disposed), and is the scene's, not the sky's",
      own._disposed and sky.weather_fx is mine and not mine.owned_by_sky)
mine.dispose()

# ---- the bake hands over ----
sc, cam = fresh(24)
sky = make_sky(sc, camera=cam, hours=16.0, weather='storm', cache_dir=cache('handover'), quality='draft')
fx = sky.weather_fx
# geometry the scene gains after make_sky: a bench to wet, and an awning's underside marked to stay dry
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-3.0, 6.0, 0.5))
bpy.context.object.data.materials.append(principled('bench_wood', (0.3, 0.2, 0.12)))
bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0.0, 6.0, 2.5))
bpy.context.object.data.materials.append(principled('awning_underside', (0.5, 0.5, 0.5)))
bpy.context.object['eido_dry'] = 1
calls = []


def fx_bake(frame_start=None, frame_end=None, bake_sky=True, keys=True, sky_bake=None):
    calls.append((frame_start, frame_end, bake_sky, keys, sky_bake))
    fx.sky_frames = ['the sky frames']
    return []


fx.bake = fx_bake
got = sky.bake(3, 5, overscan=0.1, plate_scale=1.5, log=print)
check("Sky.bake hands the bake to the sky's weather with its own options, and returns the sky's frames",
      calls == [(3, 5, True, True, dict(overscan=0.1, layer_scale=None, plate_scale=1.5, log=print))]
      and got == ['the sky frames'], calls)
check('the handed-over bake wraps what the scene gained since make_sky (eido_dry stays dry)',
      wrapped('bench_wood') and not wrapped('awning_underside'))
del fx.bake                                         # the instance's own method again
seen = []
sky.bake = lambda *a, **k: (seen.append((a, k, fx._baking)), ['baked'])[1]
rows = fx.bake(1, 24, sky_bake=dict(overscan=0.05))
check("the weather's bake plans every frame, then bakes the sky with its options while flagged (so the sky does not "
      'hand it back)', len(rows) == 24 and seen == [((1, 24), dict(overscan=0.05), True)] and not fx._baking
      and fx.sky_frames == ['baked'], seen)
del sky.bake
from eidoblend.sky.world_nodes import _fcurves  # noqa: E402
rain = bpy.data.objects['eido_rain']
paths = {fc.data_path for fc in _fcurves(rain.animation_data)} if rain.animation_data else set()
car = bpy.data.objects['eido_weather']
check('it keyed the rain generator and the audio contract', any('inputs' in p for p in paths) and 'rainK' in car.keys(),
      sorted(paths)[:3])

# ---- the weather without a sky ----
sc, cam = fresh(48)
world = bpy.data.worlds.new('studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.3, 0.32, 0.36, 1.0)
sc.world = world
key = bpy.data.objects.new('key_light', bpy.data.lights.new('key_light', 'SUN'))
sc.collection.objects.link(key)
nodes_before = sorted(n.name for n in world.node_tree.nodes)
check('without a sky an unsaved .blend needs cache_dir', raises(lambda: make_weather_system(sc, None), ValueError))
wx = make_weather_system(sc, None, cache_dir=cache('skyless'), log=lambda *a: None)
check('without a sky: the weather runs on its own clock (state only), with no sun lamp and the scene\'s world as it was',
      wx.sky.state_only and not wx.sky_drawn and wx.sky.sun is None and 'eido_sky_sun' not in bpy.data.objects
      and sc.world == world and sorted(n.name for n in world.node_tree.nodes) == nodes_before)
gens = [wx.objects['eido_rain'], wx.objects['eido_splashes']]
from eidoblend.weather._graph import get_input  # noqa: E402
check("the generators' Sky input is 0 (every column rains, no sun glint)",
      all(get_input(g['modifier'], g['ids']['Sky']) == 0.0 for g in gens))
check("it wrapped the scene's materials (wrap_scene)", wx.wrap_scene() == 2 and wrapped('ground_asphalt'))
wx.set_weather('storm')
wx.transition_to('darkstorm', 1.0, 0.5, at=1.0)
rows = wx.bake(1, 48)
r = rows[-1]
check('it rains: the storm then the darkstorm rain amount, on every column', all(rw['rain_k'] > 0.99 for rw in rows)
      and all(rw['cell_at_camera'] == 1.0 for rw in rows), '%.2f, cell %.2f' % (r['rain_k'], r['cell_at_camera']))
check("the rain keeps its base colour and light, with no storm canopy (the JS's sky-less rain)",
      all(rw['rain_light'] == 1.0 and rw['storm_canopy'] == 0.0 and tuple(rw['rain_color']) == tuple(WATER_BASE)
          for rw in rows))
check('no lightning without a sky, even in a darkstorm (the JS schedules it only with a sky)',
      len(wx.sched.events) == 0 and all(rw['l_light_intensity'] == 0.0 for rw in rows), len(wx.sched.events))
check('the ground wets', rows[-1]['wetness'] > rows[0]['wetness'] + 0.05 and rows[-1]['moisture_at_camera'][0] > 0.05,
      'wetness %.3f -> %.3f, moisture at the camera %.3f' % (rows[0]['wetness'], rows[-1]['wetness'],
                                                            rows[-1]['moisture_at_camera'][0]))
check('nothing baked a sky', wx.sky_frames is None and not os.path.exists(os.path.join(cache('skyless'), 'sky_cam_0001.exr')))
check("the clock refuses a sky bake", raises(lambda: wx.sky.bake(), ValueError))
wx.set_colors({'rain': (1.0, 0.55, 0.3)})
rows = wx.bake(1, 4)
check('the rain colour still applies without a sky',
      all(abs(rows[-1]['rain_color'][i] - WATER_BASE[i] * c) < 1e-9 for i, c in enumerate((1.0, 0.55, 0.3))),
      rows[-1]['rain_color'])
wx.dispose()
sc.camera = None
check('without a sky the rain needs the scene camera',
      raises(lambda: make_weather_system(sc, None, cache_dir=cache('skyless')), ValueError))
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
