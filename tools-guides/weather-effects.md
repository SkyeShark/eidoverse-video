# Weather effects — rain, wet ground, lightning and weather audio

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Sky and weather states](sky-weather.md)

**`make_weather_system`** is the weather of the Blender 5.2 EEVEE edition (`blender/eidoblend/weather/`), the
port of `eidoverse/weather_system.js` and `eidoverse/weather_audio.js`. The sky package owns the weather *states*:
the `WEATHER` table, `set_weather`, `transition_to`, the eased morph, sky greying, sun and sky dimming. This package
draws what the states make happen on the ground:

- world-space rain streaks and ground splashes;
- wet surfaces and puddles, from a 2D history of how much rain each place has had;
- lightning: the deterministic scheduler, the bolt, the strike light, the flash in the sky, and on a local strike
  its sparks, burn puffs and scorch;
- the weather audio: the rain bed, the wind bed and one thunderclap per strike, delayed by distance, baked to a WAV
  and muxed onto the film.

Everything is keyed Blender data. After `bake()` a plain render plays the weather with no Python in the loop, and a
saved `.blend` renders any frame on its own (its `sky_cache` folder must stay beside it).

```python
import sys; sys.path.insert(0, '<worktree>/blender')
import bpy
from eidoblend.sky import make_sky
from eidoblend.weather import make_weather_system

scene = bpy.context.scene
sky = make_sky(scene, camera=cam, hours=17.0, weather='rain', cache_dir='C:/films/street/sky_cache')
sky.transition_to('darkstorm', 1.0, 9.0, at=39.0)         # direction calls stay on the sky

wx = make_weather_system(scene, sky,
                         strike_targets=[street],          # objects or collections local strikes may hit
                         occluders=street)                 # roofs and awnings that keep the rain off
wx.wrap_scene()                                            # eido_wet in front of every Principled BSDF
wx.bake(frame_start=913, frame_end=1392)                   # plan, bake the sky with the flashes, key it all
bpy.ops.render.render(animation=True)
wx.bake_audio('C:/films/street/weather.wav', frame_start=913)
wx.merge_av('street_video.mp4', 'C:/films/street/weather.wav', 'street_final.mp4')
```

`bake()` plans every frame from the scene's first, so frames before `frame_start` are a pre-roll: the weather runs
through them as state only. Here 38 seconds of rain wet the street and fill its puddles before the shot opens, and
darkstorm's cadence makes its first strike a close one, about 3 s after the storm starts rolling in.

## How a frame is made

`bake()` replays the sky's direction calls frame by frame (`sky.frame_states`). After the sky's update it runs the
weather's own update, where the JS `weather.update(t, camera)` runs: the integrated fall and wind phases, the
lightning scheduler, the rain light and colour, and the moisture history. Then it does three things:

1. It bakes the sky with the lightning in it. An `on_frame` callback writes each frame's flash, sheet flash, strike
   colour and strike position into the sky's state before its update, so the baked sky layers carry the zenith and
   horizon flash and the clouds glow around the strike. While the sky replays, the weather's Geometry Nodes objects
   are left out of the viewport depsgraph (renders use the render depsgraph and keep them): the replay steps every
   frame, and the rain's ray casts were most of a one-frame sky bake.
2. It keys the frames into the scene (below).
3. It writes `weather/weather_state.json` beside the sky cache: every frame's values, the events, the diagnostics.

| What | Keyed as |
| --- | --- |
| rain streaks, splashes | Geometry Nodes generators `eido_rain`, `eido_splashes`: modifier inputs keyed per frame (camera, fall phase, wind offset, rain amount, cell gate, canopy, cloud drift ...) |
| shader values | the node group `eido_weather_values`: rainK, rainLight, rainColor, wetness, wet target, surface water, time, the rain direction, the moisture centre, keyed per frame |
| moisture history | an image sequence `weather/moisture_####.exr` (R thin wetness, G pooled water, B the local rain cell) |
| rain exposure | `weather/rain_exposure.exr`: the first surface along the rain, and `rain_exposure_soft.exr`: the gust-soft ground mask (with `occluders`) |
| strike light | `eido_lightning_light`: energy keyed per frame, colour and position per event |
| bolts | one mesh per event, `eido_bolt_###`: its channel glow keyed, hidden from renders while it does not glow |
| impacts | per local strike `eido_impact_sparks_###`, `_puffs_###`, `_scorch_###`: Geometry Nodes on Scene Time |
| audio contract | the empty `eido_weather`: rainK, denseA, wind_len, strike_id / x / y / z / flash / local |

