"""The facade's records in Blender axes, and make_weather_audio (makeWeatherAudio) in a frame loop of its own. No
render (no GPU slot).

    bash run_blender.sh blender/tests/weather/test_facade_records.py

A flat ground under darkstorm with a forced local strike, planned for 8 s. Checks:
  - state['strike'] (the JS state.strike) is in Blender axes: its x, y, z is the strike point the frame record keys for
    the audio (strike_blender), its z is the struck surface's height, its normal points up (+Z)
  - diagnostics['lightning']['lastStrike'] and localImpact.lastSurfaceDamage are in Blender axes too, while the
    scheduler's own records stay in three.js axes (the parity tests read those)
  - make_weather_audio(weather=wx, camera=cam), updated after wx.update(t, cam) in a loop over sky.frame_states,
    records the timeline WeatherFX.audio_timeline() records from the baked rows: the same rain and wind envelopes,
    the same thunder events; stats, timeline() and to_json() are there, and wx.audio (sky_worlds.js `audio`) too
  - the lightning profile's entries by their snake_case names, the JS names as aliases, the gap scale bound
  - three's FrontSide: the splash rings face the sky, every face of the spark octahedra and the puff spheres faces
    out, and those three materials cull back faces while the rain, bolt and scorch stay double sided
  - make_weather_audio without a weather reads the scene's own system (the JS globalThis._weather), and records
    nothing once it is disposed
  - fall_speed, rain_radius, rain_height, puddles, wet_tint, cloud_color and sun_color at values other than their
    defaults reach the generators, the keyed values, the colour record and the sky
"""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.weather import make_weather_system, make_weather_audio  # noqa: E402

OUT = os.path.join(HERE, 'out', 'facade')
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 8 * 24 + 1
sc.render.resolution_x, sc.render.resolution_y = 320, 180
ground_c = bpy.data.collections.new('ground_set')
sc.collection.children.link(ground_c)
me = bpy.data.meshes.new('ground')
me.from_pydata([(-300, -300, 1.5), (300, -300, 1.5), (300, 300, 1.5), (-300, 300, 1.5)], [], [(0, 1, 2, 3)])
mat = bpy.data.materials.new('ground')
mat.use_nodes = True
me.materials.append(mat)
ground = bpy.data.objects.new('ground', me)
ground_c.objects.link(ground)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
cam.location = (0, -10, 3.2)
cam.rotation_euler = (math.radians(90), 0, math.radians(20))      # looking along +Y, turned 20 degrees left
sc.camera = cam

sky = make_sky(sc, camera=cam, hours=15.0, weather='darkstorm', cache_dir=os.path.join(OUT, 'cache'), quality='draft')
wx = make_weather_system(sc, sky, strike_targets=[ground_c], moisture=False, log=lambda *a: None)
wx.wrap_scene()
wx.debug_force_local_strike(at=1.0)
rows = wx.plan()
local = [e for e in wx.sched.events if e['strike']['local']]
check('the forced strike is local', bool(local), [(e['time'], e['strike']['kind']) for e in wx.sched.events])

# ---- the records, in Blender axes ----
row = next((r for r in rows if r['strike_blender'] and r['strike_blender']['local']), None)
st = wx.state['strike']
sched_st = wx.sched.strike
check('state.strike is in Blender axes: the point the audio contract keys',
      st is not None and row is not None
      and all(abs(st[k] - row['strike_blender'][k]) < 1e-9 for k in ('x', 'y', 'z')),
      (st and (st['x'], st['y'], st['z']), row and row['strike_blender']))
check('state.strike z is the struck surface height (1.5 m + 0.04)', st is not None and abs(st['z'] - 1.54) < 1e-6,
      st and st['z'])
check('state.strike normal points up (+Z)', st is not None and st['normal'][2] > 0.99, st and st['normal'])
check('the scheduler record stays in three.js axes (y is the height)',
      sched_st is not None and abs(sched_st['y'] - 1.54) < 1e-6 and abs(sched_st['z'] + st['y']) < 1e-9,
      sched_st and (sched_st['x'], sched_st['y'], sched_st['z']))
D = wx.diagnostics['lightning']
ls = D['lastStrike']
check('diagnostics.lightning.lastStrike is in Blender axes', ls is not None and abs(ls['z'] - st['z']) < 1e-9
      and abs(ls['y'] - st['y']) < 1e-9, ls and (ls['x'], ls['y'], ls['z']))
