# Particles — make_particles, particle morph

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Two systems, both stateless functions of the scene clock, both one Geometry
Nodes graph on a point cloud, so a saved .blend scrubs, re-renders and motion
blurs with no script running:

- `eidoblend.fx.particles`: `make_particles`, the Blender edition of
  `particles.js`. Sparks, embers, smoke, dust, snow, magic, stars, muzzle
  flashes and fire, on the engine's 80-sprite library.
- `eidoblend.fx.particle_morph` and `eidoblend.fx.particle_targets`:
  `make_particle_morph`, the Blender edition of `particle_morph.js`. A cloud
  that dissolves anything and reforms it as anything else: a body, a model from
  a file, a neural net, a word, an image, a volume. Each shape keeps its own
  colours.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend.fx.particles import make_particles
from eidoblend.fx.particle_morph import make_particle_morph
```

## `make_particles` — sparks, smoke, dust, snow, magic, fire

Each particle's position is a closed-form function of time, as in the engine:

```
tL  = fract(t · speed / lifetime + phase)
age = tL · lifetime
p   = origin + emit + vel · age + ½ · gravity · age² + drift + swirl
```

The flame preset also converges toward the axis. Geometry Nodes does the work,
driven by Scene Time:

- a point per particle carries its emit offset, launch velocity and seed;
- a quad is instanced on each point and turned to the active camera, and the
  flame preset spins it in its own plane;
- size changes over life;
- each particle's life phase, twinkle, opacity and colour are stored for the
  material.

`blender/tests/particles/test_particles_presets.py` checks the graph's
particle centres against `particles.js`'s positionNode in numpy for every
preset, to within 4 µm. It also checks that every quad faces the camera.

```python
make_particles('embers', map='glow_soft', origin=(0, 0, 0.35), count=90, size=0.035, area=0.25)
make_particles('fire', map='flame_05', origin=(0, 0, 0.10), count=120, size=0.46, area=(0.18, 0.18, 0.05))
make_particles('sparks', map='spark_05', origin=(0, 0, 1))      # the engine's example, origin [0, 1, 0]
make_particles('snow', map='auto', origin=(0, 0, 9))             # the table's sprite for the preset
```

| preset | count | size | life (s) | blending | `map='auto'` picks |
|---|---|---|---|---|---|
| `sparks` | 220 | 0.06 | 0.9 | additive | `spark_05` |
| `embers` | 140 | 0.05 | 2.6 | additive | `glow_soft` |
| `smoke` | 70 | 0.7 | 4.5 | normal | `smoke_04` |
| `dust` | 160 | 0.04 | 6.0 | normal | `dot` |
| `snow` | 320 | 0.05 | 8.0 | normal | `dot` |
| `magic` | 180 | 0.08 | 2.4 | additive | `magic_05` |
| `stars` | 420 | 0.07 | 3.0 | additive | `star_06` |
| `muzzle` | 48 | 0.45 | 0.22 | additive | `muzzle_02` |
| `fire` | 150 | 0.5 | 0.55 | additive | `flame_05` (or `flame_06`) |

Stage each preset the way it is used. The probes in
`test_particles_presets.py` (its `STAGES` table) show where each one reads:
- glowing presets on a dark backdrop;
- smoke against a darker dusk sky;
- snow falling from about 9 m: the engine's snow accelerates, it has no
  terminal speed;
- stars around a camera at their centre. The field is 22 m across, and its
  7 cm sprites are 3 to 6 px at 960 px through a 35 mm lens. A wide lens
  shrinks them to faint single pixels, so pick a bold sprite (`star_06`) or
  raise `size` for a sky that reads;
- sparks, fire and the muzzle flash at 2 to 3 m, where their sizes were tuned;
- fire above whatever it burns on. The sprites are depth-tested, as in the
  engine, and the preset's 0.5 m flame quads reach below the emitter, so a
  bare floor cuts them along straight grey lines. Set the fire on logs, as
  round one's campfire test (`blender/tests/fx`) does, or lift the emitter.

- Override any preset field: `count`, `size`, `color`, `origin` (or
  `position`, the engine's alias), `gravity`, `speed`, `lifetime`, `area`,
  `grow`, `wobble`, `opacity`, `blending`, `up`, `spread`, `twinkle`, `swirl`,
  `flame`, `converge`, `rotate` and `intensity`.
  - `area` takes a radius or `(x, y, z)` extents. An invalid value falls back
    to the preset's, with a warning. In the engine a NaN area silently killed
    the emitter.
  - Override `gravity` and `area` in Blender axes (Z up).
- `opts=` takes the engine's options as one dict, the way a scene.js wrote
  them, in three's axes: `make_particles(opts={'preset': 'sparks', 'origin':
  [0, 1, 0], 'gravity': [0, -4, 0]})`. Keywords win over it.
- `scene=` takes a Blender scene, or the engine's group: a collection links the
  emitter there, and an object becomes its parent (the emitter moves with it,
  and `origin` is in the parent's frame), as `corner.js` passed its set's
  group. `collection=` and `parent=` say the same thing directly.
- `map` takes a library sprite by name (`'flame_05'`), a path, a Blender
  image, or `'auto'` (the table's pick). With no map, particles get the
  engine's soft procedural dot.
- `camera=` turns the quads to that camera. Left out, they face whichever
  camera is active at each frame, so marker-bound cuts are followed.
- `seed` fixes every particle. The engine used `Math.random()`.
- `time_offset` shifts the clock: t = (frame − frame_start) / fps + offset.
- `lit=True` shades normal-blended matter (smoke, dust, snow) by the scene's
  lights. Without it, it stays unlit like the engine's MeshBasicMaterial.

### Keyed uniforms: a burst, a moving emitter

The engine's live uniforms are keyable here. `size`, `opacity` and `color`
are the Geometry Nodes modifier's inputs, and `origin` is the object's
location. Each is a `Uniform`: `.value` sets it, `.key(frame)` keys it, LINEAR
by default.

```python
p = make_particles('magic', map='magic_05', origin=(-1, 0, 1))
for f, v in ((1, 0.0), (30, 0.0), (36, 1.0), (60, 0.15)):     # "pulse uniforms.opacity.value for a burst"
    p.uniforms.opacity.value = v; p.uniforms.opacity.key(f)
