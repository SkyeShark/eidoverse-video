# Sky packages, celestial bodies, weather and weather audio

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

For a complete sky use the `sky_worlds.js` facade. It loads each world's assets,
sky, weather and celestial elements and owns their update order. This facade
is explicitly loaded by a scene; the lower-level `makeSkySystem` and
`makeWeatherSystem` functions are already injected by the renderer.

```js
// In setup(), after constructing the scene, camera and its sun/hemi lights:
eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
const sky = await makeSky({
  scene: _s, camera: _c, renderer: _r, sun, hemi,
  world: 'earth', hours: 15, clouds: 'cumulus', weather: 'clear'
});
await sky.bakeEnv();
// In renderFrame(t), before rendering: sky.update(t);
```

| World key | Package |
| --- | --- |
| `earth` | Earth sky and its moon |
| `ringworld` | Orbital/Halo sky with the authored terrain band |
| `shieldworld` | Far-future Earth under a red giant, hex shield and companion body |

Use the package's own assets and scale. There is no need to manually build the
ring, load another moon texture or create a separate light for its band.

## Direct the sky

- `setTime(hours)` sets time of day and stops an active day cycle.
- `dayCycle({startHour, seconds})` advances a full day over media time.
- `setClouds(type, shape?)` selects `clear`, `cumulus`, `stratus` or `cirrus`.
  `transitionClouds(type, seconds)` eases into a cloud preset (`seconds`
  defaults to 2.5).
- `setWeather(name, intensity)` selects `clear`, `fair`, `sunshower`,
  `overcast`, `rain`, `storm`, `cyclone` or `darkstorm`.
  `transitionTo(name, intensity, seconds)` changes weather over time
  (`intensity` defaults to 1, `seconds` to 45).
- `setColors({cloud, star, sky, rain, shield})` retints authored channels.
  Omitted channels retain their values; `shield` only applies to `shieldworld`.
- `wrapScene()` includes geometry added after initial construction in wetness
  and cloud-shadow effects. Materials can use `userData.noWet` when appropriate.
- `enableReflections(options)` enables moving sky reflections on metals,
  using the camera passed to `makeSky` (else `globalThis._c`). `options` is
  optional; `gain` (default 1) scales the reflection. The low-level
  `makeSkySystem` object takes the camera first:
  `enableReflections(camera, options)`.
  `await bakeEnv(options)` produces environment lighting; `{ifAbsent:true}`
  retains an environment already supplied by the scene.
- `update(t)` owns sky, weather, lightning/audio timing, celestial motion,
  lights and cache updates. Call once per frame; do not additionally update
  its internal sky and weather. Intentional extra lighting adjustments follow it.
- `sunDir` and `moonDir` are the true world-space unit directions of the sun
  and moon. After dusk the facade reuses its directional light for the moon,
  so the light's position is not the sun at night. Read `sky.sunDir` when
  something must follow the sun itself, such as a flare, a corona, or flowers
  turning to face it.

The clouds are rendered in the scene so solids occlude them. A flat HDRI
background is not equivalent. Test the horizon, reflected sky, atmosphere and
light changes at several points in a weather/day transition.

## Sun corona — `sun_corona.js`

A corona of light-petals around the true sun. It was made for DAISY's
finale, where the sun opens as a day's eye (the Old English *dæges ēage* that
became "daisy"). The corona is a camera-facing card parked far along the sun
direction and drawn additively over the sky. It tests depth but does not write
it, so nearer geometry and the horizon occlude it, and the bloom pass makes
its petals glow.

```js
const { makeSunCorona } = await import(new URL('sun_corona.js', EIDOVERSE_DIR).href);
const corona = makeSunCorona(THREE, { petals: 12, size: 400 });
scene.add(corona.mesh);
// renderFrame(t), after sky.update(t):
corona.update(camera, sky.sunDir, open, t);   // open 0..1: 0 = folded shut (hidden), 1 = full petals
```

The options are:
- `distance`: 1500 m by default. Keep `distance + size / 2` inside the
  camera's `far`.
- `size`: 400 m.
- `petals`: 12.
- `color`: linear RGB, a warm orange by default.

It returns `{ mesh, U, update }`. `U.gain` scales the brightness; `update`
drives `U.open` and a slow turn, like a flower tracking the light. The corona
hides itself when shut or when the sun is below the horizon. Against a bright
clear sky the bloom renders it almost white; a sunset sky keeps its colour.
Pass `sky.sunDir` rather than the light's position (see above).

## Produce rain and thunder audio

The facade records weather sound events by default; it cannot play sound in
the headless renderer. After the render, save its timeline from `cleanup()`:

