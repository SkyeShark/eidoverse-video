# Shallow water, pours and 2D fluids

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Choose the water representation by its motion and spatial needs.
`eidoblend.fx.swe` models a shallow-water heightfield over `bed_fn(x, y) → z`,
with coupled pours, droplets, foam and sphere interactions. It is the
Blender edition of `fluid_swe.js`. Use [3D free-surface water](free-surface-water.md)
when the surface must fold over or flow around volumetric moving colliders.
A flat reflective water surface suits distant water without those
interactions, and the 2D dye solver is for panels and fields of swirling
colour (both are in "Not yet ported" below).

The solver is the engine's, kernel for kernel, in numpy:

- flux-form shallow water with per-cell pipe outflows and proportional
  rescale, so h ≥ 0 and mass is exact;
- semi-Lagrangian velocity with surface gravity, Bingham yield, Manning bed
  friction and drag;
- disc emitters and sphere coupling for bodies;
- foam advected and fed by churn, crests, wakes and landings;
- rain with squall bands, and hydraulic erosion with talus slumping;
- the spray exchange: field promotion into droplets that carry volume, and
  pour droplets that return volume, momentum and foam where they land.

It runs in three.js's frame internally, on the same (NZ, NX) layout as the
engine's textures. Fields are rounded to half float after every kernel, as
the engine's rgba16float storage was (`precision='half'`, the default). The
presets, rain rates and thresholds were all tuned on that storage. Pass
`precision='single'` to keep float32.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.fx.swe import create_water_swe

swe = create_water_swe(
    bed_fn=lambda x, y: ground_z(x, y),       # the terrain IS the bed (Blender world, vectorised if it can be)
    world_size=(16, 16), grid_size=(256, 256), domain_center=(0, 0, 0),
    spray_max=6144,                           # whitewater budget (0 = off)
    cache_dir='//swe_cache')

def controls(frame, t, swe):                  # the engine's per-frame calls, Blender coordinates
    swe.set_pours([dict(x=4.7, y=1.0, z=0.53, vx=-0.35, vy=-1.7, vz=-0.4, rate=0.5)])
    swe.set_spheres([dict(x=bx, y=by, z=bz, r=0.42, vx=vx, vy=vy, vz=vz)])   # vz matters: entry splash