p.uniforms.origin.value = (-1, 0, 1); p.uniforms.origin.key(1)  # a moving emitter
p.uniforms.origin.value = (1, 0, 1.4); p.uniforms.origin.key(72)
p.uniforms.color.value = '#5cf0ff'; p.uniforms.color.key(72)
```

### Glow in daylight, and the engine's display

Additive particles add light, so they vanish against a bright sky (adding to
white shows nothing). Stage glowing particle work against dark backgrounds.
For daylight there is the engine's light-motes recipe: the `snow` preset with
`glow_soft` and a warm colour. Normal blending survives a bright sky.

```python
make_particles('snow', origin=(0, 0, 1.6), map='glow_soft', color=0xffd28a, size=0.06, count=260)
```

The engine drew its frames through three's ACESFilmic. The film's view here is
AgX, which carries bright saturated light to white along a different path, so
a dense additive stack reads cream-white sooner. `intensity` scales the
emission. It dims the stack but does not change its hue: the fire ramp itself
starts near white.

`create_particles_compose(scene)` shows the additive sprites' light the way
three's ACES showed it, and leaves the rest of the frame to AgX.
- It turns on EEVEE's Transparent pass, which holds exactly the light of
  BLENDED surfaces: the additive sprites. Normal-blended sprites dither with
  the opaque surfaces and are not in that pass.
- It runs that light through three's ACESFilmic at the scene's exposure and
  the sRGB transfer, then through the inverse of the scene's view (OCIO).
- It adds the result back to the rest of the image.
- A scene that already composites (the fire's compose, the look's post chain)
  gets the match inserted right after its Render Layers.
- Use the look 'None' for an exact match.

```python
from eidoblend.fx.particles import create_particles_compose
create_particles_compose(scene)               # after the scene's view, exposure and compositor are set
```

## Particle morph — dissolve and reform anything

The morph is a cloud of N particles. Each one sits on point i of the current
target, and a morph carries it to point i of the next one. Its position is
the engine's positionNode:

```
me     = smoothstep(0, 1, morph)
base   = spin( mix(target_from, target_to, me) )                 about the cloud's vertical axis
baseV  = turn(base, vortex · sin(π morph) · (0.8 phase + 0.6))  a per-particle swirl, peaking mid-morph
disp   = (sin p.y − cos p.z, sin p.z − cos p.x, sin p.x − cos p.y) · turb_scale,
         p = baseV · curl_scale + 0.35 t + 12 phase