```js
const timeline = sky.audioTimeline();
if (timeline) Deno.writeTextFileSync('work/<id>/weather.json', timeline);
```

```bash
python bake_weather_audio.py work/<id>/weather.json --out work/<id>/weather.wav --duration 60
python merge_av.py --video work/<id>/scene.mp4 --audio work/<id>/weather.wav --out work/<id>/final.mp4
```

Mix narration/music with that WAV first when needed; see [audio.md](audio.md).
With a separately built low-level weather system, explicitly load
`eidoverse/weather_audio.js`, call `makeWeatherAudio({weather, camera})`,
update it **after** `weather.update(t,camera)`, and save `toJSON()`.
Preserve the included audio files and their licenses with the timeline baker.

## Lower-level systems and optimization

These are the systems the package facade composes. Use them for an explicitly
custom scene or toolkit work after reviewing their contracts:

| System | Entry and lifecycle |
| --- | --- |
| `sky_system.js` | `await makeSkySystem({scene,textures,opts})`; `update(t,camera)`, `setTime`, `setClouds`, `setColors`, `applyToLights`, `bakeEnv`, `enableReflections`, `wrapCloudShadows` |
| `weather_system.js` | `await makeWeatherSystem({scene,sky,opts})`; `wrapScene`, `setWeather`, `transitionTo`, `update(t,camera)`, `sunDim`, `hemiDim` (hemisphere-light multiplier; `0.5 + sunDim×0.5` unless the preset authors its own), `setColors` (forwards to the sky only the channels named, so `setColors({ rain })` leaves cloud/sun/shield tints alone) |
| `redgiant.js` | `makeRedGiant({opts})`; attached by the shieldworld package; its star/shield tint and motion are driven by the shared sky |
| `ringworld.js` | `makeRingworld({glbBytes,textures,opts})`; group, band lighting and `update(t)` are owned by the ringworld package |
| `asteroid_moon.js` | `makeAsteroidMoon` loads the prepared mesh and maps; the package positions it on its authored orbit |
| `cloud_spatial.js` | `makeSpatialCloudPass(THREE,renderer,camera,{div,width,height})`; `attach(scene,sky)`, then `await render()` before the scene draw |
| `weather_audio.js` | `makeWeatherAudio({weather,camera})`; event timeline recorded after weather updates, then baked offline |

Low-level sky and weather require the scene to apply its lighting every frame:
sky first, then weather dimming. The facade does that automatically.
On `makeSkySystem`, `opts.azimuth` aims the sun's arc, `opts.moonAngularDeg`
sets the moon's apparent diameter, and `opts.ringCurve` curves its cloud deck.
`cloudColor` and `sunColor` are construction-time sky tints; `rainColor` is a
weather tint. For package scenes use `setColors` so the world routes the tints
to its celestial elements. A sky-element material's `userData.keepEnv`
preserves its environment lighting when reflection hooks are installed.
`makeSpatialCloudPass` is a current-frame spatial downsample, not temporal
reprojection; it belongs around the low-level sky domes. The world facade
keeps its internals private. Use its supported performance settings rather
than extracting and reparenting internal domes from a production scene.

The asteroid module also contains `bakeAsteroidMoon` for regenerating its
specific prepared assets. Normal videos load the bundled result; keep asset
regeneration work separate from playback. Check [development.md](development.md)
before changing a world or its assets.

## Custom celestial clusters

After loading the facade, `SKY_WORLDS` lists its available package keys.
For toolkit work or a custom celestial scene, explicitly load
`asteroid_moon.js` before calling `makeShatteredMoon`. The normal shieldworld
package already owns its cluster; do not create a duplicate there.

```js
eval(Deno.readTextFileSync('eidoverse/asteroid_moon.js'));
const cluster = await makeShatteredMoon({ glbBytes: ASSETS.fragments, spread: 1.75 });
scene.add(cluster.group);
cluster.uniforms.sunDir.value.copy(sunDirection).normalize();
// In renderFrame(t), before rendering:
cluster.update(t);
```

`fragments` must be a GLB with separate fragment meshes and usable bounds,
not a single fused sphere. Returns `group`, `pieces`, `dust`, lighting
`uniforms`, `update(t)` and `disposeTextures()`. Motion is a deterministic
bounded orbital/tumble effect, not an n-body physics solver. It uses the
native `THREE`/TSL and `GLTFLoader` globals. Match the sun
direction/color and place/scale the group for the scene. When retiring it,
dispose owned meshes/materials and call `disposeTextures()` for its retained
source maps. Do not dispose resources shared with another live object.
