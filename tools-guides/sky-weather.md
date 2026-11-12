# Sky packages, celestial bodies, weather and weather audio

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

**`make_sky`** is the sky of the Blender 5.2 EEVEE edition (`blender/eidoblend/sky/`). It is our sky, not
a stand-in. The cloud and celestial shaders of the WebGPU engine are ported line for line to GLSL
(`bake/sky.glsl`, from Eanpa Engine's `engine/sky_system.js`). They run in Blender's own GPU module once
per film frame, driven by a Python port of the same state machine: time-of-day palette, cloud presets,
transitions, weather, integrated wind. EEVEE then uses what they produce natively:

- the world shows the sky and lights the scene with it;
- a sun lamp is keyed from the palette;
- a hidden caster plane carries our cloud shadows on EEVEE's own sun shadows;
- the compositor blends distance fog toward the sky's fog colour.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sky import make_sky

sky = make_sky(bpy.context.scene, camera=cam, world='earth', hours=16.5, clouds='cumulus',
               cache_dir='C:/films/meadow/sky_cache')   # may be left out once the .blend is saved
sky.use_fog(density=0.0004)              # optional: three's FogExp2, in the sky's keyed fog colour
sky.bake()                               # the scene's frame range: sky layers, world, sun lamp, shadows
bpy.ops.render.render(animation=True)    # a plain render: everything per frame travels in keyed data
```

`cache_dir` defaults to `//sky_cache` beside the saved `.blend`. A script that builds its scene from
nothing has an unsaved `.blend`, so it must pass `cache_dir` (otherwise `make_sky` raises), or save the
`.blend` first.

| World key | Package |
| --- | --- |
| `earth` | Earth sky and its moon (moon radius 0.55°, the eidoverse film setting) |
| `ringworld` | Orbital / Halo: the ring band rising from the horizon to a 9.8 km crest, its rock-giant companion (16°), the ring-native cloud deck |
| `shieldworld` | Earth 5129323011 CE: the red giant (a 32° disc) riding the sun, the planetary hex shield, the shattered moon |

`SKY_WORLDS` maps each key to its label (`sky.label`). One call selects the whole world: its assets, its
celestial bodies, its placement and its per-frame behaviour all belong to the world, as in
`eidoverse/sky_worlds.js`, and a scene cannot substitute any of them. The assets come from
`eidoverse/assets/sky/` and `eidoverse/assets/sky/celestial/`, unchanged. An unknown key raises and names
the valid ones.

`weather` overrides `clouds`, because every weather state carries its own cloud preset. Here
`weather=None` is the default and keeps your cloud preset. The WebGPU facade defaults to `'clear'`,
which empties a cumulus sky.

## Direct the sky

Every direction call applies now, or at media time `at` (seconds, `(frame - scene.frame_start) / fps`).
`bake()` replays them in order, frame by frame, through the WebGPU update order: time → sky → weather →
lights.

- `set_time(hours, at=None)` sets the time of day and stops a running day cycle.
- `day_cycle(start_hour=6, seconds=60, at=None)` runs a full day over `seconds` of media time.
- `set_clouds(type, shape=None, at=None)` selects `clear`, `cumulus`, `stratus` or `cirrus`. `shape`
  overrides preset keys (`largeT`, `start`, `wispOn` ...).
  `transition_clouds(type, seconds=2.5, at=None)` eases every preset uniform there together.
- `set_weather(name, k=1, at=None)` selects `clear`, `fair`, `sunshower`, `overcast`, `rain`, `storm`,
  `cyclone` or `darkstorm`. `noreaster` and `hurricane` map to `cyclone`, `drizzle` to `rain`.
  `transition_to(name, k=1, seconds=45, at=None)` changes the weather over time: clouds, sky greying,
  sun and sky dimming and wind all ease together.
- `set_colors({cloud, star, sky, fog, rain, shield}, at=None)` retints those channels. Omitted channels keep
  their colour. `sun` is accepted for `star`. `shield` exists only on the shieldworld, where it recolours
  the lattice (linear HDR, values above 1 intended); another world prints a warning and ignores it, as the
  JS does. On the shieldworld `star` also recolours the red giant itself, over its authored ember ramp.
- `on_frame(fn)` calls `fn(sky, t)` every frame before the update. It is the WebGPU `renderFrame(t)`
  escape hatch for anything a schedule cannot say. Direction calls it makes belong to that frame run
  only; they are not recorded.
- `use_fog(density=0.0004, kind='exp2', near=1, far=1000)` adds distance fog: three's `FogExp2`, or `Fog`
  with `kind='linear'`. The sky writes the colour every frame, from the weathered horizon. The scene
  owns the density, as in WebGPU. The sky itself is never fogged, and neither are its elements (the
  ringworld's band, the shattered moon), whose WebGPU materials take no fog.
- `sun_dir` and `moon_dir` are the true unit directions in Blender world space (Z up). After dusk the sun
  lamp follows the moon. When something must follow the sun itself, such as a flare or flowers turning
  to it, read `sky.sun_dir`, not the lamp.
- `bake(frame_start=None, frame_end=None, overscan=0.08, layer_scale=1.0, plate_scale=1.0)` renders and
  keys the frames. A camera layer belongs to its camera: bake again after changing the camera's
  animation, the frame range or any direction call. The world is built for the range baked. Before that
  range it holds the first baked frame's sky, and after it the last's. On the ringworld it also renders
  the band's plate per frame (`plate_scale` against the frame), and `bake_plates()` renders the plates
  again for the last bake after a change to the band (see [Sky elements](#sky-elements-and-the-clouds-in-front-of-them)).
- `frame_states(frame_start=None, frame_end=None)` yields `(frame, t, lights)` per frame, with the scene
  on that frame and the sky in that frame's state. It is the state a bake renders, without rendering:
  use it to make something follow the weather or the sun frame by frame.
- `use_cloud_dome(radius=3072)` (or `make_sky(cloud_dome=True)`) draws the clouds over geometry beyond the
  radius, as WebGPU's cloud dome does. See [The cloud dome](#the-cloud-dome).
- `attach_cluster(cluster)` takes a custom celestial cluster that the scene places, and lights, dusts and
  overlays it like the shieldworld's own moon. See [Custom celestial clusters](#custom-celestial-clusters).
- `bake_env(width, height)` returns the environment of the current state as a float image (the band traced
  in on the ringworld). `bake()` already writes one per frame for the world.
- `label`, `planet_shine` (the companion body's reflected light, or `None` on Earth) and `internals`
  (`sky`, `wx`, `band`, `celestial`, `moon`: for engine work, not for scenes) mirror the JS getters.
  `apply_to_lights()` returns the frame's lamp values; `update(t)` computes them every frame, because
  lighting is not opt-in. As in Eanpa, the weather's skylight dim (`hemiDim`) greys the fog colour too.
  `wrap_scene()`, `audio_timeline()` and `audio` reach the weather system attached to this sky
  (`eidoblend.weather.make_weather_system` sets `sky.weather_fx`; [weather effects](weather-effects.md)): wetness wrapping, the weather-audio
  timeline and its carrier, or nothing and `None` without one. `make_sky(audio=False)` silences the
  timeline. `enable_reflections()` does nothing: EEVEE ray-traces reflections without a hook. makeSky's
  `renderer` and `hemi` have no counterpart: the bake renders in Blender's own GPU module, and the EEVEE
  world is the hemisphere light.

Every bake replays the sky from its starting point: the `make_sky` options, then every direction call in
the order made (immediate calls first, scheduled calls at their times), from the scene's first frame.
So a second `bake()` gives the same frames as the first, and an immediate call made after a bake joins
the next one. `bake(frame_start=25)` replays frames before 25 as state only, so its frames are the full
bake's frames. Change the sky through direction calls or `on_frame`: an edit made straight to
`sky.sky.U` is lost at the next bake.

The schedule is deterministic. The same calls give the same sky, frame for frame, in any background
Blender (`state_and_wiring.py` checks it). A saved film `.blend` renders with no frame handlers, as long
as its `sky_cache` folder stays beside it. When the `.blend` is already saved at bake time, the sky
images are stored with relative paths. `use_fog` splices its nodes into the scene's compositing tree
right after Render Layers. Whatever read the render image before now reads the fogged image (another
family's glare or grade, or the tree's output), so a post chain stays connected. A re-bake replaces only
the fog's own keys.

## What EEVEE receives

`bake()` writes, per frame, to `cache_dir` (default `//sky_cache` beside the saved `.blend`):

- `sky_cam_####.exr`, the **camera layer**: background and clouds for the exact screen rays of that
  frame's camera, sun disc included. It carries 8% overscan for depth-of-field and motion-blur jitter.
  The world finds each camera ray's pixel by direction, through that frame's keyed camera basis. The
  window comes from Blender's own camera frame (`Camera.view_frame`), so it is right for every sensor
  fit. `AUTO` fits the sensor width to the larger side, so a portrait frame's height. It is pixel exact
  with roll and lens shift. `probe_projection.py` measures a mean difference of 0.12% at 480×270
  `AUTO`, 0.09% at 270×480 `AUTO` and 0.07% at 270×480 `VERTICAL`, every case aligned with no pixel
  outside the layer.
- Motion blur: an image sequence shows frame `floor(t)` at a sub-frame (`probe_world_api.py` P6). So
  every per-frame key (camera basis, fill, caster, fog colour) is `CONSTANT` and held over `[f, f+1)`.
  A sub-frame therefore reads a layer through that layer's own camera. Before its range a sequence shows
  file `first - 1`, which is missing and renders magenta, so the bake writes that file as a copy of the
  first frame (all three sequences). After its range Blender holds the last file.
  `probe_subframe.py` checks sub-frames against the camera's true rays, on a pan of 6° per frame. At
  t = 2.75 the render matches layer 2 read through its own camera to 0.10%; the old half-frame keying
  measured 26%. At t = 0.75, before the first frame, it matches frame 1 to 0.14%, with no magenta.
  Rays that a fast pan carries beyond the 8% overscan within a frame fall back to the environment: 1.3%
  of the rays at t = 2.75 on that pan.
- `sky_env_####.exr`, the **environment**: a 1024×512 equirect in Blender's Environment Texture
  convention. Every other ray sees it: diffuse light and glossy reflections. It has no sun disc,
  because the sun lamp is the sun. Below the horizon it is ×0.45, as in WebGPU's `bakeEnv`.
- `sky_shadow_####.exr`: cloud **transmittance** toward the key light, 512² over 6144 m around the
  camera. It comes from the same density field the camera sees.
- `sky_state.json`: per frame, the lamp values, the fog colour and every uniform, for inspection.

The scene also receives:

- a sun lamp `eido_sky_sun`, or the `sun=` object you pass. Colour, strength and direction are keyed
  per frame from `applyToLights` × `sunDim`; the angle is the real sun's 0.53°. A three.js directional
  intensity is the same irradiance as a Blender sun's W/m², so the strength is the palette's number
  unchanged.
- the world: `Is Camera Ray` picks the camera layer. Glossy rays see the environment at the sky's own
  radiance, so a mirror reflects the sky it stands under in any weather. Diffuse light gets the
  environment at the keyed fill, `ambient × hemiDim`: the weather dims the sky's fill, as in WebGPU,
  where `hemiDim` scales only the hemisphere light. EEVEE's world lighting tells `Is Diffuse Ray` from
  `Is Glossy Ray` (`probe_world_api.py` P5). `world.sun_threshold` is 0: no second sun is extracted.
- `eido_sky_cloud_shadow_caster`, a plane invisible to camera and indirect rays. Its transparency is the
  transmittance map, projected along the light. A receiver anywhere under it reads the value of its own
  light ray, so cloud shadows are exact at every height under the plane, terrain relief included. It
  sits at 0.9 of the lowest cloud base the bake sees: 630 m under cumulus, 216 m under cyclone, 198 m
  under darkstorm's lowered storm layer. So hills, trees and towers below the clouds all receive.
  `make_sky(shadow_height=, shadow_ground=0)` puts it `shadow_height` metres above `shadow_ground`
  instead. Like Eanpa, the shadows dim only the sun lamp: shaded ground keeps its sky light.
  `make_sky(..., shadows=False)` leaves the caster out.

**`ambient` (default 1.0)** scales the world's diffuse light against the sky the camera sees.
Reflections always see the sky at its own radiance, whatever `ambient` is. In `probe_reflection.py` a
mirror floor gives 0.98 of the sky's brightness under cumulus, and 0.965 under rain (`hemiDim` 0.65)
at both ambient 1.0 and 0.5, while the diffuse sphere drops to 0.57 at ambient 0.5. At 1.0 the sky
lights diffuse surfaces as it is: a sunlit-to-shade ratio of about 4:1 at 16:30, which reads as real.
With its cloud-reflect hook on, WebGPU fills diffuse light with a hemisphere light worth about 0.4 of its
environment and keeps reflections at full. `ambient=0.4` gives that harder, darker shade, and mirrors
stay right. The weather table's `hemiDim` acts the same way. Darkstorm's 0.12 (Eanpa's value) leaves
matte objects nearly black under a sky a mirror still shows as dark grey.

**Exposure.** three's ACES divides by 0.6 before its curve, so AgX at exposure 0 sits about 0.7 EV
under it in the upper mids. The tests use `view_settings.exposure = 0.6` against WebGPU frames.

**Quality and cost.** `quality='film'` (default) runs 8 march passes × 60 steps with a 20-step light
march. `'draft'` runs 3 passes with a 512×256 environment. Measured on this machine:

| Frame size | Quality | Camera layer | Environment |
| --- | --- | --- | --- |
| 960×540 (layer 1114×627) | film | 0.8–0.9 s | 0.04 s |
| 480×270 | draft | 0.05 s per frame, all layers | |

Draws are split into strips, so a frame never holds the shared GPU for long.

**Sun disc bloom.** EEVEE has no bloom. For the WebGPU glow around the disc, add a compositor Glare
node (Bloom).

## Weather

Each state writes its cloud preset and overrides, cloud dim and radiance, weather grey, sun-disc
intensity, celestial visibility, rain curtains, wind and the light dimmers. These are the WebGPU tables
(`weather_system.py`, from Eanpa). Ported and seen in renders (`sky_matrix.py`, `sky_sequence.py`):

- every state's sky;
- sky greying (`mixG`, `horMul`, `greyTint`);
- `sunDim` on the lamp, and `hemiDim` on the world's diffuse fill;
- the darkstorm sealed canopy (the storm field: 2 × 12 steps);
- the integrated wind.

Ported, but not yet judged in a render of their own:

- the rain curtains under dense cells (`precipK`, in the sky shader);
- the below-cloud shafts (`shafts=`, off by default as in WebGPU);
- the wetness and surface-water time constants, as numbers the weather effects read.

Rain streaks and splashes, wet ground, lightning and the weather audio are in `eidoblend.weather`
([weather effects](weather-effects.md)): it attaches itself to a sky (`sky.weather_fx`), drives the
sky's flash through `on_frame`, and answers the facade's `wrap_scene()` and `audio_timeline()`.
Without it a rain state has no falling drops and darkstorm no flashes.

**Wind direction.** Clouds drift *with* `skyWind`, as in Eanpa: the density is sampled at `p` minus the
integrated displacement (`cloud_motion`). This repo's older WebGPU `eidoverse/sky_system.js` samples at
`p + skyWind·t`, so there the same shot drifts the opposite way.

## Sky elements and the clouds in front of them

The ringworld's band and the shieldworld's shattered moon are real EEVEE geometry, kilometres away. In
WebGPU they drew before the cloud dome and before every local opaque (draw slots: sky −100 < moon −99.5 <
shield and band −99 < clouds −98, with no depth written), so the local clouds always covered them, and so
did every local object: in `sky_worlds.js`'s words, "foreground opaques draw later, painting over the
depthless band". EEVEE's world is behind everything and its geometry shares one depth buffer, so each
element gets the same order its own way.

**The ringworld's band is a plate.** At its authored placement the band meets an eye-level view about
875 m out along the ring, and its walls about 960 m out at 30°. In one depth buffer, any terrain, set or
mesa past that, inside a 60° wedge each way along the ring, would lie behind the band: a third of the
horizon. So `make_sky` moves the band, its walls, its cloud sheet and the band's two lamps into a scene
of their own, `eido_ring_plate` (`Ringworld.make_plate`). Its film is transparent, its camera has Eanpa's
20 m near plane, and it takes the main scene's world, which lights the band as before. `bake()` renders
that scene per frame from the bake camera's own window, with both scenes on that frame (the band reads the
sky's environment and the cloud-shadow map through image sequences, which follow the main scene's frame),
and composites it into the camera layer, the clouds over the band over the sky:
`C + (1 − a)·(P + (1 − Pa)·B)`. `B` is the sky without the band (`sky_base_####.exr`); the bake keeps it,
so `sky.bake_plates()` can render the plates again after a change to the band's materials or options,
without baking the sky again. The band thus reaches the frame through the world: every local object
draws in front of it, the fog and rain walls (which stay in the main scene) veil it, and the clouds
cover it. Eanpa does the same with its private sky depth layer, composited behind local geometry.
`ring_band_behind_local.py` puts five mesas 1.5–4 km out on a 12 km desert. With the band as geometry,
the three mesas inside the band's wedge disappear behind it, and the walls cut the fourth. As a plate,
all five stand in front of the band, as in WebGPU.

The plate covers the camera layer's window at the frame's own pixel density (`bake(plate_scale=1)`), so the
band's textures take the mip levels a direct render gives them, and its film filter is one pixel wide: the
main render filters it again when it samples the world. Against the band rendered as geometry, the 11:00
horizon differs by 2.1/255 over the frame and the 23:00 one by 1.8/255 (most of it the fog wall, which now
veils the band's foot, as in WebGPU); the night water on the far arc reads 5% brighter, and the band is a
touch softer (18% less pixel-to-pixel contrast in a crop of the arc: the world resamples the plate). A finer plate
(`plate_scale=1.5`) is crisper but resolves the wave normals further, and the night glints read 12% brighter.
A plate costs about a second per frame at 1114×627 once its shaders are compiled (the first takes about
20 s). The eclipse proxy is in both scenes, because it shadows both suns. Reflections on local metal see
the band through the environment, which traces the band analytically, as WebGPU's `bakeEnv` does. In the
viewport the main scene shows no band: look through the camera in Rendered mode after a bake, or open the
`eido_ring_plate` scene.

**The shattered moon** sits 34 km out, beyond any local geometry, so it stays in the main scene, and its
materials composite the sky over themselves: `eido_sky_overlay` (`sky_view.py`) reads the frame's shield
and cloud layers through the keyed bake camera and lays them over the surface, for camera rays only. An
opaque element shows `(1 − a)·surface + C`; a blended one emits `c·(1 − a) + α·C` over
`(1 − α)·behind`. A custom cluster does the same (`attach_cluster`). `probe_eevee_facts.py` measures the
EEVEE facts this rests on: light linking (F1), `Is Camera Ray` in a material (F2), a Blended
`Add(Transparent(1 − a), Emission)` being exactly a premultiplied over (F3).

**No fog on sky elements.** WebGPU builds every ring and moon material with `fog: false`: they carry their
own air. `use_fog` leaves them clear too. The band is in the world, where the depth is the sky's, and the
moon's fragments, debris and the asteroid moon write 1 into the `eido_sky_element` AOV
(`sky_view.mark_sky_element`), which the fog's compositor nodes read. Before this, `use_fog(0.0004)`
turned the ringworld's band into a pale ghost above the clouds and the moon's fragments into dark blobs.
One residue remains: the fog tells geometry from sky by the depth pass, one value per pixel, so where a
debris grain smaller than a pixel sits in front of the sky, the sky around it in that pixel is fogged with
it. Under fog at night that shows as dark dots in the debris river where it runs under a cloud
(out/verify/fog).

So a sky world's bake splits the camera rays into layers, each its own pass (`SkyBaker.camera_layers`):
`sky_cloud_####.exr` (the clouds, premultiplied; the expensive march, once), the background (atmosphere,
stars, moon, celestial body, moon dust), and on the shieldworld `sky_shield_####.exr`. The world gets
`sky_cam` (everything composited, as on Earth, with the band's plate on the ringworld); the overlay group
gets the cloud and shield layers. Earth without a dome still bakes one composite pass, exactly as before.
`moving_camera_worlds.py` checks the keying a moving camera relies on: in each world, frame 5 of a bake
whose camera walks and turns equals a bake of a camera parked at frame 5's pose, to 0.00/255.

### The ringworld

`make_sky(world='ringworld')` builds the `eido_ringworld` collection from the authored
`RINGWORLDskyelement.glb`, at its authored placement: the group at 4940 m, recentred on the walls'
bounds as Eanpa does, so the ring axis lies at 4921.7 m. The band passes 78 m under the stage, rises out
of the ground about 780 m away and crests 9.8 km overhead.

- **The band** (`eido_ring_band`) is Eanpa's `makeRingTerrainGeometry`: 4096 rows around, concentrated
  toward the observer, 512 to 64 segments across by distance, stitched so transitions share every edge,
  with two closing skirts: 626 565 vertices, 1 228 416 triangles, built in about 9 s. The relief is the
  repo's 16-bit `ring_band_height.png` × 85 m (`terrainHeightMeters`), eased in from 700 to 2000 m of arc
  (`localReliefBlend`) so no peak pierces the stage. Eanpa's own eroded v4 relief is ported too (see
  **Eanpa's v4 band** below), but its files are not in this repo. Eanpa also closes its shorelines with
  a separate level sea cylinder 2 m above the sunken land;
  that is not ported on purpose: two surfaces 2 m apart at 10 km fight in EEVEE's one depth buffer (Eanpa
  itself needed a private depth layer with a 20 m near plane for them). Here the land mask holds the
  lakes level on the one displaced surface. The repo's height field steps up at every shoreline within
  a few metres, while the far rows sample it every 7 to 15 m, so each row samples the relief prefiltered to
  its own vertex spacing: full detail at the observer, a 6-texel blur on the far arc, blended continuously
  with distance so the level-of-detail rows stay seamless (`reliefPrefilter`, on by default; the Blender
  edition's own). On a synthetic shoreline it turns the far rows' 6-level stair into a 32-level ramp.
  On the real band the change is slight, and the spiky coasts the v1 band shows on the far arc at night
  remain. They go with the v1 maps, not with the land mask: with the same mask and the same rows, the v4
  maps draw smooth shores (`ring_relief_v4.py`). The likely cause, not isolated, is that the v1 height
  steps up at every shoreline and its normal map's ridges follow the coasts, and the lightweight waves read
  that same normal map. The normal map carries the fine relief in the shading either way, as in Eanpa.
  `geometryRelief=False` keeps the GLB's own flat terrain mesh, shaded by the normal map alone.
- **Its material** is the lit-band graph: the authored colour map (8 × 1 around, Eanpa's UV phase), lakes
  where the mask is black (soft shoreline, wet sand, dark water whose silver comes from reflection),
  baked cavity AO, the band normal map in the analytic cylinder frame, two scrolling wave reads on the
  water, and in emission the air's inscatter, the foot veil at the horizon and the night water glint
  under planetshine. `arcShade` (`eido_ring_arc_shade`) is Eanpa's newest, per pixel: the wide
  terminator, eclipsed by the band itself (`eido_ring_eclipse`, Eanpa's `ringSolarVisibilityNode`); the
  golden band; the planetshine visibility; per-channel transmittance over the height-integrated optical
  length of the slant path (an 8 km scale height, so the low band at your feet stays crisp and the high
  crest takes the haze); the sub-cloud rain veil with its drifting curtains; the inscatter that
  collapses at night and under the eclipse; and the foot veil, faded in from 1.6 to 3.8 km so it lies only
  on the band's true foot.
- **Eanpa's v4 band** (`src/ring_relief.js`, ported as `decode_ring_relief` and `load_ring_relief`). Eanpa
  displaces an eroded relief: `ring_relief_v4.bin.gz`, 4344 × 1448 half-float heights with their own normals
  and AO, eroded by 3.1 million droplets. It comes with its matching albedo `ring_albedo_v4.png`, and keeps
  the v3 relief's normals for the water waves. `make_ringworld(..., {'reliefDir': folder})` builds the band
  from that set. `make_sky` does it automatically when `eidoverse/assets/sky/celestial/` holds the files,
  and `ring={'reliefDir': False}` keeps the v1 maps. The decoder matches Eanpa's own byte for byte
  (`js_parity.py`), and refuses truncated or foreign files as the JS does.
  The heights go in as stored, × 85 m, peaking at 73.6 m. The land mask is resampled to the relief's
  resolution and still holds the lakes level. The normal and AO maps are written once into the ring's cache
  as PNGs in the repo maps' convention, and the material reads the AO from their alpha, at
  `bandNormalScale` 1, as Eanpa's host sets them. The first build decodes and writes those maps in about
  45 s; later builds read them from the cache in about 7 s.
  By day the v4 band reads like satellite imagery: soft eroded ranges with drainage, open water and a
  green-blue palette, close to Eanpa's own frames. The v1 relief is harder and browner. At night the far
  arc's lakes glint silver against dark land. Their shores are smooth natural outlines, where the v1 band
  draws spiky, flame-like coasts (`ring_relief_v4.py` renders both, day and night).
- **Its light** comes from its own two lamps, `eido_ring_band_sun` (the true sun at full strength 3.2,
  the local palette by day handing over to daylight white below the horizon) and `eido_ring_band_shine`
  (planetshine 0.55, the giant's warm white). Light linking keeps them on the band alone, and links the
  scene's sun away from it: WebGPU's per-material `lightsNode`, done with Blender's own linking
  (`probe_eevee_facts.py` F1). Shadow linking (F5) gives Eanpa's custom light model: the band sun is
  shadowed only by the eclipse proxy and the cloud sheet (transparent shadow), the planetshine only by the
  sheet. Nothing of the local scene shadows them. The near band also lies under the local deck, as in
  Eanpa: `eido_sky_cloud_shadow_caster_band`, a twin of the cloud-shadow caster that only the band sun
  sees, lays the local clouds' shadow on the band within its 6 km square. It sits at the deck's top
  (`cloud_shadows.deck_top_for`: 730 m under the ring's cumulus deck, 1670 m under the darkstorm canopy),
  so the band rising through and beneath the clouds reads its own light ray's transmittance through the
  whole deck, out to about 4 km of arc under a storm (Eanpa weights it in within 2.5–5 km). The map
  marches through a sealed canopy as well: Eanpa skips that march once a storm makes celestial visibility
  zero, because the scene's sun is zero then, but the band's sun is never dimmed by weather, and with the
  march skipped a darkstorm left the band's foot in full sun under a black sky. The map is projected
  along the cloud key, which is the moon at night, so the twin is keyed off then
  (`eido_band_caster_on`; the near band faces away from a sun below the horizon anyway). `bandCastShadow=True` adds the band's relief and walls to
  the band sun's blockers (off by default, as in Eanpa). It changes nothing visible yet: at 5–10 km
  EEVEE's sun shadow draws no relief self-shadow, and `ring_options.py` measures the night frame
  identical with and without it.
- **The eclipse** (Eanpa `ring_eclipse.js`): `eido_ring_eclipse_proxy` is a shadow-only cylinder on the
  band's axis, 966 m wide, invisible to every ray but shadow rays. Its radius is 5025 m: 25 m behind the
  band, so a lit band point never compares its depth against the proxy wall just behind it at the band
  sun's 2.8 m texels (the eclipse edges move by under 0.2°). It shadows the band sun, so the near arc
  eclipses the far one, and it shadows the scene's sun, so every local receiver gets its own eclipse, as
  Eanpa's `sky.setSolarOcclusion` gives each PBR receiver its `solarVisibilityNode`.
  EEVEE's penumbra from the sun's 0.53° disc is the analytic penumbra's width. The camera's own solar
  visibility still dims the sky (`solarSkyVisibility = 0.16 + 0.84·v`), and the sun lamp is not dimmed by
  it (`sky.solar_occlusion`). With the authored noon in the ring plane, noon is arch night: at 12:00 the
  stage stands in the band's shadow under a sky at 0.16.
- **The walls** (`eido_ring_walls`) get fresh cylindrical UVs in 60 m panel tiles and the SolarPanel001
  set, in the authored emissive panel look. **The cloud sheet** (`eido_ring_clouds`) floats 280 m above
  the band: Eanpa's satellite-scale field (macro systems, a warp and five filament octaves, exact around
  the ring), baked once into `ring_cloud_field.exr`, drifting with the sky's wind and taking its
  coverage, density and colours from the sky's own cloud uniforms. At local night the sheet over the far
  arc, which is still in sunlight, takes Eanpa's constant daylight grey (`farDaylight`), so a large
  covered system of the field reads as an even grey sheet over the lit arc. **The fog boundary** (1250 m) and
  **the rain wall** (1380 m, only in real rain) ring the stage in the weathered horizon colour. They stay
  in the main scene, depth-tested against the local geometry, so a terrain past them takes their haze, and
  they veil the band's plate. They also veil the clouds behind them, where WebGPU draws its cloud dome over
  them. The clouds' overlay cannot go on them here: a wall cannot tell sky behind it from a mesa behind it,
  and would paint clouds onto the mesa. The difference is a veil over the cloud bases in the bottom fifth
  of the sky in rain, and at the horizon line: under a storm at 10:30, a mean of 3.9/255 over the frame,
  29/255 at most along the horizon (out/verify/haze_order).
- **The sky** runs ring-native (`ringCurve` 5000): the deck's rounded-corner chord profile (flat 450 m
  over the local scene, a 350 m circular fillet by the crest), its containment strip, the slope shear,
  the slab march window, the storm layer's bisection: the `RING_*` constants in `sky.glsl`.
  The environment traces the band analytically, so reflections and the sky's light carry the arc.
- Per frame, `eido_ring_keys` holds the arc's values (LINEAR keys) and the two lamps are keyed. The
  camera's clip end is raised to 16 km and EEVEE's shadow pool to 1024 MB (in the plate scene too).

`make_sky(..., ring={...})` passes options to `make_ringworld` under the JS names (defaults in
brackets):

- the band's look: `planetShineColor` (the world's), `hazeNightLevel` (0.055), `shoreTexels` (3),
  `shoreWetness` (0.2), `waterWhite` (False: lakes are the mask's black), `bandAOFloor` (0.62),
  `bandAOPackedNormal` (False: AO from the AO map's alpha), `bandNormalScale` (1.4),
  `analyticBandNormal` (True; False uses the mesh's own normals as the frame), `inscatterEnabled`,
  `inscatterNightLevel` (0.28), `footVeil`, `footWidthNight` (0.075);
- the water: `waves` (`'lightweight'`, two scrolling reads of the band normal map; `'full'`, the
  procedural look-dev field of two tileable value-noise octaves; `False`), `lightweightWaveSpeed`
  (0.0065), `lightweightWaveAmp` (0.26), `waveAmp` (0.55, the full field);
- the analytic path: `litBand=False` paints the band through emission as the JS's comparison path does
  (`litArc` with the sun rake, `nightSide` with the bi-directional planetshine hillshade, `sparkle`),
  with no band lamps; `nightTint` (the planetshine colour at luma 0.343), `nightSat` (1.3),
  `nightLevel` (1.2) shape its night side;
- the geometry: `geometryRelief` (True), `terrainHeightMeters` (85; `heightMeters` too),
  `localReliefBlend` ((700, 2000) m of arc), `around` (4096), `across` (512), `panelTile` (60), and the
  Blender edition's `reliefPrefilter` (True);
- the lamps: `bandLights`, `bandSunIntensity` (3.2), `bandShineIntensity` (0.55), `bandCastShadow`
  (False), `bandShadowMapSize` (4096: texels of 2 × 1.15 R / size, 2.8 m) or `bandShadowTexel` in metres;
- the sky elements: `ringClouds`, `cloudHeight` (280 m above the band, Eanpa's), `cloudAtlas`
  ((8192, 256), baked once), `fogWall`, `rainWall`, `fogWallRadius` (1250);
- look-dev: `debugBand='basic'` (flat red, to bisect geometry from material) or `'lighting'` (red the
  eclipsed terminator, green the planetshine visibility, blue the night relief).

`ring_options.py` exercises every one of these from one camera and sky: the material options rebuilt on
one band by day, the night-only ones (`hazeNightLevel`, `footWidthNight`, `inscatterNightLevel`, the
analytic night side) re-baked at night, both compared on screen with the default; and the build options in
a few rendered builds, each with a numeric check of what it owns. Three JS options have no counterpart: `bandEnvIntensity` (EEVEE has no per-material environment intensity:
the band takes the world's light, which `make_sky(ambient=)` scales), `bandLightLayer` (light linking
isolates exactly; there is no camera-layer test to dodge) and Eanpa's `cloudShadowStrength` (EEVEE's
transparent shadow takes the sheet's own alpha). The SPOM options (`pomEnabled`, `pomScale`,
`pomMinLayers`, `pomMaxLayers`, `pomShadow`, `pomShadowFloor`, `pomShadowSteps`) are superseded by the
displaced relief, as in Eanpa, which leaves SPOM off.

```python
sky = make_sky(scene, camera=cam, world='ringworld', hours=23, clouds='cumulus',
               cache_dir='C:/films/halo/sky_cache')
sky.bake()      # the band keeps its look: the far arc is at its own noon while the stage is dark
```

### The shieldworld

- **The red giant** is the sun: its shader (Eanpa's `redgiant.js`, generated per world by
  `bake/celestial.py`) rides the sky's sun with the default disc and glow lobes off. Fine boiling
  granulation over a handful of giant convection cells, one hot patch, three slowly forming sunspot
  pairs, strong limb darkening that reddens, the H-alpha rim, a three-term corona, and prominences: five
  limb slots and three front events on a deterministic schedule (`flare_env`, the same schedule the
  shield reads). The palette is Eanpa's warm giant tint; sunset stretches across the 16° radius of the
  disc (`sourceAngularRadiusDeg`), and the cloud phase is softened for a wide source.
- **The shield** is a hex lattice on a virtual flat ceiling (21 km dome, gnomonic cells), with five
  radiation-hit slots that light whole hexagons in expanding rings, more and harder while a flare peaks,
  near-silent at night. It is dimmed by the clouds' shadow column where the view crosses the deck, and
  drawn between the sky and the clouds. WebGPU's `bakeEnv` never sees it, and neither does the
  environment here.
- **The shattered moon** (`eido_shattered_moon`) is the authored `asteroid_cluster_v3.glb`, 16 fragments
  at scale 1400 on their orbit (rising 22.3 h, a 6.2 h transit, 34 km out, outside the shield), with
  Eanpa's celestial shading (a Lommel-Seeliger/Lambert blend and a horizon guard), its bounded drift
  (`make_fragment_motion`: no two envelopes ever touch) and tumble. Its accretion dust is marched in the
  sky shader behind the fragments; its debris river is 7000 grains in Geometry Nodes, evaluated from
  Scene Time. It shows only at night and high enough (Eanpa's elevation-gated fade).
- **The night**: the shield's cyan and the moon's amber light the scene through the world's diffuse
  rays (`eido_sky_diffuse_tint`, `eido_sky_ambient_add`, keyed), the lattice glow washes out the
  Milky Way and lifts the sky floor. The key light at night is the moon itself: the sky's moon follows
  the cluster (Eanpa's `setMoonDirection`), at `sky_worlds.js`'s `moonLightIntensity` 1.15 in the giant's
  amber, three times Earth's moonlight, so a moonlit shieldworld night reads warm and bright on the
  ground. The dust's opacity is capped at 0.38 with its colour scaled to match, so it stays
  premultiplied.

`make_sky(..., redGiant={...})` passes `angularRadius`, `granScale`, `plasmaSpeed`, `hexScale`,
`shieldRadius`, `flares`, `flareBoost`, `starColor`, `shieldColor`, `paletteTint`. `flares=[]` means no
prominences and no sunspot events, as the JS's `opts.flares ?? FLARES` does. The shieldworld always has
its shield, because `sky_worlds.js` forces it; for engine work, `make_red_giant({'shield': False})` leaves
it out. `redgiant_options.py` renders each option against the default.

### The cloud dome

`make_sky(..., cloud_dome=True)` (3072 m, WebGPU's `DOME_R × 0.96`) or a radius in metres puts a sphere
around the camera whose material shows the frame's cloud layer through the keyed bake camera. Geometry
nearer than the radius hides it; geometry beyond gets the clouds over it, as WebGPU's dome does. With the
dome, the world shows the sky behind the clouds (`sky_back_####.exr`; on the ringworld the band's plate is
composited into it, and the dome draws the clouds over both). Opaque sky elements keep compositing
the shield, and the clouds wherever they are nearer than the dome (the overlay's `Color` / `Alpha`).
The dome is Blended, and EEVEE draws Blended objects farthest origin first (`probe_eevee_facts.py` F4),
so its origin is parked a thousand kilometres ahead of the camera and it draws under every other
transparent surface. A blended sky element with the overlay therefore lands on the dome's clouds
and composites every cloud over itself (`ColorAll` / `AlphaAll`): `c·(1 − a) + α·C` over
`(1 − α)·(C + (1 − a)·B)` is exactly `C + (1 − a)·(c + (1 − α)·B)`, the clouds over the element over the
sky. `dome_and_spatial.py` renders a ridge 9 km out with and without it.

Like WebGPU's, the dome lays every cloud on its ray over geometry beyond the radius, including clouds
farther away than that geometry. Low on the horizon the distant deck therefore covers the 9 km ridge,
and its peaks show only through gaps between the clouds. Use the dome when distant terrain must sit
inside the weather, not for a clear view of far landmarks.

### The sun corona

```python
from eidoblend.sky.sun_corona import make_sun_corona
corona = make_sun_corona(scene, petals=12, size=400)   # distance=1500 m, color in linear rgb
corona.bake(sky)                     # keys the card over the frames; open_fn(t, sky) -> 0..1 overrides
```

A camera-facing card parked along the true sun, drawn additive (Blended, emission over full
transparency) and depth-tested, so the horizon and nearer geometry hide it. The petals are rounded spoons
with a brighter midrib that lengthen with `open` and turn slowly. `update(camera, sun_dir, open, t)` and
`key(frame)` drive it by hand. EEVEE has no bloom: a compositor Glare node gives the WebGPU glow.

### The asteroid moon pipeline

```python
from eidoblend.sky.asteroid_moon import bake_asteroid_moon, make_asteroid_moon
bake_asteroid_moon(height_png, albedo_png, out_dir)      # once: the three artifacts
ob = make_asteroid_moon(out_dir + '/asteroid_moon_mesh.f32', out_dir + '/asteroid_moon_baked.png',
                        out_dir + '/asteroid_moon_normal.png')
```

The bake-once tool is ported whole: three's icosahedron(24) carried onto the analytic potato and
displaced into real craters by the tileable height (triplanar), a high poly that re-evaluates the potato
at every sub-vertex (16 per base face, 200 000 triangles), and two atlases rasterised in the runtime UV by
Blender's GPU module: the light-neutral shaded albedo (cavity and slope) and the object-space normals. The
mesh file keeps the JS layout (count, positions, normals, UVs, three.js space). The runtime loader gives
the celestial lambert material over the normal atlas. The source pair is yours to choose: the WebGPU
recipe used an AI-generated height and albedo, and the test bakes a CC0 ground set from the shared cache.
The JS loader's `uniforms` (sunDir, sunCol, gain) are the `eido_moon_keys` node group here, which the
runtime material reads: key its `sun_dir` (Blender world space), `sun_col` and `gain` values.

### Custom celestial clusters

The shieldworld owns its shattered moon; do not add a second one there. For toolkit work or a custom
celestial scene, build the cluster yourself and place it. `make_shattered_moon` takes a GLB with separate
fragment meshes, not one fused sphere:

```python
from eidoblend.sky.asteroid_moon import make_shattered_moon
cluster = make_shattered_moon(scene, glb_path, spread=1.75, scale=1400)   # scale: the group's starting scale
cluster.group.location = (0, 30000, 14000)       # placed (and animated, if you like) by the scene
sky = make_sky(scene, camera=cam, world='earth', hours=18.6, cache_dir=...)
sky.attach_cluster(cluster)                      # lit by the sky's true sun, dust and clouds included
sky.bake()
```

`attach_cluster` makes the bake treat the cluster as the shieldworld treats its moon, with three
exceptions: the scene owns the group's transform, nothing fades it, and there is no orbit. Every frame
the fragments drift and tumble on Eanpa's bounded motion. The sky's true sun lights them. The cluster's
`uniforms` keep `sun_col`, `gain` and `fade`. The accretion dust is marched in the sky shader behind the
fragments, following the hero fragment through the group's world matrix. The sky's clouds composite over
it all. A bake keys the fragments and the shading values. It never touches the group's own keys, so the
scene can move the cluster across the sky.

Without a sky, `cluster.bake(sun_dir=...)` keys the fragments over the scene's frames, lit by
`cluster.uniforms`: `sun_dir` in Blender world space, `sun_col`, `gain` and `fade`. That gives the
fragments and the debris river. The dust needs a sky's shader. `cluster.update(t)` and `cluster.key(frame,
values)` are the per-frame pieces, as the JS's `update(t)` is. Materials and keys are shared by name, so a
scene holds one cluster. `custom_cluster.py` renders both cases.

### The spatial cloud pass

WebGPU's `cloud_spatial.js` renders the sky domes at 1/div for the current camera, with no history, and
composites them back through proxy shells. The bake already works that way: every frame's camera layer
is rendered for that frame's camera alone and composited by direction. So
`make_spatial_cloud_pass(sky, div=2)` sets the bake's layer scale (`sky.layer_scale`), and
`set_divisor`, `get_resolution` and `dispose` work as in WebGPU. `render()` has nothing to do per frame.

## Lower-level systems

These are what the facade composes, for toolkit work. The first six do not import `bpy` at module level.

| Module | Entry and lifecycle |
| --- | --- |
| `sky_system.py` | `SkySystem(opts)`: `set_time`, `set_sun`, `set_moon_direction`, `set_clouds`, `transition_clouds`, `set_colors`, `get_colors`, `update(t)`, `apply_to_lights()`; uniforms in `.U` under the TSL names |
| `weather_system.py` | `WeatherSystem(sky)`: `set_weather`, `transition_to`, `update(t)`, `sun_dim`, `hemi_dim`, `set_colors`; `WEATHER`, `LEGACY_STATES` |
| `palette.py` | `TOD`, `tod_at`, `tod_disc` (extended source), `PRESETS`, `sun_moon_at(hours)`, `three_to_blender`; three (x, y, z) = Blender (x, -z, y) |
| `worlds.py` | `WORLDS`, `SKY_WORLDS`, `ring_constants(R)` (the deck's `RING_*`), `ring_deck_y(z, k)` |
| `redgiant.py` | `make_red_giant(opts)`: `celestial_glsl()`, `shader_defines()`, `flare_env(f, t)`, `set_shield_color`, `set_star_color`, `attach(sky)`, `update(t)`; `FLARES`, `PALETTE_TINT` |
| `bake/baker.py`, `bake/celestial.py` | `SkyBaker`: `camera_layer(output=)`, `camera_layers`, `environment`, `shadow_map`, `weather_at`; `weather_map()`, bit-exact with the JS `fbmAt`; `red_giant_glsl`, `dust_glsl` |
| `ringworld.py`, `ring_materials.py` | `make_ringworld(scene, assets, opts, cache_dir)`: `bind_weather`, `update(t)`, `key(frame, vals)`, `eclipse_k(dir, origin)`, `unlink_scene_sun`, `attach_lights`, `dispose_lights`, `info`; `ring_terrain_arrays`, `ring_cloud_field`, `ring_solar_visibility`, `eclipse_k`, `decode_ring_relief`, `load_ring_relief` |
| `asteroid_moon.py`, `moon_materials.py` | `make_shattered_moon` (`update(t)`, `key`, `bake`, `uniforms`, `dispose_textures`), `make_fragment_motion`, `bake_asteroid_moon`, `make_asteroid_moon`, `icosahedron_nonindexed`, `potato` |
| `sun_corona.py`, `cloud_dome.py`, `cloud_spatial.py` | `make_sun_corona`, `build_cloud_dome`, `make_spatial_cloud_pass` |
| `sky_view.py`, `nodes.py` | the keyed bake camera (`eido_sky_view`), the overlay group, and the node-graph builder the materials are written with (`eido_h21`, `eido_vnoise2`: the WebGPU hash and value noise) |
| `world_nodes.py`, `cloud_shadows.py`, `fog.py` | the EEVEE world, the caster (`caster_height_for`) and the compositor fog built from a bake |

`make_sky` options pass straight to `SkySystem`, under the WebGPU names:

- `azimuth` aims the sun's arc;
- `maxElevationDeg`, `azSpanK`, `moonAngularDeg` (the moon's angular radius), `sourceAngularRadiusDeg`,
  `paletteTint`, `cloudPhaseSoften`, `cloudMultiScatterFloor`, `moonLightColor`, `moonLightIntensity`,
  `cloudLightScale`, `cloudAmbScale`, `cloudFadeDist`, `shafts`, `shaftDensity`;
- `cirrus_atlas=` points at an ice-trail atlas.

## Tests

`blender/tests/sky/`. Run each with `bash run_blender.sh <test> [args]`, one render at a time on a
shared GPU. They write to `blender/tests/sky/out/`.

- `meadow_cumulus.py` (`--views up,sun,level,high`): the first-priority probe. A cumulus late afternoon
  (16:30, sun at 23.7°) over a meadow made from our blade atlas, with white, grey and chrome spheres. It
  picks a sunlit spot from our own shadow field.
- `sky_matrix.py`: 4 presets × 4 times, plus 7 weather states, on one stage.
  `contact_sheet_matrix.py` assembles them.
- `sky_sequence.py`: a weather transition, a day cycle and wind drift, baked once and rendered as plain
  animations (with an H.264 preview). `--rebake` bakes twice on the same `Sky` and checks that the
  second bake's camera layers are bit-identical to the first's.
- `probe_world_api.py`: the EEVEE world facts the design rests on (P1–P6).
- `probe_projection.py` (`--res 270x480 --fit AUTO|VERTICAL`): camera-layer alignment, portrait
  included.
- `probe_subframe.py`: motion-blur sub-frames read each layer through its own camera, with no magenta
  before the first frame. It also renders real motion blur (steps 1 and 3) to look at.
- `probe_reflection.py`: a mirror floor holds the sky's brightness under rain at `ambient` 1.0 and 0.5,
  while a diffuse sphere follows the fill.
- `probe_caster_height.py`: a plateau at 300 m gets its cloud shadows with the caster under the cloud
  base (brightness spread 31 levels). With the old fixed 150 m plane it gets none (3 levels).
- `state_and_wiring.py` (no GPU): re-bake and partial-bake replay, the camera window against Blender's
  sensor-fit rules, the fog splice, the caster height.
- `inspect_exr.py`: layer statistics and previews.

`blender/tests/sky_worlds/` covers the sky worlds, written to `blender/tests/sky_worlds/out/`:

- `world_views.py --world ringworld|shieldworld|earth --hours 11,23 --views horizon,up,giant,moon,side`:
  a world from a small stage (ground disc, white, grey and chrome spheres, a monolith) at each hour and
  view. `--dome`, `--weather`, `--quality film`, `--save-blend`, `--out`, `--tag`, `--plate-scale`.
- `shader_variants.py`: every world's variant of `sky.glsl` compiles, and the layered passes recompose
  exactly into the single composite pass.
- `state_and_api.py` (no GPU): the world table against `sky_worlds.js`, the band's placement, rows and
  relief, the light and shadow linking, the eclipse proxy, arch night at noon, the deck constants, the
  moon's orbit and visibility, the shieldworld's night light, the shield and star colours, bit-exact
  replay of the band and moon state, the lamp and texture lifecycles, the facade's delegation to a
  weather system, the spatial pass (`width`, `height`, `resize`, `dispose`). It also checks that the band
  takes the v4 relief exactly when the repo carries the set, that the band, walls, sheet and lamps sit in
  the plate scene with the eclipse proxy in both scenes, and that the shieldworld's own moon refuses
  `attach_cluster` and a standalone `bake`.
- `ring_options.py [--parts day,night,build]`: every `make_ringworld` option exercised and rendered
  against the default from one camera and sky (sheets `sheet_day`, `sheet_night`, `sheet_build`); an option
  that changes nothing on screen, or in the data it owns, fails.
- `world_sequence.py --world ringworld|shieldworld`: a day cycle baked once and rendered as plain frames
  (a strip), then the saved `.blend` reopened and a frame rendered from the file alone.
- `js_parity.mjs` + `js_parity.py` (deno, no Blender): the red giant's flare envelopes and shield impacts,
  the ring's solar visibility, and the fragment motion (with and without separation passes) match the
  Eanpa sources to 1e-9. The ring relief decoder matches Eanpa's `decodeRingRelief` exactly on the real v4
  set, texels and refusals.
- `probe_eevee_facts.py`: F1 light linking, F2 `Is Camera Ray` in a material, F3 the blended over,
  F4 the Blended draw order, F5 shadow linking.
- `asteroid_moon_pipeline.py`: the bake-once tool and the runtime loader, end to end, then every bake
  option (`detail`, `hiSub`, `bakeSize`, `seed`, `squash`, `reliefAmp`, `tile`) on small bakes.
- `redgiant_options.py`: every `redGiant={...}` option rendered against the default, over the frame or
  locally (a prominence at the limb). The star's options are seen at sunset. The shield's are seen at
  night, looking up from 8 km off-centre: the shield is a sphere about the origin, so only there does
  `shieldRadius` show. The script also checks `shield=False` and `flares=[]` without the GPU (sheets
  `sheet_star`, `sheet_shield`).
- `custom_cluster.py`: a custom celestial cluster on its own, keyed by `cluster.bake`. Then the same
  cluster in an Earth twilight sky through `attach_cluster`, in a clear sky and under `--clouds` (cirrus).
  It checks the drift and tumble, that the scene's own group animation is kept, and that the dust sits on
  the hero fragment, and renders each sky with and without the fragments.
- `ring_relief_v4.py [--no-render]`: Eanpa's `ring_relief.js`. It checks the decoder's round trip and its
  three refusals, and the v4 set's orientation, normal convention and packed AO. Then it renders the v4 band
  beside the v1 band, reading the set from Eanpa Engine's own folder (read only).
- `dome_and_spatial.py`: the cloud dome over a far ridge, and the 1/2 spatial layer.
- `corona_probe.py`: the corona's placement, facing, petals and occlusion, then its options: `distance`,
  `size`, `petals` (counted from the render) and `color`.
- `moving_camera_worlds.py [--worlds ringworld,shieldworld,earth]`: each world under a camera that walks
  and turns (the ringworld toward its band, the shieldworld under its moon, Earth along a ridge under the
  cloud dome). Frame N of that bake must equal a bake of a camera parked at frame N's pose; it does, to
  0.00/255, so no key or image sequence is a frame off for a moving camera.
- `ring_band_behind_local.py`: the ringworld over a 12 km desert with five mesas 1.5–4 km out. Every
  mesa draws in front of the band (the band's plate), the band shows above them, `bake_plates()`
  reproduces the bake's frame, and `use_fog` fogs a far mesa but not the band.

## Not yet ported

- **`makeSky` building the weather itself.** `make_sky` returns the sky alone; attach the weather with
  `eidoblend.weather.make_weather_system(scene, sky)` ([weather effects](weather-effects.md)).
- **Ringworld, Eanpa's v4 relief files.** The code is ported (`load_ring_relief`, `reliefDir`), but the
  files are not in this repo: `ring_relief_v4.bin.gz`, `ring_albedo_v4.png` and `ring_relief_v3.bin.gz` live
  in Eanpa Engine's `assets/ringworld/`. Without them the band displaces the repo's v1 height map and
  keeps the authored colour map, as `sky_worlds.js` does. Copying the three files into
  `eidoverse/assets/sky/celestial/` switches every ringworld to the v4 band with no code change.
  The rain curtains stay off in ring mode, as in the JS.
- **Ringworld, baked night AO.** WebGPU's `aoNode` darkens only indirect light; EEVEE has no such input,
  so the band keeps the cavity AO in its albedo and EEVEE's own horizon scan on the real relief.
- **Cirrus atlas.** Eanpa's ice-trail atlas (`cirrus_ice_trails.png`) is not in this repo, so cirrus
  draws the in-repo eidoverse mares'-tail plumes. Copying the atlas into `eidoverse/assets/sky/`
  switches to it with no code change.
- **Ringworld, the haze walls under the clouds.** WebGPU draws its cloud dome over the fog and rain walls;
  here the walls veil the clouds behind them (see the ringworld's walls above for why, and how much).
- **The band in the main scene's viewport.** The band renders through its plate, so the main scene's
  solid viewport has no band; look through the camera in Rendered mode after a bake, or at the
  `eido_ring_plate` scene.
- **WebGPU-only machinery, dropped**: density and light caches, compute passes, the cached panorama,
  cloudgraph and quality tiers, MRT and G-buffer flags, SSR and blur reflection hooks (EEVEE ray-traces),
  PMREM patches, the ring cloud field's per-frame GPU pass (baked once here), the browser host's lazy
  weather loading and `dispose()` (Blender data lives in the file), `CLOUDDBG`, the `EANPA_SPATIAL_DIAG`
  switch, the spatial pass's `compileAsync` (a pipeline warm-up), and `bakeEnv`'s `assign` / `ifAbsent`
  (the EEVEE world is both the visible sky and the environment, so the bake always builds it). Eanpa's
  `sky_geometry_layer` / `sky.depthLayers` are ported as the ring's plate (above); the shattered moon,
  34 km out, needs no private layer. The repo copy's `RING*` environment knobs are the `ring={...}`
  options above. `hdriMix` is dropped too.