center = baseV + disp · turb · sin(π morph) · curl_strength      loose in transit, crisp at both ends
```

Each particle is drawn as a camera-facing soft dot, or the sprite `map`, that
twinkles. Its colour runs from `color` to `color2` across a morph, or from
each shape's own colours to the next shape's.

`test_morph_parity.py` checks this against the engine, number for number:
- the engine's own `particle_morph.js`, run in Deno on a seeded mulberry32
  stream, against the port on the same stream: every generator, the
  resampling, `makeParticleMorph`'s buffers, `morph()` and `updateTarget()`;
- the graph's positions against the TSL positionNode in numpy, within 2 µm.

### One call

```python
from eidoblend.fx.particle_morph import make_particle_morph, key_visibility
from eidoblend.fx.particle_targets import from_object, target

body = from_object(robot_vrm, 60000, live=True)      # my body, bound live to its skinned surface
m = make_particle_morph(count=60000, size=0.022, blending='normal',
                        targets=[body,                                        # in its own colours
                                 ('polyhaven:alarm_clock_01:2k', {'fit_height': 1.5, 'at': (-1, 0, 1.05)}),
                                 ('neural_net', {'width': 3.2, 'height': 2.0, 'at': (-1, 0, 1.05)}),
                                 ('text:CLAUDE', {'width': 3.6, 'at': (-1, 0, 1.05)})])
m.key_hold(0, 1)
m.key_fade(44, 56, 0.0, 1.0)                                       # the cloud appears over the walking body
m.key_sequence([(1, 56, 104), (2, 128, 172, {'ease': 'in_out_sine'}),
                (3, 192, 240, {'vortex': 6.0, 'turb': 0.55, 'turb_auto': True})])