dmg = D['localImpact']['lastSurfaceDamage']
check('diagnostics.lightning.localImpact.lastSurfaceDamage is in Blender axes',
      dmg is not None and abs(dmg['point'][2] - 1.54) < 1e-6 and dmg['normal'][2] > 0.99, dmg and dmg['point'])
li = wx.state['lastImpact']
check('state.lastImpact is the same Blender record', li is not None and li['point'] == dmg['point'], li and li['point'])
check('the struck object carries the record', ground.get('eido_lightning_strikes', 0) >= 1
      and json.loads(ground['eido_lightning_last'])['point'] == dmg['point'])

# ---- make_weather_audio in a frame loop of its own, against the baked timeline ----
baked = wx.audio_timeline()
wx_audio = make_weather_audio(weather=wx, camera=cam, quiet=True)
wx._last_t = 'unset'                     # a fresh run of the weather (what plan() does)
for f, t, _L in sky.frame_states(sc.frame_start, sc.frame_end):
    wx.update(t, cam)
    wx_audio.update(t)
tl = wx_audio.timeline()
check('make_weather_audio: same rain envelope as audio_timeline()', tl['rain'] == baked['rain'],
      (len(tl['rain']), len(baked['rain'])))
check('make_weather_audio: same wind envelope', tl['wind'] == baked['wind'], (len(tl['wind']), len(baked['wind'])))
check('make_weather_audio: same thunder events (clip, time, gain, pan, distance)',
      [(e['clip'], e['t'], e['gain'], e['pan'], e['distance']) for e in tl['events']]
      == [(e['clip'], e['t'], e['gain'], e['pan'], e['distance']) for e in baked['events']] and tl['events'],
      (len(tl['events']), len(baked['events'])))
check('make_weather_audio: the local strike gets the explosive clap', any('explosive' in e['clip'] for e in tl['events']),
      [e['clip'].rsplit('/', 1)[-1] for e in tl['events']])
check('make_weather_audio: stats, timeline() and to_json()', wx_audio.stats['strikes'] == len(wx.sched.events)
      and json.loads(wx_audio.to_json()) == json.loads(json.dumps(tl)), wx_audio.stats)
check('wx.audio (sky_worlds.js audio): the planned timeline with stats, timeline() and to_json()',
      wx.audio is not None and json.loads(wx.audio.to_json()) == json.loads(wx.audio_json())
      and wx.audio.stats['strikes'] == len(wx.sched.events))
from eidoblend.weather import lightning as LP  # noqa: E402
P = wx.lightning_profile
check('lightning_profile: snake_case entries, the JS names as aliases, the system gap scale bound',
      all(P[a] is P[b] for a, b in (('styleKeyAt', 'style_key_at'), ('eventGapAt', 'event_gap_at'),
                                    ('initialEventGapAt', 'initial_event_gap_at'), ('strokePlanAt', 'stroke_plan_at'),
                                    ('flashAt', 'flash_at'), ('channelAt', 'channel_at'),
                                    ('localCandidateAt', 'local_candidate_at')))
      and P['event_gap_at'](7, 'darkstorm', 0.6) == LP.lightning_event_gap_at(7, 'darkstorm', 0.6, wx.sched.gap_scale)
      and LP.EANPA_LIGHTNING_PROFILE['style_key_at'](5, 'darkstorm') == LP.lightning_style_key_at(5, 'darkstorm'))
fallback = make_weather_audio(quiet=True)          # no weather: the scene's own system (the JS globalThis._weather)
fallback.update(0.0)
check('make_weather_audio with no weather reads the scene\'s weather system', len(fallback.timeline()['rain']) == 1,
      fallback.timeline()['rain'])

# ---- three's FrontSide on the splash rings, the sparks and the puffs: front faces out, back faces culled ----
import numpy as np  # noqa: E402
wx.key(rows, frame_start=sc.frame_start)
imp = wx.sched.impacts[-1]
sc.frame_set(int(round((imp['birth'] + 0.3) * 24)) + 1)
dg = bpy.context.evaluated_depsgraph_get()