swe.bake(1, 1350, controls=controls, track_spheres=[(wader, 0.42)])
```

`bake()` runs the engine's `step(dt)` once per frame and writes per-frame
OpenEXR data images. Geometry Nodes reads them back by frame number:

- `water`: surface height, depth, foam and foam noise;
- `bed`: erosion;
- `spray`: one texel per droplet slot;
- `stream`: the pour tubes' vertices.

The `.blend` then plays the water with no Python at render time.
`track_spheres` feeds animated objects as spheres, with their velocities,
every frame.

The returned object holds:

- `surface_object`, the displaced water surface;
- `terrain_object`, the eroding ground patch (erosion only);
- `spray_object`, the droplets: points from the cache, each a small sphere
  stretched along its velocity;
- `stream_object`, the pour tubes;
- `material`, the surface material;
- `solver`, the numpy state (`solver.volume()` for conservation checks);
- the setters `set_pours`, `set_emitters`, `set_spheres` and `set_rain`.

The probe `blender/tests/fx/test_swe_basin.py` is the engine's `swe_demo`: a
bowl filling from three rim spouts, then a chrome wader breaching. It bakes
288 frames at 256² with 6144 spray slots in about 40 s on the CPU.

**Liquid presets**: exported as `LIQUID_PRESETS`. One word selects a whole
material behaviour (`preset='water' | 'gel' | 'goo' | 'lava' | 'mud'`), and
any option still overrides it. Presets drive both the sim and the look:

- `yield_slope`: Bingham yield, so gel holds its mounds instead of levelling;
- `wave_scale`: a gloopy, slow response;
- `spec_pow`: highlight tightness, which sets the surface roughness;
- `spray_stretch`: needles or blobs;
- `stream_aeration`: water whitens as it falls; honey and gel stay glassy
  filaments;
- `droplet_visibility`;
- `foam_gain`: gel barely froths.

```python
gel = create_water_swe(bed_fn, preset='gel', deep_color='#6e2603', shallow_color='#ff7d1f')
```

**Pour styles**: `set_pours([dict(..., style='seep', seep_width=0.8)])`.
`'jet'` (the default) renders the ballistic stream tube and the droplet
breakup. `'seep'` is a slow dribbling curtain at the mouth, for a rock
spring or a weeping wall; a seep must not render a jet parabola. The mass
ledger is identical. Put pour mouths on the visible geometry's lip.

The pour throttle is the engine's (`fluid_swe.js` cycleEst 1.05 s, a
−0.22 s cooldown, a −0.03 s re-roll). It assumes a droplet cycles in
1.05 s, but droplets are born in the arc's breakup band and recycle much
faster, so a pour delivers more than its `rate`:

- a jet delivers 2–3×: three 0.5 m³/s pours on the demo filled at about
  3.4 m³/s;
- a seep at ground level, whose droplets land almost at once, delivers
  about 15×: a 0.05 m³/s seep in the erosion probe added 0.75 m³ in its
  first second, and the field held 15.7 m³ after 30 s against 2.27 m³ of
  nominal rain plus pour.

The films were tuned on that behaviour (their surge was a seep), so it is
kept. Size a pour by what it delivers, not by its label: bake a few
seconds, read `swe.solver.volume()` and scale `rate`.

**Hydraulic erosion and rain: the bed can be alive.** Pass `erosion={}` and
the terrain under the water becomes dynamic. Fast flow picks the bed up as
suspended sediment, so the water visibly muddies. It carries it downstream
and lays it down where the current slackens. Rills capture into a braided
wash, the wash incises, cut banks cave to the angle of repose, and a silt
fan builds at the outlet.

Pair erosion with `rain_rate`: distributed rainfall over the whole domain,
in m/s of depth. 4.6e-5 is a violent cloudburst, and `rain_patchiness`
animates squall bands. Rain is the natural source for wash formation; a
lone jet pour reads as a garden hose. `swe.set_rain(v)` inside `controls`
ramps the storm. Build with `rain_rate > 0` so the rain term exists.

Under half-float storage, rain increments smaller than half an fp16 step
vanish on wet cells, as they did in the engine. A 17 m valley gathered
about 60% of its nominal rain in the first 20 s.

```python
swe = create_water_swe(
    bed_fn, world_size=(17, 17), grid_size=(256, 256), rain_rate=4.6e-5, rain_patchiness=0.6,
    erosion=dict(capacity=0.30, erode=0.32, deposit=0.42, bank=1.2,
                 talus_slope=0.5,         # wet-sand repose ~29 degrees: banks slump WIDE
                 talus_rate=3.0, max_delta=0.35,
                 terrain_maps=dict(albedo='soil_diff.jpg', rough='soil_rough.jpg', normal='soil_nor.jpg'),
                 terrain_tex_period=120 / 26))   # metres per tile, WORLD-locked like the static ground