key_visibility(robot_vrm, 1, True); key_visibility(robot_vrm, 56, False)   # the hand-off, keyed
```

`targets` takes two or more of anything below, each resampled to `count`.
`make_particle_morph` returns a `ParticleMorphSystem` with:
- `object` (also `.mesh`), `material`, `modifier`, `node_group`, `count` and
  `targets` (one `Target` each);
- the engine's calls: `morph`, `update_target`, `set_targets`, `update`;
- the keyed timing: `key_morph`, `key_sequence`, `key_hold`, `key_fade`,
  `key`, `set_stagger`;
- `uniforms`.

### Driving it

**The engine's way, per frame.** `m.morph(from_idx, to_idx, t01, turb,
frame=f)` keys one frame:
- the segment is keyed CONSTANT, the factor and turbulence LINEAR;
- `turb=None` is the engine's default sin(πm), computed in the graph, so it
  is exact between frames too;
- inside a harness `render_frame`, pass `ctx=ctx` instead of `frame`.

**Whole transitions.** `m.key_morph(from_idx, to_idx, start, end, ease, turb,
turb_auto, vortex, spin)` keys one transition:
- the segment switches at `start`;
- Morph runs 0 → 1 with the easing, then holds;
- `turb`: None for the engine default, a number for a fixed turbulence, a
  number with `turb_auto=True` to scale the default (the films' usual 0.55);
- `vortex`: a number for the segment;
- `spin`: `(a0, a1)` radians over the segment.

`m.key_sequence(steps)` chains transitions. Each step is `(to, start, end)`,
`(to, start, end, {opts})` or a dict, and starts from the previous step's
target.

Easing names:
- `'linear'`: the engine's own motion (the position is smoothstepped inside
  the graph anyway);
- `'constant'` and `'smooth'` (Bezier);
- any Penner curve, `sine` `quad` `cubic` `quart` `quint` `expo` `circ`
  `back` `bounce` `elastic`, with an `in_`, `out_` or `in_out_` prefix. These
  are Blender's own F-curve easings.

`m.key_hold(idx, frame)` holds a shape crisp. `m.key_fade(start, end, a, b)`
keys the opacity, or any uniform by name. `m.key(name, frame, value, ease)`
keys a single uniform.

**Uniforms.** These are keyable `Uniform` handles on the modifier's inputs:
- the engine's: `morph`, `turb`, `spin`, `vortex`, `size`, `opacity`, `color`,
  `color2`;
- this edition's: `from_idx`, `to_idx`, `turb_auto`, `curl_scale`,
  `curl_strength`, `center`, `own_color`, `gain`, `stagger`, `stagger_axis`,
  `stagger_lo`, `stagger_hi` and `points_only`.

**The hand-off.** `key_visibility(src, frame, visible)` keys a body, model or
collection shown or hidden from a frame on, CONSTANT, in the viewport and the
render. A hidden object still evaluates for the cloud: a live target keeps
following a walking body after it is hidden. The checks confirm the cloud on
the hidden body to 2e-7 m.

**`update_target(idx, pts)`** swaps one target. One index past the last adds
one. The engine's live-pose capture is
`m.update_target(0, from_mesh(vrm, m.count, frame=dissolve_frame))`: a
snapshot of that frame's pose. A .blend keeps one point set per target index
for the whole film, so to change a target mid-film, add it as a new index and
key the segment to it.

### Targets from anything (`eidoblend.fx.particle_targets`)

A `Target` holds:
- points, (m, 3) float32, in Blender world coordinates;
- colours, (m, 3) linear RGB, or None (the cloud's `color` / `color2` then);
- an optional **live binding**: three vertex indices and barycentric weights
  per point, into the evaluated meshes of a set of objects.

The morph graph samples a live binding every frame (Object Info, then Sample
Index). A walking, skinned body dissolves from the pose it has on that frame,
and a reform lands on the pose it has then.

`np.asarray(target)` gives the points (a live one's at the current frame).
These return a new Target:
- `t + (x, y, z)`, `t.translated(v)`;
- `t.scaled(s, about)`, `t.rotated(euler, about)`;
- `t.at(point, anchor)`, with anchor `'centroid'`, `'base'` or `'center'`;
- `t.fit(height=, width=, size=)`;
- `t.flattened(axis)`, `t.tinted(colour)`, `t.with_colors(rgb)`;
- `t.resample(n)`, `t.take(indices)`.

A live target transforms through a matrix the graph applies every frame.

| source | call |
|---|---|
| any Blender object, evaluated: modifiers, shape keys, armatures; curves, text objects, surfaces, metaballs; Geometry Nodes output (meshes, instances, point clouds); collection instances; particle-system instancers; a whole collection; a VRMHandle | `from_object(src, n, mode='surface', live=False, frame=None)` |
| the engine's vertex sampling (`fromMesh`) | `from_mesh(obj, n)` (live=True, frame=, colors=) or `from_object(src, n, mode='vertices')` |
| the inside of a closed mesh | `from_object(src, n, mode='volume', voxel=None)` |
| curves without bevel, wires | `from_object(src, n, mode='edges')` (automatic when there are no faces) |
| a file or a library name: .glb .gltf .fbx .obj .vrm .stl .usd* .abc .dae .blend, `'polyhaven:<id>[:<res>]'`, `'model:<name>'` (the repo's own `eidoverse/assets/models`, by name or a word of it: `'model:crow'`), `'vrm:<name>'`, `'asset:<path under eidoverse/assets>'` | `from_file(spec, n, fit_height=, at=, rotate=, clip=)` |
| an image: alpha (a silhouette), luma, dark (ink on paper), any, edges; in the pixels' colours | `from_image(img_or_path, n, width=4, mode='alpha')` |
| a model's flat cut-out silhouette along a view axis, in its colours | `from_silhouette(src, n, axis='-y')` |
| a POINTCLOUD object, a vertex-only mesh, .ply .npy .xyz .csv .txt .pts, an (m, 3 or 6) array | `from_point_cloud(src, n)` |
| a Volume object or a .vdb, coloured by density | `from_volume(src, n, threshold=0.05)` |
| text, multi-line ASCII art, a block banner | `'text:HELLO'`, `'ascii:<art>'`, `'banner:HELLO'` (`from_text`, `ascii_banner`) |
| the engine's diagrams | `'neural_net'`, `'neuron_graph'` |
| the shapes the films hand-rolled for `fromPoints` | `shapes.sphere`, `scatter`, `galaxy`, `ring`, `torus`, `helix`, `spiral`, `disc`, `lattice`, `line`, `cube` |

**One call.** `target(spec, n, **opts)` resolves any of these. It takes:
- a Target, an array, an Object, a Collection, a VRMHandle or a bpy Image;
- a string spec;
- a dict, such as `{'text': 'HI', 'width': 5}` or
  `{'shape': 'galaxy', 'arms': 4}`;
- a tuple `(spec, {opts})`.

Placement options apply to all of them: `fit_height`, `fit_width`, `fit_size`,
`rotate`, `at` and `anchor`. `make_particle_morph` passes every target through
it.

**Colours.** Each sampled point takes the colour of its material where it
lies:
- a Principled BSDF's Base Color: its image texture sampled at the point's UV
  (through a multiply tint), or the plain value;
- the VRM add-on's MToon base colour and texture, when MToon is enabled;
- a Diffuse, Emission or Toon colour, or a colour attribute;
- plus the material's emission.

Some points get no particles:
- glass and mostly-transparent materials (`skip_glass`);
- alpha-cut texels: leaves, decals;
- the VRM add-on's MToon outline shells.

Byte sRGB textures are linearised. Textures are read at 1024 px at most.

**Live.** `from_object(vrm, n, live=True)` binds every particle to a
barycentric point of the evaluated surface. It works for mesh objects whose
vertex count stays fixed: armatures and shape keys keep it, while a
topology-changing modifier does not. Instanced geometry is sampled static.

An animated model from a file follows its own clip in one call. `clip=`
plays the model's embedded animation, or a VRM's VRMA slot, over the scene's
range, and the cloud follows it while the model stays hidden:

```python
crow = target('model:crow', 20000, live=True, clip=0, fit_size=1.1, at=(5.4, 0, 1.4))   # its 'Caw' clip
m = make_particle_morph(count=20000, targets=[crow, 'text:CAW'])
```

Hiding a source hides what it draws and leaves its armature alone. With its
armature hidden as well, a mesh stops posing.

**Equal counts, centroids, pairing.**
- Every target is resampled to `count`. Point lists use the engine's
  `resampleToN`: cycle with a ±1 cm jitter when upsampling, stride when
  downsampling. Samplers draw exactly `count`.
- `align='centroid'` moves static targets onto the first target's centroid,
  at `align_frame` for a live one: the engine's "share centroids if a jump
  isn't wanted".
- `pairing='height'` sends top to top, and `'space'` (a Morton curve) sends
  nearby to nearby, for a cleaner reform than the engine's random pairing
  (`'index'`).

**Stagger and centre.**
- `stagger=0.4, stagger_by='down'` makes particles leave and land in turn:
  head first. `stagger_by` also takes `'up'`, a direction, or `'random'`.
- `center=` sets the vertical axis spin and vortex turn about. The engine's is
  the world origin: a body at x = 2 swirls around x = 0. Pass `'auto'` for
  the first target's centroid, or a point.

**Rendering.**
- `render='billboard'` is the engine's soft dots or sprite map.
  `blending='additive'` glows. `'normal'` dithers: dark colours stay dark, so
  a model reads as itself.
- `render='sphere'` draws small icospheres. `lit=True` with normal blending
  makes Principled beads that the scene lights.
- `render='points'` makes a point cloud, which EEVEE draws as spheres: the
  cheapest at huge counts.
- `realize=True` gives one mesh instead of instances, for motion blur.
- `own_colors` (a 0..1 number blends toward `color`/`color2`) and `gain`
  shape the colour.
- `scene=` takes the engine's group as `make_particles` does: an object
  parents the cloud, and static targets are then read in its frame. A
  collection holds the cloud.

### The ASCII terminal panel

`ascii_panel` is the engine's `makeAsciiPanel`, the glowing terminal that the
text example puts under its cloud. It draws multi-line ASCII art or monospace
text onto a plane: a background fill, a glow, CRT scanlines. Use it for
monitors, HUDs, code walls and server readouts, and pass `figlet()` or
`ascii_banner()` output for big letters.

```python
from eidoblend.fx.particle_morph import ascii_panel
term = ascii_panel('+------------------+\n|  SIGNAL ACQUIRED |\n+------------------+',
                   color=0x33ff88, bg=0x02100a, width=5.0, font_size=20, scanlines=True,
                   location=(0, 0, -2.7))           # stands facing -Y; term.mesh, term.texture, term.canvas
