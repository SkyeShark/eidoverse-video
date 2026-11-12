# SDF explosions, fire and smoke

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [SDF surfaces and volumes](sdf-volumes.md)

The engine's volumetric `EXAMPLES` (`explosionRing`, `flame`, `smoke`,
`gyroidFireball`, `bonfire`, `candleFlame`, `fire`, `nuclearBlast`) and its
screen-space mushroom cloud (`effects_tsl/nuclear_explosion.js`) are real
volumes in Blender. Each example's `sample()` is the engine's TSL written in
GLSL node for node and evaluated into OpenVDB grids, one file per frame, by
[`create_sdf_volume`](sdf-volumes.md#volumes--create_sdf_volume). EEVEE then
draws them with depth, fog, other volumes and any camera position, inside the
cloud included. Keyed lamps carry their glow onto the scene, because EEVEE's
volume emission lights no surface.

```python
import os, sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.sdf import EXAMPLES
from eidoblend.sdf.examples_volumes import light_from_emission, light_from_surface, fit_volume_range, build_still

fire = EXAMPLES['bonfire'].make(location=(0, 0, 0), cells=200, build=False,
                                cache_dir=os.path.join(out_dir, 'sdf_cache'))
fire.bake(1, 240)                       # one .vdb per frame; the saved .blend plays and renders any frame
light_from_emission(fire)               # keyed point lights: the fire's light on the floor, walls and faces
fit_volume_range(scene, scene.camera, [fire])   # EEVEE's froxel slices tight round the fire
```

`make(**opts)` is the engine's `EXAMPLES.x.make(opts)`. The engine's knobs
become this volume's uniforms (`speed=2.0` sets `uSpeed`). `look='lit'`
splits fire and smoke (see below). Everything else is a `create_sdf_volume`
option: `cells` / `voxel` / `quality` for the grid, `location`, `rotation`,
`scale`, `cache_dir`, `name`, `time` (the still `build()` makes), and
`build=False` to bake instead.

For stills at several times, use `build_still(vol, t)`. It writes one file
per time. Blender keeps the grids it has loaded from a path, so a second
`build()` of one volume, which rewrites `<stem>.vdb`, still renders the first
one's grids. That was measured: four stills at four times rendered as one.

## The examples

| name (engine name) | what | knobs (`make(...)`) | box (three's y up) |
|---|---|---|---|
| `explosion_ring` (`explosionRing`) | expanding smoke-ring detonation: a torus easing outward, the smoke rolling round the tube, white-hot to fire to grey smoke on a 4.5 s loop | `speed` | ±1.2 × [−0.25, 1] |
| `flame` (`flame`) | torch flame: the 2D simplex-fbm flame revolved round y | `strength` (1..5, turbulence), `speed` | ±0.65 × [0, 1.45] |
| `smoke` (`smoke`) | rising, widening grey-blue plume | `speed`, `density` | ±0.95 × [0, 2.6] |
| `gyroid_fireball` (`gyroidFireball`) | cellular fireball: ignition, fireball, smoke puff, gone, on a 3 s loop | `speed`, `seed`, `density` | ±0.75 |
| `bonfire` (`bonfire`) | noise-shaped flames in a swaying teardrop envelope, broken smoke on a wind-bent axis | `speed`, `density` | ±0.9 × [0, 2.8] |
| `candle_flame` (`candleFlame`) | a real-size candle flame (0.16 m): blue hollow base, warm teardrop, a thin smoke thread | `speed`, `density` | ±0.16 × [0, 0.62] |
| `fire` (`fire`) | a roaring blaze: licking tongues over a tapered footprint, a hollow torn smoke column to 5 m | `speed`, `density` | ±1.5 × [0, 5.1] |
| `nuclear_blast` (`nuclearBlast`) | the mushroom cloud placed: cap, stem, trail, base surge and pad, rolling noise, cooling heat, late dispersal on a 20 s loop | `speed`, `heat`, `density`, `size` (1.4: 19 m tall) | ±7.45 × [0, 13.65] × size |

`explosion` (`explosion`), the pyroclastic fireball, is a surface SDF: it
is in [the solids' table](sdf-volumes.md#the-examples) and builds with
`create_sdf_object`.

Each volume keeps its own uniforms. The engine's `E._u` were shared, so
`make({speed: 2})` sped up every instance of that example. Here two fires
from one example burn at their own speeds. `vol.sdf_live_uniforms` is the
engine's `vol.userData.sdfLiveUniforms`. Read or set a knob there
(`vol.sdf_live_uniforms['density'] = 0.5`), then build or bake again. A
baked volume keeps the grids it baked. To change a knob over a shot, key it
per frame:

```python
smoke = EXAMPLES['smoke'].make(cells=180, build=False)
smoke.bake(1, 120, controls=lambda frame, t: {'uDensity': min(1.0, t / 2.0)})   # thickens over 2 s
```

The engine's animation ran on three's global `time` through memoised TSL
nodes (`_anim`, `_animMemo`, cleared in `make()` so no two materials shared
node objects). In GLSL the animation is a plain function of `uTime`
computed in `sample()`, so there is nothing to memoise or clear. `bake(fs,
fe)` samples `uTime` = the frame's time, and `time_scale` / `time_offset`
move it (`time_offset=5.0` starts the blast 5 s in).

## What changes from the engine

**The step counts.** The engine stopped each ray after `steps` samples
(`explosionRing` 320, `nuclearBlast` 300). The grids hold the whole box, so
a long ray through the medium shows its far part here, where the engine cut
it off. A spec keeps `steps` as the engine set it; the grids do not use it.

**`post(sum)`.** Only `explosion_ring` has one. It is a contrast curve on
the composited pixel: `smoothstep(0, 0.3)` on the colour and `smoothstep(0,
0.95)` on the alpha. A volume has no composited pixel, so the curve is folded
into the medium (`RING_POST_FOLD`). In the grids, each sample's density is
raised to the power 1.75 (`uFoldGamma`): thin wisps fade and the core
holds. Then `material_settings` scale the density × 2.1 and the emission ×
3.0. These numbers are fitted to the engine's own march with `post`, over
39 k covered pixels at five times of the loop (`test_volume_examples.py --
fit=1`, through the tests' `engine_march.py`). The power takes the fit's
error from 0.143 (scales alone) to 0.122. `uFoldGamma` 1 is the engine's own
`sample()`.

**The grid box.** The engine's bounds were raymarch boxes. They were loose,
because they cost only march steps. A grid spends its voxels over its whole
box, so `make()` uses a box measured round each example's medium over its
loop (`GRID_BOUNDS`). The explosion ring's medium never leaves ±0.72 ×
[−0.23, 0.26] of its ±1.2 × [−0.25, 1] box, so its voxels are 1.7 × finer
in each axis. (Seen from above at a grazing angle, the engine's march of
the ring in its own box showed a dark hole through the middle that the
volume does not. The same march started from the tight box fills it as the
volume does. The hole was the march's two-speed stride, 1 cm steps outside
the tube, stepping over the thin top of the near tube; where the box put the
march's start decided it.) `test_volume_examples.py` checks each box at 16
times: no voxel outside it
holds more than 0.1 % of the peak density. `make(fit=False)` keeps the
engine's box. `bonfire` and `fire` lose only their empty tops (their smoke
ends at 2.1 and 4.9 by construction). `nuclear_blast` keeps its box: its
surge ring runs past the box's sides, and the box cuts it flat, as the
engine's did.

**The smoke's light.** The engine's colours were the light each sample
added, already lit. They convert exactly to emission. The smoke then glows
its hand-lit grey whatever the scene's light, as it did in the engine. For
the four examples that carry both fire and smoke, `make(look='lit')` keeps
the two media apart. The fire emits its colour. The smoke becomes a
scattering medium of the same density, so it takes the moon, the sun and the
fire's own lamps, and it casts volume shadows. Its albedo is the engine's
smoke colour, lifted so that each example's brightest smoke scatters about
0.75 of the light, keeping the engine's gradient: × 2 for the bonfire and
× 2.5 for the fire and the candle (the engine's greys, taken as albedos as
they are, read as soot against a night sky). The blast's smoke band (0.012 to
0.18) is darker still, so its cooled cloud is dust in the band's hue, with an
albedo of 0.3 to 0.6. The one-medium examples (`smoke`,
`explosion_ring`, `flame`, `gyroid_fireball`) take `sample_as='albedo'` for
the same effect.

## Light on the scene

EEVEE draws volume emission but does not let it light a surface: in EEVEE
the light a fire casts on the scene is a light. `light_from_emission(vol)`
gives a volume its lamps. For every baked frame it
reads the frame's density and emission grids back from the `.vdb`. It finds
the light that escapes the medium: each voxel's emission, times its mean
transmittance to the box along the six axes, times its volume, times 4π.
That is the same watts as a Blender light. It keys point lights with that
power and colour at the escaping light's centroid, with a radius of 0.6 × its
spread, parented to the volume object so they follow it. `count=3` splits
the light over three k-means lobes, which suits a spread-out medium like the
cap and the ring of the blast. Each light's cutoff distance is set where its
largest power fades to 10⁻⁴ W/m², so the scene's light threshold does not
cull the glow on distant walls. One point light cannot carry a flame's
angular shape; round an asymmetric fire, more lobes (`count=`) follow it
more closely. `test_volume_lights.py` renders a bonfire and a candle on a
grey floor at night with their lamps.

```python
rig = light_from_emission(fire, count=1, energy_scale=1.0, radius_scale=0.6, shadows=True)
rig.lights               # the point-light objects (keyed: energy, colour, location, radius)
rig.frames[24]           # [{'power': (r, g, b) W, 'centre', 'radius', 'share'}] per light
rig.remove()
```

The pyroclastic `explosion` is a surface. An emissive mesh lights the scene
in EEVEE only through Fast GI's screen-space pass and the probes, so a
glowing solid wants lamps too: `light_from_surface(sdf)` does for an
emissive SDF solid what
`light_from_emission` does for a volume. Per frame it reads the evaluated
mesh's faces and each face's emitted radiance: a baked frame carries
`sdf_emission` per vertex, and a still is evaluated with the SDF's own
`surface()`. The power is π × radiance × area, a Lambertian emitter, times
the material's emission strength. The fireball's skin is deeply folded, and
much of what a fold emits lands on the fireball itself. So each face's power
is weighted by its escape fraction: 16 cosine-weighted rays per face,
sphere-traced through the SDF on 4096 faces drawn by power. The lights sit
at the emitting skin's centroid, inside the solid, so shadow linking takes
the solid out of their shadows; otherwise its own surface would block them.
The lights carry no specular, because EEVEE's ray tracing already reflects
the glowing mesh.
`time_scale` / `time_offset` are the ones the solid's `bake()` used: the
escape is traced through the SDF at each frame's time. Baked over four
frames of its growth, the fireball's keyed lamps rise from 38 to 66 W, and
about two thirds of its skin's light escapes its folds.

```python
boom = EXAMPLES['explosion'].make(location=(0, 0, 1.5), build=False)
boom.bake(1, 120)
light_from_surface(boom, count=1)
```

**Reflections.** EEVEE draws no volume in its ray-traced reflections or its
light probes: a chrome ball beside the fire shows the lamp's round
highlight. The mushroom cloud reaches metal through light probes and
stand-ins (`reflections=True`, below).

## EEVEE's froxels

EEVEE resolves volumes on a camera-aligned grid of froxels: `tile_size`
pixels across and `samples` slices between the range's start and end. A
volume outside the range does not render at all, and the range is the
scene's: it clips every volume, not only the ones you fit it to.
`fit_volume_range(scene, camera, volumes, frames)` fits the range round the
volumes' boxes, seen from the camera over the frames, and sets the tile
size, the slice count, the slice distribution and volumetric shadows.

- It also covers every other volume that renders (`others=True`): Volume
  objects and meshes with a volume material, such as a fog box, another
  fire or a second blast. Fitted round a bonfire alone, a fog box filling
  the stage vanished beyond the fire. That was measured in
  `test_volume_scene_integration.py` (fog luminance 0.30 → 0.23, the haze
  gone). With `others=False` the range stays tight round the given
  volumes.
- A world volume fills the view, so the range keeps the camera's whole clip
  range, or the custom range already set if that is wider.
- `camera=None` follows the camera Blender renders each frame: the
  scene camera, switched by timeline markers. The range is the union over
  every cut. Fitted to the near camera only, a far cut showed no fire at all.
  A list of cameras fits all of them.

Blender cannot key the range, so it is one union over all the frames. A
wide range spreads the slices thinner; `samples` and the distribution
(0.8: more slices near the camera) buy them back.

The grid is the other resolution. The engine sampled its noise per pixel
along each ray. Here `cells` voxels span the box's longest side, and detail
finer than about two voxels is gone: the ring's 350-per-metre octave and the
candle's 90-per-metre smoke octave are grain the grid cannot hold. Beside
the engine's own march of the same `sample()`, the renders show the same
shapes, colours and smoke, softer.

What a frame costs, at the probes' resolutions (`test_volume_examples.py --
timing=1`, sampling on the GPU and writing the `.vdb`):

| example | cells | voxels | voxel | s / frame | MB / frame |
|---|---|---|---|---|---|
| `explosion_ring` | 256 | 5.8 M | 5.6 mm | 1.33 | 8.0 |
| `flame` | 200 | 2.6 M | 6.0 mm | 0.49 | 2.4 |
| `smoke` | 180 | 1.9 M | 14.4 mm | 0.36 | 6.8 |
| `gyroid_fireball` | 192 | 7.1 M | 7.3 mm | 1.23 | 4.0 |
| `bonfire` | 200 | 5.4 M | 11.0 mm | 0.95 | 5.5 |
| `candle_flame` | 256 | 1.9 M | 2.3 mm | 0.30 | 0.8 |
| `fire` | 220 | 4.0 M | 22.5 mm | 0.76 | 6.4 |
| `nuclear_blast` | 220 | 9.8 M | 95 mm | 1.78 | 3.0 |

## The mushroom cloud — `nuclear_explosion`

`effects_tsl/nuclear_explosion.js` was a world-layer post effect,
`NuclearExplosionFX.applyTo({scene, camera, opts})`. It marched every
pixel's view ray through the cloud's SDF and composited the cloud over the
frame, clamped to the scene's depth. A second pass marched the reflected
rays of metal surfaces, and a third blurred those by roughness. The engine
later rebuilt it as `EXAMPLES.nuclearBlast` for placing. In Blender the
effect itself is a cloud in the scene:

```python
from eidoblend.sdf import nuclear_explosion as NX

nuke = NX.apply_to(scene, camera, {'origin': [0, 0, -120], 'scale': 3.0, 'timeOffset': 2.0},
                   cache_dir=os.path.join(out_dir, 'nuke_cache'))
nuke.bake(1, 480)                  # both volumes, one .vdb each per frame, the glow lamps keyed, froxels fitted
nuke.key_opacity(1, 0.0); nuke.key_opacity(12, 1.0)   # the effect's opacity, keyed: media and lamps fade together
nuke.update(7.5)                   # or one still at t = 7.5 s (the effect's update(t))
```

Two Volume objects hold it: the wide, thin base surge (r ≤ 20.7, y ≤ 3.6
in the original's units) and the mushroom above it (r ≤ 5.5, y 3.6 to
13.3). They partition the space, so no voxel is spent on the air round the
cap and nothing is counted twice. The anatomy, lifecycle and palette are
the original's, unchanged:

- the cap, stem, trail, base-surge torus and ground pad, fused by
  `sminCubic`;
- the original's `If`-gated rolls of the noise round the cap's and the
  surge's vortex rings;
- the 4-octave cascade times the SDF-depth falloff, and the late dispersal
  that dissolves wisps first;
- heat from the distance to the core, cooling over the loop, and the
  near-black smoke band under the fire ramp;
- density × 0.22 per 0.08-unit stride, in world units, as its marcher had
  it.

The base surge is **not** capped. `nuclear_blast` caps it at 6.6 × size to
fit its box; the effect runs it to 20 × scale, the 2 km ring.

| option (engine spelling) | here |
|---|---|
| `origin` | ground zero, three's axes → the volumes' location (x, −z, y) |
| `scale` | the size (1 unit ≈ 100 m: scale 1 is a ~900 m cap); it sets the grids' boxes, so pass it to `apply_to` |
| `timeOffset`, `loopSeconds` | the shader's phase and period (uniforms; `nuke.uniforms['time_offset'] = 3`, then bake) |
| `opacity` | one Value node in a shader group that both volumes' materials use, multiplying density and emission; each lamp's energy is a driver, its keyed power (`glow_power`) × that socket. `key_opacity(frame, v)` keys it (`nuke.opacity_socket` is the socket), and a key set on the socket any other way fades the lamps too. Exact for thin smoke; the dense core fades later than the screen mix did |
| `volSteps` | accepted: the grids hold the whole cloud, so no step count limits it |
| `surfSteps`, `maxT`, `width`, `height` | the screen march's budgets and size: accepted and reported. The cloud is drawn at any distance |
| `reflectSteps` | the reflection march's budget: accepted and reported. The reflections are the light probes' (`reflections`, below) |
| `disableForPerfTest` | the volumes are built hidden and nothing is baked |
| (extra) `quality` | `'fast'` / `'balanced'` / `'high'`: voxels of 0.16 / 0.08 / 0.055 original units × scale |
| (extra) `lights`, `light_scale` | glow lamps per frame (3: the surge, the stem and the cap), and their multiplier |
| (extra) `bake` | `(fs, fe)` or `'scene'`: bake now |
| (extra) `reflections`, `reflection_density` | the light probes' stand-ins of the cloud (below), and the medium's density per metre where their surface sits (0.75) |

`test_nuclear_explosion.py` renders six stills through the loop over a town
of boxes, beside the effect's own march: the flash and the young ring, the
orange surge round a white cap, the wide grey ring, the cooling orange cap,
the dark dispersing cloud. EEVEE follows the march at every stage. The glow
lamps light the ground and the buildings' faces, and the buildings occlude
the ring.

`nuke.uniforms` is the effect's returned `uniforms`: `time`, `origin`,
`scale`, `time_offset`, `loop_seconds` and `opacity`, read and set by name.
`nuke.remove()` takes it all out. Several
blasts need no hook chaining: each is its own pair of volumes, and they mix
with each other, fog and the sky physically. Each bake fits the froxel range
round its own cloud and every other volume in the scene, so a second blast
or the fog stays in it. The camera is the effect's, or every
timeline-marker cut when the scene has them.

The post registry (`look/post/custom_effects.py`) lists `nuclear_explosion`.
`NX.native_build(scene, opts)` and `NX.native_undo(scene)` are its native
build and undo: the cloud baked over the scene's range from `scene.camera`,
and everything it made removed again. Its uniform is the opacity socket.
The lamps' drivers read that socket, so `fx.key('nuclear_explosion',
'opacity', frame, v)` fades the cloud and its glow together.
`test_volume_scene_integration.py` registers the hook as written and checks
this: lamp energy 0 at opacity 0, rising with the key. `nuke.sync_lights()`
remains, and only makes sure every lamp has its driver.

### Chrome and wet metal reflect the cloud

The engine marched the cloud along the reflected rays of metal surfaces.
EEVEE's ray tracing and its light probes draw no volume, so here the
reflection goes through a sphere light probe round each piece of metal,
which captures a stand-in of the cloud that only light probes see:

```python
nuke = NX.apply_to(scene, camera, {'origin': [0, 0, -120], 'scale': 3.0, 'reflections': True},
                   cache_dir=os.path.join(out_dir, 'nuke_cache'))
nuke.reflect_in([car, sign, puddle_rim])     # a sphere probe round each
nuke.bake(1, 480)
```

- `reflections=True` gives each volume a stand-in: Geometry Nodes take the
  Volume object's own density grid to a mesh (Grid to Mesh at
  `reflection_density`, 0.75 per metre), and each vertex emits the
  medium's source function, emission ÷ density, sampled a voxel inside.
  That is the radiance an optically thick medium shows: the cap's cream and
  orange, the surge's grey. The stand-ins read the Volume objects live, so
  they follow every baked frame, and their emission takes the effect's
  `opacity` with the media. Camera and shadow rays are off and volume probes
  leave them out, so only the reflection probes see them.
- `reflect_in(objects)` puts a sphere probe round each object, its
  influence wide enough to take the object at full weight. Each object
  leaves the sphere probes (Object > Visibility > Light Probes > Sphere;
  `remove()` gives it back), so it does not block its own probe's view from
  inside it, and the probe's near clip stays at 1 cm. A probe clips with a
  plane per cube face, so a clip at the object's reach would cut away the
  ground it stands on. Its parallax is a sphere at the cloud's distance,
  where the probe's picture of the cloud belongs. Left at its default, a
  probe's parallax is its own influence, and a cloud 48 m off reflects twice
  too large. `reflect_in(objs, parallax=metres)` sets it by hand.

The probe filters its picture by the metal's roughness, as the engine's
blur did. `test_volume_reflections.py` measures a chrome ball (roughness
0.05) with the cloud behind the camera, against EEVEE's own render of the
cloud from the ball's centre looked up along each pixel's reflected ray.
Without the option the ball shows none of the cloud (98 % error). With it
the cap, stem and surge are in place at the right size and colour, softer
than a perfect mirror: 25 % error over the pixels that should show the
cloud, most of it at the softened edges. The probe's resolution is not what
softens it: at 2048 (`scene.eevee.gi_cubemap_resolution`) the error is 24 %.
Its still `reflections_look.png` puts that ball and a brushed one
(roughness 0.3) on dark ground at dusk: the chrome shows a small, bright
mushroom on its horizon, the brushed metal a soft warm glow.

## Probes

`blender/tests/sdf_volumes/`. Each script's docstring gives its command.

- `test_volume_examples.py`: the eight examples registered as the engine had
  them. Finite, occupied grids that change over each loop, and each grid box
  holds all the medium. The knobs reach only their own volume: `speed=2` at t
  gives exactly the default's grids at 2t, `density=0.5` thins the medium,
  and seed, strength and heat change it. `look='lit'` gives the same medium,
  split. With `fit=1` it refits the explosion ring's post fold, and with
  `timing=1` it times the bakes.
- `test_volume_lights.py`: the keyed lamps of a bonfire and a candle on a
  floor at night, the surface fireball's light with and without
  `light_from_surface`, and the fireball baked with its lamps keyed per
  frame.
- `test_volume_sequences.py`: every example's life over its loop (EEVEE
  above the engine's march, both over the same empty stage) and six
  consecutive frames with the lamps keyed. With `lit=1` it adds the
  `look='lit'` comparison.
- `test_nuclear_explosion.py`: the effect's options, the uncapped ring, its
  life beside its own march over a town, its motion, the keyed opacity
  (lamps included, keyed through the socket as well) and the registry
  hooks.
- `test_volume_scene_integration.py`: the volumes in a real scene.
  - A fog box and a world volume kept in the fitted froxel range.
  - Timeline-marker camera cuts.
  - The camera inside the smoke.
  - A turned and scaled fire's lamps, and a placed, scaled blast.
  - The roaring `fire`'s lamps.
  - The post-registry hook registered as written: build, keys and undo.
  - `probe_reflect`: whether a sphere probe carries a volume into
    reflections. It does not.
- `test_volume_reopen.py`: a baked bonfire and blast with keyed lamps and
  keyed opacity, saved, then rendered by a fresh Blender that only opens
  the file. Its frames match the session's exactly, and it plays.
- `test_volume_reflections.py`: the mushroom cloud in a chrome ball through
  `reflections=True` and `reflect_in`, against the cloud seen from the ball,
  with the probe at 512 and at 2048, and the two balls at dusk
  (`--no-render`: the stand-ins, the probe's settings and `remove()`).

## Not yet ported

- A volume's light on the scene is its keyed lamps, one to four point
  lights: the light's angular shape (a flame leaning one way) and its
  flicker within a frame are not carried.
- EEVEE's ray-traced reflections and light probes draw no volume
  (`test_volume_scene_integration.py -- cases=probe_reflect`). The mushroom
  cloud reaches metal through its probe stand-ins (above), an opaque
  surface emitting the medium's source function: thin smoke under
  `reflection_density` is not in the reflection, and wisps reflect with a
  hard edge, softened only by the metal's roughness. The other volume
  examples (fires, smoke, explosions) have no stand-ins: metal shows only
  their lamps' highlight.
- Detail finer than two voxels: the grid holds what its `cells` resolve. The
  engine sampled per pixel.
- `post(sum)` is folded per sample (a power on the density, then scales),
  not as the per-pixel contrast curve. The ring's late grey smoke reads a
  little darker than the engine's.
- `nuclear_explosion`'s `opacity` scales the media's density and emission.
  It does not mix the finished frame as the screen pass did, so thin smoke
  fades exactly but the dense core fades later.
- `look='lit'` is this edition's addition: the engine's look is the default.
- A volume or solid moved or rescaled after its lamps were keyed keeps the
  lamps' power. Their position follows the parent, but the power was
  computed at the scale it had then. Key the lamps again after rescaling.