Each frame record also carries what the camera stands in: `moisture_at_camera` (wet, water) and `cell_at_camera`
(the local cloud supply). `update(t, camera)` returns the record for an `on_frame` loop of your own.

## Options

The WebGPU option names, in snake_case:

- `rain_count` 16000, `rain_radius` 45 (m: the world tile is twice this), `rain_height` 24 (m: the vertical
  recycle), `splash_count` 1200 (0 turns the splashes off, the JS switch for terrain scenes), `fall_speed` 11 (m/s).
- `ground_y` 0: the splash plane's height when there are no `occluders`.
- `puddles` 1 (puddleK), `wet_tint` (1, 1, 1) for alien rain.
- `rain_color`, `cloud_color`, `sun_color`, `shield_color`: per-channel multipliers over the state's look
  (`set_colors` later).
- `lightning_gap_scale` 0.42. It is eidoverse's offline cadence: the authored 16-38 s between events, compressed so
  a 15-90 s clip catches strikes. 1.0 is the realtime spacing.
- `storm_center` (Blender x, y) and `storm_range` 700: where distant strikes land. A strike looks for a dense cell
  of the sky's weather field in that square.
- `strike_targets`: objects, collections or a callable returning them. Local strikes land on their upward
  surfaces. `strike_height_at(x, y) -> z` is a heightfield fallback. `on_local_strike(record)` is told of each
  local strike.
- `drop_texture`, `bolt_texture`: paths. They default to `eidoverse/assets/sky/rain_streak.png` and
  `eidoverse/assets/particle_textures/trace_06.png`, as the WebGPU sky does. `None` draws the procedural shapes:
  the streak's bright core with end fades, the bolt's core profile alone.

Blender additions:

- `occluders`: a collection. Rain stops at its roofs, splashes land on its surfaces, and its shelter keeps ground
  dry. `wet_exposure` (default True) is that last part.