```

- Options: `color`, `bg`, `transparent` (no fill: an overlay), `font_size`,
  `font_family`, `width` (metres; the height follows the text), `padding`,
  `glow` (px, or False), `scanlines`. `opts=` takes the engine's dict,
  camelCase included.
- `display='exact'` (the default) is the engine's `toneMapped: false`: the
  screen shows its pixels as drawn, through the inverse of the scene's view
  when the panel is made. AgX cannot show a bright neon green at all, so the
  panel's `0x33ff88` text shows as the nearest it reaches, (114, 194, 119).
  The background and glow are exact. For neon screens exactly as drawn, render
  with the view `'Standard'`. `display='view'` is a plain emissive texture
  under the film's view.
- The image is packed into the .blend.

### The examples

`blender/tests/particles/test_morph_examples.py` ports every example in the
engine's sources and renders them:
- the module header's VRM → neuron graph → VRM, keyed per frame;
- the guide's dancing VRM → neural net with a glow map, opacity fade, vortex 5
  and the live-pose capture;
- `work/morph_text_verify`: ALETHEIA → an ASCII cat → ALETHEIA under its
  orbiting camera, with its boot terminal below, plus
  `fromText('HELLO', {width: 5})` and a banner;
- the "VRM → galaxy → the word → ASCII glyph → scatter" chain, on Aletheia;
- the low-poly note: vertex rings against surface sampling;
- the render modes;
- image, silhouette, volume and point-cloud-file targets;
- Blender's own object types as clouds in their colours: a bevelled curve, a
  text object, a metaball, a Geometry Nodes instancer, a collection instance,
  an array-modified mesh, and the repo's animated crow following its own clip.

`test_robot_morph.py` is the film case. My robot body walks in and dissolves
mid-stride in its own colours. It reforms as the Poly Haven alarm clock in its
colours, then as a neural net, then as CLAUDE with the vortex reform.
Reopening its saved .blend evaluates the same cloud with no script.
`test_targets.py` checks every target source numerically.

### Particle textures

Pass the sprite's name (`'spark_05'`), and the library's
`eidoverse/assets/particle_textures/spark_05.png` is loaded once. The sprites
are palette PNGs with transparency, read as RGBA.

### Blender 5.2 facts these systems rely on

- A multi-input socket (Join Geometry) lists and joins its links newest first.
  A live binding links its objects in reverse and checks the listed order.
- On an instance from `depsgraph.object_instances`, call a plain `to_mesh()`.
  With `preserve_all_data_layers=True, depsgraph=...` it re-evaluates the
  instancer: an empty mesh for a Geometry Nodes host.
- The VRM add-on's MToon outline is a Geometry Nodes modifier. It adds an
  inflated copy of the body as instances, whose materials have
  `vrm_addon_extension.mtoon1.is_outline_material`.
- Objects referenced by Object Info evaluate even when they are hidden and
  keyed hidden, in the viewport and the render. So does their armature, if
  the armature itself is not hidden. A mesh hidden together with its armature
  keeps its last pose in Python's depsgraph reads, so the CPU side unhides the
  meshes it reads for the read (`LiveBinding.points`).
- AgX cannot display bright saturated greens: linear pure green reaches
  (62, 168, 21) at 0.5 and only whitens above that. The canvas green
  `0x33ff88` is out of its reach, and its least-squares match is
  (114, 194, 119).
- `Image.pixels` of a byte image is the stored (sRGB) value. A generated
  image regenerates, blank, when its colour space changes: set the colour
  space before the pixels.
- three.js draws 4 `Math.random()` per UUID (each Object3D, geometry,
  material). The parity dump counts draws and skips them.
- Distribute Points in Volume on a mesh whose Geometry Nodes make the volume:
  the object's bounds don't describe the volume, so a density guessed from
  them can ask for billions of points. `from_volume` measures its density
  instead.

## Not yet ported

- The engine's `mrtNode` opt-out (sprites kept out of the G-buffer) does not
  apply. EEVEE's BLENDED surfaces write no normals or depth for AO.
  Dithered, normal-blended sprites are part of the opaque pass, like any
  surface.
- `_autoParticleSystems` and per-frame `update()`: superseded. The graphs read
  the camera every frame.
- Live targets on geometry whose topology changes over time (a Geometry Nodes
  scatter, remeshing) bind statically.
- Particle colour from a material's procedural textures (Noise, Voronoi): the
  sampler reads image textures, values, colour attributes and emission, not
  procedural nodes.
- `figlet()` uses pyfiglet when a Python has it. Neither Blender's Python nor
  this machine's has it, so banners come from `ascii_banner` (block letters
  drawn from the font).