```

The probe `blender/tests/fx/test_swe_erosion.py` is the films' own setup:
*The Shape the Water Left*'s ground (`shape_water.js` groundY), its erosion
parameters and soil maps, rain set per frame and the seep surge. It bakes
720 frames at 256² in about 3 minutes on the CPU and renders the dry patch
at frame 1, the braided wash at frames 240 and 720, and a 2 m crop of the
domain rim (`swe_erosion_{low,top,rim}_f*.png`).

`terrain_object` is the eroding patch, displaced from the live bed. Lay it
over the static terrain built from the same `bed_fn`. The static mesh must
drop well away (about 1.5 m, feathered) under the patch interior and meet
it flush only at the feathered rim. Sunk only a few centimetres, it fills
every deeper cut from inside: cuts vanish, deposits still rise, and the
piece reads as ground growing around the water. Pass all three maps.
Albedo alone leaves the patch glass-smooth beside a normal-mapped world, and
the domain prints as a square even when the heights meet flush.

Scene craft for a wash that reads: shape the domain as a broad valley.
Damp the dune noise inside it and add a gentle cross-fall; a raw dune field
breaks rain into scattered pools and no channel ever organises. Widening
versus slot-cutting is the tuning axis. `bank` plus a low `talus_slope` and
a small `max_delta` give flood-broad washes. Raise `max_delta` and
`talus_slope` and drop `bank` for a young slot gully.

Key options:

- `init_level` pre-fills to a waterline. A scene whose point is the fill
  must start dry.
- `foam_decay` tightens or loosens churn patches.
- The palette is `deep_color`, `shallow_color` and `absorption`, plus
  `foam_color`.
- `emissive_color`, `emissive_strength` and `emissive_falloff` make water
  glow with depth, as the demo's palette and lava do.

Give runup a tall containment. Water that slops over a low rim pools on the
outer apron. A wading character needs a local sphere or a few spheres
(`track_spheres`); the whole body's bounds read as walking on the water.

What it cannot do: overhangs, curling breakers, submerged interiors. A
heightfield stores one surface height per column.

**The look in EEVEE.** The surface is one Principled water BSDF:

- IOR 1.333, ray-traced refraction and reflections of the scene's own world;
- clear water tinted by depth, the engine's depth-tinted body
  (`1 − exp(−h · absorption)` × `surface_opacity` of it) and the engine's
  eroded foam coverage through its flow-advected foam noise, in the
  engine's proportions;
- suspended-sediment muddying;
- the shore fade as alpha;
- the engine's emissive mix.

The engine's `envTex`, `skyColor` and hand-tuned specular are not needed:
reflections come from the world. Set `scene.eevee.use_raytracing = True`.
The surface material uses dithered transparency with ray-traced refraction.

Clear water refracts, and body or foam is diffuse. EEVEE's G-buffer keeps
one of refraction or diffuse per pixel. Given both at once (a transmission
weight between 0 and 1, or BSDFs mixed by Mix Shader), it picks one per
pixel with a pattern that stays the same every sample, and the water shows
a sandpaper grain that 64 samples do not clear. So the material makes the
choice itself. A white-noise hash of the shaded position, new at every
sample because EEVEE jitters each sample, picks clear water with
probability (1 − body)(1 − foam). The Principled renders that pick with
transmission exactly 0 or 1. The samples average to the engine's blend, the
way hashed transparency does: a faint grain at 16 samples, smooth at 64
(`swe_basin_natural_s64_f0072.png`). Film renders want 64 or more.

The surface casts no shadow, like the engine's. EEVEE would treat the
refractive sheet as opaque and shade the bed under the water.

Dry columns (under 1 mm) are drawn `dry_sink` under the bed: 1 cm or a
quarter cell, whichever is more. The engine drew them on the bed, where
they were invisible, because its surface was alpha-blended with no depth
write. In EEVEE, a refractive fragment lying exactly on an opaque surface
renders black even at alpha 0. Black z-fight speckle covered a dry erosion
patch, and a black seam ran along the domain rim, where the rain gate keeps
h at 0. Raise `dry_sink` (an argument of `create_water_swe`) for shots from
far away, where depth precision is coarser. Keep it under the wall
thickness of a vessel the water fills.

Keep the domain rim out of frame where water pools against it. The rim is
a closed wall, so a pool there ends in a cut face that shows the water's
depth colour: a dark band at the edge of the patch.

Droplets are white-grey aerated water, never a clear liquid. Each is a
small sphere stretched along its velocity. It fades by size instead of
alpha, so centimetre drops carry no dither noise. Streams are glassy tubes
that aerate as they fall. Their streak noise is a value noise with the
engine's quintic weights over Blender's White Noise hash, because the
engine's PCG hash needs integer operations that shader nodes lack.

**Pours and streams into containers**: shape `bed_fn` as the vessel's
interior: a bowl, cup, barrel or basin is a heightfield. Share one profile
function between the visible vessel (a lathe of it) and the sim's `bed_fn`.
The container the liquid fills is then the prop's interior, and the pour
lands on a rippling, rising level that conserves mass to the brim.

## Not yet ported

- The flat reflective water (`WaterMesh`). In Blender it is a plane with a
  Principled water material and the `water_normal` texture scrolled twice by
  scene time, reflecting through ray tracing or a plane light probe. Its
  sky is the sky family's Eanpa port. Not built yet.
- `fluid_sim` (2D stable fluids). It wraps the npm package three-fluid-fx,
  whose licence has not been checked. The intended port is a numpy solver
  baked to an EXR image sequence.
- The erosion valley renders (`test_swe_erosion.py`) and carves braided
  channels with banks and silt bars. It has not been compared frame by frame
  with *The Shape the Water Left*'s renders.
- The presets other than water are ported but not yet rendered. Seep pours
  run in the erosion probe, but the seep's curtain is out of frame there.
- The deprecated `chop` agitation is not ported; the engine kept it only
  for A/B archaeology.
- `SWE_DEBUG=promo`, the promotion-potential debug paint.