- `wet_model`: `'moisture'` (default) or `'eidoverse'`, see [Wet surfaces](#wet-surfaces-and-puddles-eido_wet).
- `rain_cells`: `'upwind'` (default) or `'column'`, see [Rain and splashes](#rain-and-splashes). With
  `wet_model='eidoverse'` and `rain_cells='column'` the rain and the wet ground are eidoverse's, formula for formula.
- `moisture` (default on), `moisture_radius` 1024 and `moisture_resolution` 256 (Eanpa's values).
- `cache_dir`: default `<sky cache>/weather`.

## Direction

- `set_weather(name, k=1, at=None)` and `transition_to(name, k=1, dur=45, at=None)` go to the sky's recipe. Pass
  60-120 s for a naturally rolling front.
- `set_colors({rain, cloud, sun, shield}, at=None)` retints the active look; only the channels named reach the sky.
  `shield` recolours the shieldworld's hex shield; another world prints the sky's warning and ignores it.
  `get_colors()` returns the multipliers last set.
- `sun_dim()` and `hemi_dim()` are the sky's.
- `debug_force_local_strike(at=0)`: the next lightning event after media time `at` becomes a close forward strike,
  34-58 m ahead within ±25°. It is pulled to 0.6 s after the call and bypasses chance and cooldown. It does nothing
  in weather with no lightning. It returns True: the JS returns whether the weather can strike now, and here
  whether it can at `at` is known only when the bake replays that moment (afterwards `wx.sched.impacts` lists every
  local strike, and `diagnostics['lightning']['localImpact']` counts the attempts and strikes).
- `update(t, camera=None)`: one frame of the weather, with the sky already at `t`. It is for an `on_frame` loop of
  your own. `bake()` calls it for you.
- `dispose()` unwraps every material, removes the weather's objects, materials and node groups and unhooks the sky.
  A scene has one weather system: making a second one disposes the first, as the JS registry does, and a disposed
  system's `update()` returns False.
- `uniforms`, `state` (`name`, `k`, `def_`, `strike`, `lastImpact`), `diagnostics` (the JS acceptance record:
  transition, motion, precipitation, lightning, wetness), `rain` (the streak object), `bolt` (the strike light),
  `WEATHER` and `lightning_profile` are the JS facade's fields, read after a plan or bake. Their positions are in
  Blender axes: `state['strike']` x, y, z is the strike point (z its height) with its normal, and so are
  `state['lastImpact']`, `diagnostics['lightning']['lastStrike']` and its `localImpact.lastSurfaceDamage`. Only the
  scheduler's own records (`wx.sched.events`, `wx.sched.impacts`) stay in three.js axes, as the JS keeps them.

## Rain and splashes

The streaks are the WebGPU streaks. Each one's world position is a pure function of its index, the integrated fall
phase and the integrated wind, tiled in a 90 m square around the camera. The field therefore stands still while the
camera walks through it.

- Drop sizes come as a population: the length is `streakLen × (h1² × 1.1 + 0.45)` and the width a 1:8 aspect of it,
  thickened with distance so far rain still reads as layers.
- The nearest 0.9-2.6 m fade out, so no drop lands on the lens. A circular feather hides the tile's edge.
- Each quad faces the camera's right axis and runs along its velocity, so wind tilts it.
- The colour is the lit rain colour times the per-drop glint, which brightens rain toward the sun. The opacity is
  the drop texture's alpha times the cell gate, a per-drop population gate (light rain is fewer drops, not fainter
  ones) and the rain amount. Under the sealed darkstorm canopy every drop keeps a gate of 0.82-1 and gains 1.28×
  opacity.
- Rain is translucent water lit by the sky, as in WebGPU: its radiance follows the time of day, the weather's
  dimming and the lightning, not the scene's lamps. A drop under a street lamp does not catch its light.

`test_blender_build.py` checks every quad corner the Geometry Nodes tree evaluates against the JS formulas, in float32:
the largest difference is under a millimetre.

**Against WebGPU itself.** `rain_ab_webgpu_scene.js` renders eidoverse's own `makeSky` weather in deno over a street
of grey blocks, and `rain_ab_blender.py` renders the same blocks, camera, hour and moments in EEVEE
(`wet_model='eidoverse'`, `rain_cells='column'`), each frame beside its twin with the rain hidden. In cyclone, storm,
rain and darkstorm the two engines agree on rainK, denseA, rainLight, rainColor, the wetness and the streak length to
four decimals. Daylight `rain` and `storm` streaks are faint in both: rain is translucent water lit by a dimmed sky,
and over grey facades it has little contrast. It reads under darkstorm's canopy and in cyclone. The streak detail the
rain adds to the frame (its high-pass energy) is as large in EEVEE or larger: cyclone 0.54 against WebGPU's 0.04,
darkstorm 0.36 against 0.28, storm 0.12 against 0.03, rain 0.05 against 0.01. Point-sampling the drop texture (WebGPU
samples it at mip level 0) changes it by 3-4 %, a 0.75 px pixel filter by 16-18 %, so the default linear filtering
stays.
The skies and their light differ between the two frames (WebGPU's hemisphere fill keeps the hour's blue zenith in a
storm, where the Blender world fills with the greyed sky: both the sky's), so the comparison measures the rain's own
detail, not the frames' levels.

The cell gate samples the sky's weather field at the column the drops fell from: upwind of them by their fall time
from the cloud base (Eanpa's `rainCellAt`). The splashes and the moisture history read the same gate, so rain, rings
and wet ground agree on where it is raining. Rain falls in cells: walk out from under one and the rain stops around
you while the far curtains keep falling. eidoverse gates each drop by the cell straight above it instead;
`rain_cells='column'` does that, for drops, rings and moisture alike. At the ground the two put the edge of a cell
about 150 m apart in `rain` and about 290 m apart in `storm` and `cyclone` (the wind times the fall time from the
deck); under darkstorm's sealed canopy they are the same.

Splashes are rings that expand at 2.4 Hz on a hashed phase at world-tiled spots. With `occluders`, each ring sits
1.5 cm above the first surface the rain reaches through its column (road, curb, awning, roof), on that surface's
slope, and only where the surface faces up. Without `occluders` they sit at `ground_y`, as in eidoverse. The colour
is the rain colour × 1.15.

With `occluders`, a streak is hidden when a Raycast up its own rain line meets a surface. Rain stops at roofs, at the
awning and at the ground, and never falls indoors. The rain lines are straight, so a crosswind puts a street canyon
in the rain shadow of its upwind buildings: cyclone's rain falls about 50° from vertical, and behind 15 m buildings a
16 m street gets almost no drops and stays dry (storm's 28° shelters a strip along the upwind side). eidoverse's
rain fell everywhere; leave `occluders` out to have it so, or aim the street along the wind.

Drops beading and running on the lens are a screen effect, not weather: `rain_on_camera` in the look package's post
effects (`eidoblend.look.post`, [postprocessing.md](postprocessing.md)).

## Wet surfaces and puddles: `eido_wet`

`wrap_scene()` puts a wetness group in front of every Principled BSDF in the scene. It skips the weather's own objects
and objects marked `eido_dry`. `wrap_material(mat)` wraps one material.

The group takes over the Base Color, Roughness, Metallic, Normal and IOR inputs. It feeds them from their original
sources, so textures and normal maps keep working under it. `unwrap_material(mat)` (or `dispose()`) restores every
link and value.

`wet_model='moisture'` (the default) is `eido_wet`, Eanpa's wetness response over the moisture history:

- **Wetness.** Surfaces facing the rain darken a little. The default porosity is 0.65; metals do not darken. They
  also gloss up: roughness falls to 0.48×, with a floor of 0.045. Walls facing into the wind wet, walls facing away
  stay dry.
- **Puddles.** They fill procedural cavities first. The cavities are value noise thresholded near its middle, with
  the domain warped so the outlines meander. As the pooled water rises the fill level drops from 0.79 to 0.56, so
  puddles grow out from their deepest spots. Water is a dielectric of IOR 1.333 (F0 0.0204) at roughness 0.045
  (+0.025 while it rains). From above the ground darkens a little under it, and toward grazing angles it reflects
  the street.
- **Ripples.** While rain falls on that cell, sparse expanding capillary rings ripple the water's normal. They fade
  out past 8-35 m.

`wet_model='eidoverse'` is `eido_wet_eidoverse`, eidoverse's own `wrapMaterial`, formula for formula: one global
wetness (the state's `wet × k`, eased through a transition, with no history), upward surfaces (normal height
squared) darkening toward 0.68 and glossing to roughness 0.10, puddles where the warped noise passes 0.97-1.13 on
flat ground once wetness passes 0.35-0.9, deepened and cooled toward their centres, at roughness 0.045 and never
metallic. Normal and IOR pass through. Use it to match an eidoverse film; it wets everything at once, cells and
shelter aside.

Receivers opt out the WebGPU way, with custom properties:

| WebGPU | Blender |
| --- | --- |
| `object.userData.noWet` | object `eido_dry = 1` |
| `object.userData.noPuddles` | object `eido_no_puddles = 1` (wet sheen, no pools) |
| `object.userData.wetnessFactor` | object `eido_wet_reduce = 1 - factor` |
| `material.userData.noWet / noPuddles` | material `eido_noWet` / `eido_noPuddles` |
| `material.userData.wetPorosity` | material `eido_wetPorosity` (0-1) |
| `material.userData.puddleMaskNode` | link a mask into the group's Cavity input and set Use Cavity to 1 |

Vertical glass is a good `eido_noWet` material: the test street's windows carry it.

**The moisture history** (Eanpa's `rain_accumulation_field.js`) is a world-aligned 256² grid around the camera,
1024 m half-width. Each cell integrates the local rain: the cell gate × rainK, through smoothstep(0, 0.1).

- Thin wetness arrives with a time constant of 7 s and dries in about 70 s.
- Pooled water fills later (32 s) and outlasts the rain (150 s).
- A dry gap between rain cells stays dry under a rainy sky. Overcast humidity with no rain damps surfaces without
  pooling.

The history refreshes at 4 Hz on a grid snapped to whole cells. It recentres, keeping what overlaps, when the camera
moves more than a quarter radius. Between refreshes every frame advances the last state analytically, so wetness
never steps, and the frame rate does not change it.

`test_moisture_contract.py` passes Eanpa's own contract check for check. It also finds the same moisture at 24 and
60 fps.

**Rain exposure.** With `occluders`, the bake ray-casts the first surface along the rain over the occluders' extent
(0.15 m cells by default), along the bake's rain-weighted mean direction. `eido_wet` compares each fragment with the
plane of the surface its line of rain meets. The bias is Eanpa's: 0.06 m, plus 0.28 m where the rain grazes. Under
an awning the sidewalk stays dry and gets no puddles, and in wind-driven rain the lee of a building keeps a dry
strip.

That one exact lookup draws the rain shadow as the projected roof line, hard to the centimetre, and under a lightning
flash the wet side glares beside it as a sharp polygon. Real rain swings with the gusts (±8° moves the shadow of a
15 m building about 2.4 m, an awning's 3 m only 0.45 m). So the bake also casts each line of rain up from below to
find its lowest surface, marks the lines whose first surface stands more than 0.6 m above it (a roof or an awning
over the ground), and blurs that mask along the wind with a triangle 0.15 m wide per metre of the occluder's height
(at most 2.5 m, and narrowing to nothing as the rain turns vertical). Ground-level fragments read the blurred mask with
linear filtering: the shadow's edge ramps smoothly over a few metres, with no bands, while the ground under the middle
of an awning stays dry. Raised surfaces (roofs, ledges, the awning's top) keep the exact test.
`wet_exposure=False` keeps the occluders for the drops and splashes and leaves wet ground unshadowed.

## Lightning

The scheduler is the JS scheduler, decision for decision, and it is deterministic. Every event, colour, stroke,
impact and thunderclap comes from the event index through `jsHash`, so the same film always gets the same storm.

- Events are separated by seconds of dark: 16-38 s × the gap scale (darkstorm 12-28 s, the first one after 6-9 s).
  Fewer when the weather is less electrical (×√(reference / level), at most ×2.75).
- An event is one or two return strokes on the same channel. The scene flash decays as e^-25t. The channel's
  afterglow decays four times slower, so the bolt lingers about half a second.
- A strike's colour comes from its state's palette: the standard palette is white, blue and purple; darkstorm adds
  red and green.
- A strike lands on a dense cell of the sky's weather field inside `storm_range`, or, as a local strike, on a target
  near the camera. `localStrikeChance`, a 45 s cooldown and a 28 m guard around the camera apply. Darkstorm also
  guarantees a local candidate on its first event and after six remote events in a row: a storm rolling in strikes
  close once, early, with no forcing.
- The ray cast keeps the JS receiver rules. Each candidate column is cast straight down through every surface of the
  targets, including the instances a target makes (a collection instance, Geometry Nodes instances), each through
  its own world matrix, as the JS casts an InstancedMesh's instances; the strike record then goes on the instancer.
  It skips hidden objects, objects marked `eido_noLightningStrike` (on the object or a parent), names like
  orb / emitter / beam / fastener / decal / foliage / vegetation / cactus / joshua (on the object, its parents or its
  collections), and BLENDED or translucent materials. It takes the first surface facing up within 44° of vertical.
  `strike_height_at` is the fallback when no target is hit. Mark roofs `eido_noLightningStrike` to keep strikes in
  the street.

What it draws:

- **The strike light**: the JS PointLight of 12000 cd, range 900 m, no shadows, 10 m over a local strike or 120 m
  over a distant one. In Blender that is 4π × 12000 W. `probe_eevee_facts.py` F5 measured a Blender point of
  4π·I watts lighting a diffuse plane like I candela: 0.998 in Cycles, 0.986 in EEVEE. EEVEE's custom 900 m cutoff
  is on; it is a hard edge, where three fades the light over its range (the window is 0.88 at 450 m, 0.40 at
  700 m), so a strike 450-900 m out lights the scene a little more than in WebGPU.
- **The bolt**: rebuildBolt's ribbon. A 12-anchor trunk leaves the deck at 1.04 × the cloud base, gets three passes
  of midpoint displacement (89 points) and 2-4 forks with sub-forks, and lands exactly on the strike. It faces the
  camera the event began with. Its additive material has a white-hot core and a wide glow in the strike's colour,
  dissolves into the deck at the top, and is shaped by `trace_06.png`. `test_lightning_parity.py` matches every
  ribbon vertex of 12 events against the engine.
- **The sky flash**: the sky's own shader lights the clouds around the strike and the zenith and horizon flash in
  the strike's colour. The sky bake gets these through the `on_frame` callback.
- **A local impact**: 64 sparks on ballistic arcs (0.82 s), 16 gyroid-FBM burn puffs (4.5 s) whose white-hot ember
  core dies into ash grey and rises, and a broken-edged char disc with tendrils (90 s, fading from 65 s). The
  impact pool keeps two effect slots and four scorch slots; a newer impact ends the oldest one's effects. Sparks and
  puffs draw their front faces only (backface culling), as three's default `FrontSide` does: one layer of smoke per
  puff, and an additive spark adds its near faces once. The scorch, the bolt and the rain are double sided, as in
  the JS.
- **Records**: a record of each local strike goes to `on_local_strike` and onto the struck object
  (`eido_lightning_strikes`, `eido_lightning_last`). `state['strike']`, `state['lastImpact']` and `diagnostics`
  carry the rest.

The bolt's ×26 core and the puffs' ember were tuned to glow through the WebGPU runner's bloom, which was on by
default (UnrealBloom strength 0.25, radius 0.4, threshold 0.85). EEVEE has none: give the film the look chain's
Glare at those values, before the sky bakes (its fog then splices in ahead of it):

```python
from eidoblend.look.post import chain
chain.set_bloom(scene, strength=0.25, size=0.4, threshold=0.85)
```

A close strike is meant to be blinding: 12000 cd 10 m over the road lights a street 50 m away at about one and a
half times full sunlight, so for a frame or two the facades go white, as in WebGPU. The burn puffs stay white-hot for
their first second or two (their burn curve, `noise − 2.6 × (1 − t^0.4)`), then break into grey smoke and rise.

## Weather audio

`audio_timeline()`, `write_audio(path)` and `bake_audio(wav)` record the planned frames with the weather-audio
recorder, `eidoblend.media.weather_audio`, which is `weather_audio.js` ported decision for decision:

- a rain bed scaled by rainK and curtain density, held under thunder;
- a synthesized wind bed from the wind speed;
- one thunder event per new strike. Its delay is distance / 343 m/s. Its pan comes from the camera's view of the
  strike, and its gain from the compressed inverse-distance model. Strikes within 150 m, or local ones, get the
  explosive clap with the rolling take behind it; mid-range strikes get the close take, with a crack layered on
  within 180 m; far ones get the distant take.

The recorder's options pass through: `rain_gain` 1, `thunder_gain` 1.8, `wind` True, `wind_gain` 1, `quiet`.
`bake_audio` runs the repo-root `bake_weather_audio.py` unchanged, with the clips in `eidoverse/assets/sky/audio/`.
`merge_av(video, wav, out)` runs `merge_av.py`, which refuses to clone-pad a short render or silently cut a long
one (`allow_trim=True` cuts on purpose); a refusal raises with the tool's message. Pass `frame_start` when the bake
had a pre-roll: the track then starts at the shot's first frame.

```python
wx.bake_audio('C:/films/street/weather.wav', frame_start=913)        # writes weather.json beside it, then the WAV
wx.merge_av('street_video.mp4', 'C:/films/street/weather.wav', 'street_final.mp4')
```

`make_weather_audio(weather, camera)` is `makeWeatherAudio` itself, for a frame loop of your own. Update it once per
frame after the weather's `update(t, camera)`, with the same `t`: it reads the weather's uniforms and its strike as
the JS does. `stats`, `timeline()` and `to_json()` are the JS object's.

```python
from eidoblend.weather import make_weather_audio
wx_audio = make_weather_audio(weather=wx, camera=cam)
for f, t, _ in sky.frame_states(1, 480):
    wx.update(t, cam)
    wx_audio.update(t)
open('C:/films/street/wx_audio.json', 'w').write(wx_audio.to_json())
```

`test_lightning_parity.py` runs `weather_audio.js` on the engine's own weather and matches every thunder event and
both bed envelopes. `test_audio_tools.py` bakes that same timeline with `bake_weather_audio.py` and finds each strike
where the timeline puts it and on its side of the stereo field. `test_facade_records.py` finds that the loop above
records exactly the timeline `audio_timeline()` records from the baked frames. The keyed `eido_weather` properties
also serve `weather_audio.read_props`, so a saved `.blend` can be recorded again without the weather system.

## Lower level

| Module | What |
| --- | --- |
| `lightning.py` | `EANPA_LIGHTNING_PROFILE` (`js_hash`, styles, palettes, cadence, gaps, stroke plans, flash and channel envelopes, local candidates; its entries by snake_case names, `style_key_at`, `event_gap_at` ..., with the JS names `styleKeyAt`, `eventGapAt` ... as aliases), `make_lightning_profile(gap_scale)`, `LightningScheduler`, `style_color`, the impact particle data (`impact_particles`, `spark_at`, `puff_at`, `puff_uniforms`, `scorch_at`), `strike_candidates`, `storm_cell_strike_xz`. Plain Python |
| `bolt.py` | `bolt_points`, `bolt_ribbon`: rebuildBolt in three.js space. Plain Python |
| `moisture.py` | `RainAccumulationField`: `prepare`, `sample`, `displayed`, `bounds`, `reset`, `dispose`, `stats`. numpy |
| `frame.py` | `rain_light` (rainLight / litRain / rainColor), `cell_gate`, `upwind_source`, `coverage_uv` |
| `rain.py`, `wet.py`, `strike.py`, `shelter.py` | the generators and materials; `eido_wet`, `eido_wet_eidoverse`, `wrap_material` / `unwrap_material`; the lightning objects and the ray cast (`make_strike_finder`, `resolve_targets`); the exposure maps (`capture`, `soft_map`, `exposure_at`) |
| `values.py`, `keys.py`, `_graph.py` | the keyed shader values group, bulk F-curves, the node builder with the weather hashes and value noise |
| `audio.py` | `make_weather_audio` / `WeatherAudio` (makeWeatherAudio), `record`, `write_timeline`, `bake_wav`, `merge` |

## Tests

They live in `blender/tests/weather/`. The first three need no Blender:

- `python -B blender/tests/weather/test_lightning_parity.py`: the engine's own `makeWeatherSystem` and
  `makeWeatherAudio` under deno over a 150 s storm, against the port: the profile tables, every frame's flash,
  light, bolt and sky strike, every strike, every bolt vertex, the impact pool, rainLight and rainColor, and the
  audio timeline.
- `python -B blender/tests/weather/test_moisture_contract.py`: Eanpa's accumulation contract, the time constants and
  frame-rate independence.
- `python -B blender/tests/weather/test_audio_tools.py`: `bake_weather_audio.py` and `merge_av.py` as the port runs
  them, refusals included, and the recorder's options.

These run in Blender with `bash run_blender.sh <test>`; tests that render go through the GPU slot:

- `test_blender_build.py` (no render): the generators against the JS (both `rain_cells` gates), shelter, splash
  placement, the lightning objects, keys, wrap and unwrap, the receiver flags, the rain shadow (dry under the
  awning, a smooth ramp at a building's lee), the heightfield fallback, every option the JS takes, the uniform names
  and the transition diagnostics, the one-system-per-scene registry, and dispose. It also saves the scene and
  reopens it in a fresh Blender (`check_saved_blend.py`). The reloaded file evaluates the same rain, light, bolt,
  sparks and shader values with no weather code loaded.
- `probe_eevee_facts.py`: the Blender facts the design rests on (F1-F8).
- `storm_street.py --mode check | stills | video`: a storm rolling in over a wet street while the camera walks down
  it, a close strike lighting it, a far strike's rumble, and the film with its rain and thunder track.
- `weather_states.py`: every weather state on the street, shown when its rain has wet the street most; the legacy
  names.
- `weather_examples.py`: the options and the source's examples (drop texture and procedural streaks, ember rain,
  the two wet models, ground_y splashes, splash_count 0, the two `rain_cells` gates at a cell edge, the procedural
  bolt, the five bolt styles, the impact close).
- `probe_puddles.py`: a road wetting, pooling and drying, close up.
- `test_facade_records.py` (no render): the facade's records in Blender axes, `make_weather_audio` in a loop of its
  own against the baked timeline, the profile's names, the front-face-only sparks, puffs and rings, and the plain
  options at values other than their defaults.
- `probe_strike_on_sand.py`: a forced strike on pale open ground, close: the flash, sparks, white-hot puffs, grey
  smoke and the scorch, from the side and from above.
- `rain_ab_webgpu_scene.js` with `rain_ab_blender.py`: the rain against WebGPU itself (see
  [Rain and splashes](#rain-and-splashes)). The first renders eidoverse's own `makeSky` weather in deno, from the
  worktree root: `RENDER_CODEC=libx264 RENDER_CQ=1 deno run --allow-all --unstable-webgpu --no-lock
  eidoverse/render_scene.mjs blender/tests/weather/rain_ab_webgpu.json` (through the GPU slot); the second renders
  the same set in EEVEE and compares.

`weather_states.py`, `weather_examples.py` and `probe_puddles.py` take `--dry`: they plan, key and check with no sky
bake and no render, so they need no GPU slot. `storm_street.py --mode check` is the same for the film.

The test street (`street_set.py`) is built from the shared CC0 library, with round one's interior-window rooms behind
its lit windows and shop fronts.

## Not yet ported

- **Eanpa's later rain look.** Millimetre streaks with a pixel-footprint floor, a denser near layer, PCG channels,
  and ballistic splash droplets that relocate every cycle instead of eidoverse's fixed ring spots. This edition draws
  eidoverse's streaks and rings.
- **Eanpa's volumetric impact smoke** (`impact_smoke.js`, eight samples through each puff). The gyroid burn puffs
  are eidoverse's.
- **A per-frame rain-exposure capture.** The exposure map is cast once per bake along one mean direction (softened
  for gusts, above). Moving occluders, and wind that turns during a bake, do not move the dry patches.
- **The listener exposure** (`weather_listener.js`, Eanpa's standalone): rain muffled when the camera is under a
  roof. eidoverse's audio never had it.
- **three's smooth light range window** on the strike light: EEVEE has a hard custom cutoff only (see Lightning).
- **makeSky's own weather.** `sky_worlds.js` builds the weather system inside `makeSky` and wraps the scene; here
  `make_sky` builds the sky alone and `make_weather_system(scene, sky)` attaches the weather to it. Until then a rain
  state has no falling drops (the sky's curtains and greying are there).
- **WebGPU-only machinery, dropped**: G-buffer exclusion (`mrtNode`: EEVEE draws Blended surfaces forward, after its
  G-buffer), the budgeted wrap queue (EEVEE compiles at render), pipeline warm-up (`pipeline_warmup_objects()`
  returns the weather's objects as an inventory), fixed bolt buffers (each bolt is its own mesh), `noSupportCheck`.