def faces_out(ob, per):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.array([v.co[:] for v in me.vertices]) if len(me.vertices) else np.zeros((0, 3))
    n_out, n = 0, len(me.polygons)
    for i, p in enumerate(me.polygons):
        g = i // per
        cen = co[[v for q in me.polygons[g * per:(g + 1) * per] for v in q.vertices]].mean(axis=0)
        n_out += int(np.dot(np.array(p.center[:]) - cen, np.array(p.normal[:])) > 0)
    ev.to_mesh_clear()
    return n_out, n


sp = bpy.data.objects['eido_impact_sparks_%03d' % imp['interval']]
pf = bpy.data.objects['eido_impact_puffs_%03d' % imp['interval']]
o, n = faces_out(sp, 8)
check('spark octahedra: every face faces out (the mirrored half flipped back)', n > 0 and o == n, (o, n))
o, n = faces_out(pf, 80)
check('puff spheres: every face faces out', n > 0 and o == n, (o, n))
ev = wx.objects['eido_splashes']['object'].evaluated_get(dg)
me = ev.to_mesh()
nz = np.array([p.normal.z for p in me.polygons])
ev.to_mesh_clear()
check('splash rings face the sky', len(nz) > 0 and (nz > 0.99).all(), (len(nz), float(nz.min()) if len(nz) else None))
check('FrontSide materials cull back faces (splash, spark, puff); rain, bolt and scorch are double sided',
      all(bpy.data.materials[m].use_backface_culling for m in ('eido_splash', 'eido_spark', 'eido_puff'))
      and not any(bpy.data.materials[m].use_backface_culling for m in ('eido_rain', 'eido_bolt', 'eido_scorch')))
wx.dispose()
gone = make_weather_audio(quiet=True)
gone.update(0.0)
check('make_weather_audio with no weather system at all records nothing (the JS returns)',
      gone.timeline()['rain'] == [])

# ---- the plain JS options at values other than their defaults reach what they drive ----
sc.frame_end = 25
wo = make_weather_system(sc, sky, fall_speed=7.0, rain_radius=30.0, rain_height=12.0, puddles=0.4,
                         wet_tint=(1.0, 0.8, 0.6), cloud_color=(0.9, 0.8, 1.0), sun_color=(1.0, 0.7, 0.5),
                         moisture=False, log=lambda *a: None)
rows_o = wo.plan()
wo.key(rows_o)
gen = wo.objects['eido_rain']
mod, ids = gen['modifier'], gen['ids']
spl = wo.objects['eido_splashes']
sc.frame_set(12)
vt = bpy.data.node_groups['eido_weather_values']
val = lambda k: vt.nodes[k].outputs[0].default_value  # noqa: E731
from eidoblend.weather._graph import get_input  # noqa: E402
check('rain_radius / rain_height reach the streak tile and the splash tile', get_input(mod, ids['Radius']) == 30.0
      and get_input(mod, ids['Height']) == 12.0 and get_input(spl['modifier'], spl['ids']['Radius']) == 30.0)
r12 = rows_o[11]
check('fall_speed: the keyed fall is fall_speed x fallMul, and uniforms.fallSpeed is it',
      abs(r12['fall'] - 7.0 * float(sky.wx.u['fallMul'])) < 1e-9 and wo.uniforms['fallSpeed'] == 7.0,
      (r12['fall'], wo.uniforms['fallSpeed']))
check('puddles and wet_tint: keyed into the shader values', abs(val('puddle_k') - 0.4) < 1e-6
      and abs(val('wet_tint_g') - 0.8) < 1e-6 and abs(val('wet_tint_b') - 0.6) < 1e-6,
      (val('puddle_k'), val('wet_tint_g'), val('wet_tint_b')))
skc = sky.sky.get_colors()
check('cloud_color / sun_color: the colour record and the sky get them', wo.get_colors()['cloud'] == (0.9, 0.8, 1.0)
      and wo.get_colors()['sun'] == (1.0, 0.7, 0.5)
      and all(abs(a - b) < 1e-6 for a, b in zip(skc['cloud'], (0.9, 0.8, 1.0)))
      and all(abs(a - b) < 1e-6 for a, b in zip(skc['sun'], (1.0, 0.7, 0.5))), (wo.get_colors(), skc))
wo.dispose()
print('RESULT ' + ('PASS' if not fails else 'FAIL (%d)' % len(fails)), flush=True)
