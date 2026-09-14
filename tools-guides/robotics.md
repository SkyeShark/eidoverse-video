# Modular robotics and G430 fabrication

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Use the baked modular kit, reusable interfaces and shared maps to assemble
industrial, mobile and humanoid robots. VRM character navigation (`robot_body`,
sensors, planner and controller) is a separate API.

## Load a module or assembled robot

```js
const robot = await makeRobot('payloads/arm_hand', {
  scene: _s, position: [0, 0, 0], color: '#d9e0df', accent: '#398b91'
});
robot.sample('joints', 2);             // explicit, deterministic seconds
robot.grasp(1);                       // all fingers + curved, opposed thumb
robot.play('joints');                 // optional engine-clock automatic update
robot.stop();
```

Creation is **asynchronous**. Add `.group` to the scene yourself if `scene` was
omitted. Metres, radians and **Three.js +Y up** are the public convention.
`setJoints` takes rotation radians and prismatic travel metres; root metadata
retains source-asset +Z axes and is converted by the runtime. Do not convert twice.

Inspect `await RoboticsKit.catalog()` for the complete catalog. It contains
85 source GLBs and four reusable humanoid subassemblies extracted from an
existing GLB; those extra entries do not duplicate the asset or texture files.
The GLBs contain many component parts and sample assemblies. File and catalog
entry totals describe packaging, not the number of unique component designs.
Use `.parts()` to enumerate a model's pieces and `loadPart` to extract one.

| Load name | Content |
| --- | --- |
| `arm` / `a650` | A650 six-axis industrial arm |
| `scara` / `s500` | S500 SCARA arm |
| `gripper`, `linear`, `rotary` | Parallel gripper, guided stage, hollow rotary drive |
| `fdm`, `cnc`, `gantry` | G430 with extruder, with spindle, or without a process head |
| `filament_spool` / `spool` | Freestanding 200 mm reel and dispenser with live filament |
| `spool_mount` | Rail-mounted carrier; `fdm` combines it with the shared reel, axle and fittings |
| `fdm_plate`, `cnc_plate` | Removable PEI sheet and T-slot table; included in their machines |
| `cnc_relief` | T-slot CNC with ball-nose tool and coordinated rough/finish relief sample |
| `cnc_rotary` / `rotary_fixture` | XYZ + A stock-rotating CNC, or its reusable drive/chuck/tailstock fixture |
| `cnc_clamp`, `tube_support`, `push_fitting`, `ball_tool` | Reusable workholding, feed hardware and the ground two-flute ball cutter |
| `process/extruder`, `process/spindle`, `process/vacuum` | Detachable process heads |
| `arm/shoulder`, `arm/upper`, `arm/elbow`, `arm/forearm`, `arm/wrist` | Modular humanoid arm sections |
| `arm/mc110_adapter`, `arm/sm40_adapter`, `arm/clamp_adapter` | Existing interface adapters |
| `hand`, `camera`, `lidar`, `face`, `interaction/antenna`, `interaction/diagnostic` | Articulated attachments |
| `mobility/body`, `mobility/tracks`, `drone` | Backbone, tracked platform, folding quad airframe |
| `humanoid_modules/left_leg`, `humanoid_modules/right_leg` | Mirrored, articulated leg modules |
| `humanoid_modules/pelvis`, `humanoid_modules/torso` | Articulated pelvis and torso |
| `payloads/arm_hand`, `payloads/arm_clamp` | Complete seven-axis arm/tool builds |
| `payloads/drone_hand`, `payloads/drone_clamp`, `payloads/rover_arm` | Mobile payload demonstrations |
| `rover`, `platforms/survey`, `humanoid`, `quadruped`, `mantis` | Complete sample platforms |
| `stock/<component ID>` | Reusable original flange, bearing, mount and connector geometry |

`makeBot({model:'humanoid', ...options})` is an asynchronous convenience loader.
Choose a catalog model and its declared joints/ports. Use Eidoverse's audio
and display tools for speech, screens and diagnostic readouts.

## Connections and reuse

```js
const body = await makeRobot('mobility/body', {scene:_s});
const camera = await makeRobot('camera');
body.attach(camera, {
  port:'body_base/sensor_0', childPort:'camera_base/input', twist:0
});
// Equivalent: RoboticsKit.connect(body, camera, sameOptions)
console.log(Object.keys(body.ports), Object.keys(camera.ports));
camera.setJoints({camera_pan:0.6, camera_tilt:0.15});
```

Mounts align their authored mating frames, oppose their normals and preserve
the source physical scale. `twist` is rotation around the attachment normal.
Mismatched interfaces and graph cycles throw; choose the declared adapter.
SM40, TC70, MC110 and other interfaces are distinct. A socket does not establish
clearance for every possible payload or motion: inspect the completed assembly.

`robot.roots`, `robot.specs`, `robot.ports`, `robot.parts()` and `robot.stats()`
expose the actual content. Repeated humanoid joints use qualified names, so a
left-hand or leg command cannot accidentally target the right-side copy.

### Individual components inside a GLB

GLBs preserve named part meshes and articulated node hierarchies. Some exports
batch several parts into one mesh; the included `provenance/` sidecars identify
which triangles belong to each part. Use the loader below for either layout:

```js
const catalog = await RoboticsKit.catalog();
console.log(catalog.models['interaction/face'].parts); // discover exact part IDs

const yoke = await RoboticsKit.loadPart(
  'interaction/face', 'FACE swept tilt yoke', {scene:_s}
);
console.log(yoke.parts(), yoke.stats().triangles);
yoke.group.position.set(0.3, 0, 0); // offset from the original module placement
```

`loadPart` isolates only that part's triangles, preserves its baked UVs/materials
and shares cached texture maps. It retains the donor's hierarchy and origin;
it does **not** recenter the component. Other donor meshes are hidden. Missing
part names or incomplete triangle ownership throw an error. Keep `provenance/`
with `models/` and `textures/` when distributing the kit.

For a loaded module, `robot.parts()` lists its part IDs. `robot.part(name)`
returns the underlying mesh objects for inspection; a batched mesh can still
contain other parts, so use `loadPart` to isolate geometry. For common bearings,
flanges and mounts, standalone `stock/<component ID>` entries are also available:

```js
const flange = await makeRobot('stock/flange.tc70.6mm', {scene:_s});
```

Use complete catalog modules with the `attach` example above when building an
articulated robot. An extracted casting or fastener is geometry; its donor's
joint/port metadata does not make it a complete mechanical module.

Do not re-unwrap, call `layerSurface`/texel normalization on, or replace the
finished maps of these GLBs. The linear recoloring formula is
`fixed.rgb + primary * mask.r + accent * mask.g`. `setColors(primary, accent)`
changes body/accent while preserving metal, rubber, text, grime and normal maps.
The dispenser adds `filament * mask.b`; use `filament:'#218675'` when loading
or `robot.filament.setColor(color)` afterwards. It shares five 2048-square maps
between the standalone dispenser and assembled printer; tube and live strand
use no image textures.
Never reflect normal-map green or tangent.w to compensate for a mirrored object.
The NodeMaterial runtime corrects tangent-frame parity from its world transform.

## Motion and IK

`robot.clips` lists available sample names. `sample(name, seconds)` is seekable;
`play(name, {start, speed})` registers the engine clock; `stop()` removes it.
Do not run the robot's automatic sample and a fabrication job on the same axes.

- `grasp(0..1)` preserves the reviewed approach and curved final thumb contact.
  `graspReference()` creates the cylinder used for that grasp, under each hand.
- `jawGap(0..0.044)` drives both jaws and the opposed screw. Zero closes them.
- `spinRotors(angle)` drives every propeller with its proper direction.
  `fold(0..1)` parks propellers, releases locks, then folds the booms.
- `trackTravel({rootName: metres, ...})` updates both specified belts and wheels.
  The `drive` and `drive-circle` samples coordinate chassis travel with both
  tracks. Track shoes are rigid objects with shared data, not CPU-deformed meshes.
- `flight` demonstrates takeoff, translation and landing. Payload builds use
  the same rotating propeller hierarchy. These are authored kinematics, not a
  claim of flight dynamics, contact physics, actuator capability or load capacity.
- The complete humanoid and quadruped include `walk`, `run-circle`,
  `run-figure_eight` and `run-straight`. Walking plays all constituent channels;
  running uses the reviewed sampled trajectories and local joint matrices.
- A650: `joints([q1,...,q6])`, `moveTo(localYUpMatrix4, seed)` and `ik`.
  The solver is bounded damped least squares; an unreachable target throws.
  `ik.forward/inverse` retain the explicitly documented native +Z-up source-asset axes.
- S500: `scaraJoints([shoulder,elbow,quill,tool])` and
  `moveScara([x,y,z], yaw, {tcp,seed})`. The low-level `scara` solver uses native
  source-asset coordinates; `tcp` in that wrapper is likewise an authoring-axis offset.
- G430: `axes([x,y,z])` uses machine XYZ travel. `moveTool([x,height,z])` is in
  the machine's +Y-up bed frame, with height measured above the bed.
  `toolTip()` returns that same frame; `toolTip(true)` returns a world Vector3.

## FDM and CNC

```js
const printer = await makeRobot('fdm', {scene:_s});
const job = await FabSim.print(printer, meshOrGeometry, {
  size:0.04, layerHeight:0.0004, beadWidth:0.0008, infill:0.25,
  base:0.00065, feed:0.025, duration:18, color:'#278b79'
});
job.seek(4);                          // seconds of playback; may rewind
job.play();                          // optional engine-clock update
job.setColor('#da642c');              // spool, live strand and deposited print
```

FDM accepts a BufferGeometry, Mesh, or Object3D hierarchy. It snapshots parent/world
transforms, reflected placements, instances and the current skinned/morph pose,
then fits uniformly to `size`; source vertex buffers remain unchanged.
`space:"local"` ignores the root placement; `matrix` applies a Matrix4 before
fitting. Overlapping mesh solids are unioned, while interior holes remain empty.
Source materials are replaced by the selected filament color.

FDM slices the closed source solids into connected contours and alternating
infill (25% by default), with three solid bottom/top layers by default (`solidLayers:0` disables
these). Solid skins follow local ledges, recess roofs and changing cross-sections,
including surfaces below taller features. Interior columns retain sparse infill.
Open/nonmanifold slices are rejected. Travel is explicit and deposits
nothing. A single acceleration-limited feed cursor drives both the actual nozzle
and the GPU bead front. Layer height is real geometry; the finish is accumulated
beads. There is no molten-metal field or final swap to an unprinted source mesh.
The basic slicer does not generate support structures or certify printability.

The dispenser's reel rotation follows consumed filament volume using the
1.75 mm feed diameter and winding radius. It pauses during travel; direct-drive
retraction does not rewind the supply reel. `retractLength` defaults to 0.0008 m
and `retractSpeed` to 0.035 m/s. Retraction and priming take physical time with
the nozzle stationary. `job.filamentLength`, `state.filamentLength`,
`state.filamentRetraction` and `state.filamentSpeed` expose metres and metres/s.
The loaded reel requires matching `filamentDiameter`; an oversized job is rejected.

The FDM reel mounts on the fixed side rail. Filament pays off tangentially into
the carrier's forward guide, then feeds the direct-drive extruder through an
exposed span. The PTFE totals 174 mm: a 34 mm liner through the carrier, a
44 mm inward-facing lower entry and a 96 mm head entry. Straight insertion
sections seat in the fittings; the short bends guide the free strand around
the frame. The head bend turns toward the supply within its forward clearance.
Each section retains its length as the head moves.

The milky, semi-transparent 4 mm outer / 2 mm inner tube surrounds an independently
colored filament core. `robot.filament.guideTube` is the straight carrier liner;
`robot.filament.tubes` contains four cubic sections forming the lower entries; `robot.filament.supplies` holds the two smoothly joined
cubics for the exposed span. `supply` references the first of those cubics.
Machine joint controls update their uniforms automatically. The reel and extruder
share the same push fitting, with a 4.3 mm tube seat and narrower filament passage.
Routing is calibrated for this G430 layout; changed mounts need new clearance
checks. These are geometric feed paths. Pressure, temperature, elastic bending
and extra reel payout caused by head travel are not simulated.

The strand begins inside the polygonal winding surface, tangent to a baked row.
Its visible payout traverses the reel continuously and reverses smoothly at the
ends for long jobs. This represents level winding: the baked surface retains
its size and detail instead of unmeshing each layer. `remainingRadius` is the
consumption estimate used for reel timing, not a changing rendered radius.

For a separate tube or cable, create an editable cubic curve in your scene:

```js
const tube = await RoboticsKit.createPTFETube({
  points: [[0,0,0], [0,.20,0], [.12,.20,0], [.12,0,0]],
  outerDiameter: .004, innerDiameter: .002, segments: 48, color: '#e7eee5'
});
_s.add(tube.mesh);
// tube.setPoints(fourLocalPoints) changes control uniforms, never vertex buffers.
// tube.sample(u), tube.length and tube.points inspect the curve in mesh-local space.
// tube.dispose() removes the mesh and releases its geometry/material.
```

The synchronous ESM factory is exported from `robotics/index.js`. A standalone
spool exposes `filament_stand/input` (SM40) and `filament_stand/filament_out`
(PTFE4) ports. The assembled FDM uses its own G430 side-rail mount and downward
filament-out frame; do not substitute the standalone dispenser's placement.
Connect a dispenser mechanically before routing its feed.
Its `filament-feed` sample demonstrates metered reel rotation independently;
the assembled printer's fabrication job owns its feed timing. The print-head
fan follows that same physical clock at 4,800 rpm by default (`fanRpm` on the
print job). For independent head animation, use
`robot.coolingFan(seconds, {rpm:4800})`; its shroud stays fixed.

The original 450 × 520 mm FDM bed carries a 458 × 528 × 0.65 mm removable
textured PEI spring-steel sheet. Two pull tabs extend beyond its front edge.
The default `base:0.00065` places the first layer on that sheet; its extra
width is overhang for removal, not extra axis travel. `buildPlate:false` hides
the removable sheet and lets a scene provide its own fixture and `base`.
`job.plate` references the sheet assembly; disposing the job preserves it.

Give wide shots sufficient camera depth precision for the thin sheet and its
bed. The fixed manufacturing example uses a 50 mm near plane with clear
foreground space; choose a nearer plane when moving in for a close inspection.

The CNC has a separate aluminum work table: eight extrusions form seven real
T-slots with 8 mm mouths, 16 mm undercuts and 56.25 mm pitch. Four low-profile
toe clamps engage sliding T-nuts and hold the included 78 × 128 × 20 mm stock.
They fit 78 mm wide stock, 108–148 mm deep and at least 15 mm high. Other
fixtures can use `workholding:false`, which hides the included clamps while
the job exists. Supply and check appropriate workholding in that case.

The sheet, table, clamp, frame guide and push fitting share
one 512 × 1024 atlas containing base color, tangent normal and packed
AO/roughness/metalness. The PEI coating uses CC0 ambientCG Plastic004 PBR with a fine, low-contrast
powder-coated finish at a physical 100 mm scan repeat.
Matching coating regions and extrusions reuse UVs; lettering remains unique.
The maps request 8× anisotropic filtering, retained by the kit loader.

For printing, the source is uniformly fitted to `size`, centered in X/Z and
placed on the build surface. Object3D transforms are included in the planning
snapshot; `space:"local"` uses the supplied root's local orientation instead.

```js
const cnc = await makeRobot('cnc', {scene:_s});
const milling = await FabSim.mill(cnc, null, {
  material:'wood',                   // aluminum, brass, steel, wood, plywood
  stockWidth:0.078, stockDepth:0.128, stockHeight:0.020,
  resolution:192, duration:18,
  effects:{maxParticles:1200, seed:7319, dust:true}
});
const profiles = await FabSim.stockMaterials();
// Explicit paths can be supplied instead of null, or made with pocketProgram().
```

Stock selection sets surface finish and default feed, plunge, spindle RPM,
stepdown and pocket depth. Metal uses metallic PBR and small folded chips;
wood uses three-dimensional grain, larger shavings and fine dust; plywood
also exposes laminations on cut walls. Fine surface patterns are filtered to
avoid moiré. Metal presets do not emit wood dust or generic sparks.

These are illustrative motion/appearance presets for filmmaking, not machining
settings validated for real equipment. Override `feed`, `plunge`, `rpm`,
`stepdown`, `cutDepth`, `stepover` and `flutes` for your scene. A custom path's
per-move `feed` takes precedence. `job.settings` exposes the effective defaults,
cutter diameter and nominal chip load. The `cnc` assembly has a 6 mm flat end mill; `cnc_relief` has a 6 mm ball nose.
Both use `radius:0.003`; a mismatching radius or profile is rejected.

Chips originate only at newly removed material, including plunges. Air moves
and repeated passes through the same cleared volume emit nothing. A fixed GPU
particle pool evaluates emission and ballistic/damped travel from physical time,
so seeking and replay remain deterministic. `effects:false` disables debris;
wood `dust:false` retains shavings. Chips have a short lifetime rather than
accumulating on the bed; the effects do not model coolant or chip collisions.
`job.stock.removedVolume` is a grid estimate in cubic metres.

For 3D relief carving, load the ball-nose assembly:

```js
const reliefCnc = await makeRobot('cnc_relief', {scene:_s});
const target = await FabSim.sampleRelief(); // original flowing-crest sample
const carving = await FabSim.carve(reliefCnc, target, {
  material:'wood', stepover:0.0008, sampleStep:0.001,
  resolution:192, duration:24
});
carving.seek(20);
```

`carve` accepts a height function `(x,z) => height`, a sampled heightfield
`{heights,columns,rows,width,depth}`, or a Mesh/Object3D/BufferGeometry in
physical stock coordinates. For meshes, `reliefFromMesh` samples the upper
visible surface by downward rays and retains Object3D transforms. Fit the
source inside the stock before calling it. The result is a three-axis relief;
vertical undercuts and side machining require another process.

`reliefProgram` makes successive roughing rasters followed by a finer finishing
raster. Ball-footprint compensation raises the cutter tip over neighboring
high areas; `roughAllowance` leaves material for the finish. `surfaceTolerance`
is an added finish allowance on the sampled target, not a certified machining
error bound. `sampleStep` controls path sampling and `stepover` controls spacing
between finishing rows. The planner retracts above stock between rows. Use
`job.program.stages` and `state.stage` to inspect the rough/finish sequence.

Paths are arrays of `{position:[x,height,z], type:'rapid'|'cut'|'extrude', feed?}`.
Lengths are metres and feed is metres/second. The GPU evaluates the actual
swept flat-end or ball-nose cutter envelope against heightfield stock, including
sloping moves. Spatial bins avoid scanning the complete toolpath for every
stock vertex. Rewinding and seeking use the same progress cursor as the head.
`job.stock.cellSize` reports stock discretization; a finer grid resolves finer
scallops at greater rendering cost. `mill` accepts explicit cutter paths and
`carve` also accepts them. The fitted tool profile and radius must match.
Rapid moves through remaining stock, bed penetration, excessive footprint,
incompatible workholding and cuts deeper than the exposed tool are rejected.
`PrintSim.print` and `CNCSim.carve/mill` are asynchronous facade methods.

For all-around carving, use the separate stock-rotating machine:

```js
const machine = await makeRobot('cnc_rotary', {scene:_s});
const target = await FabSim.sampleRotary();
const job = await FabSim.rotaryCarve(machine, target, {
  renderer:_r, material:'wood', duration:32,
  stockLength:.140, stockWidth:.036, stockHeight:.036,
  angles:96, sampleStep:0.001, resolution:[256,96,96]
});
job.seek(16);
```

Initialize `_r` before creating the job. `rotaryCarve` accepts a BufferGeometry,
Mesh or Object3D hierarchy, or a `radius(x,angle)` function in metres/radians.
The stock's longitudinal axis is X. Supplied mesh geometry retains its world
orientation and is fitted uniformly inside the cutting region by default.
Use `fit:false` for geometry already positioned in stock coordinates.

```js
const job = await FabSim.rotaryCarve(machine, suppliedModel, {
  renderer:_r, material:'aluminum', duration:32,
  stockLength:.140, stockWidth:.036, stockHeight:.036,
  angles:12, gridStep:.0005, sampleStep:.001, stepover:.00165
});
console.log(job.program.report); // input triangles, fitting, reach and retained ends
```

Mesh planning projects actual triangles from multiple indexed directions and
makes lateral XYZ rasters. Upper bounds over clipped triangle cells protect thin
features between sample rays; the full swept cutter footprint protects nearby
surfaces. Coarser roughing precedes finishing. `gridStep` is the projection-cell
size, `sampleStep` the axial path spacing, and `stepover` the lateral row spacing.
Mesh input defaults to 12 orientations; `angles` accepts 4–96. A radius function
uses circumferential stations (default 96), with an axial stroke at each angle.

The cutter retracts beyond the uncut blank before each A-axis index; the chuck,
drive and stock turn together with XYZ stationary. Both input modes subtract
actual swept tool volume. The target mesh is never substituted for the cut stock.
This is indexed four-axis machining: inaccessible undercuts, cavities narrower
than the cutter and features requiring tool tilt cannot all be reproduced.
Mesh programs conservatively retain stock beyond the installed flute reach and
report `reachLimitedSamples`; `requireReach:true` rejects those jobs instead.
The report does not certify complete surface accessibility. Smaller stock or
another machining setup may be necessary, and sacrificial ends remain attached.

For manual fixture motion, `setJoints({rotary_output:angle})` turns its output
and chuck together. The inspector exposes this as **A axis / chuck**. Stop a
fabrication job before taking manual ownership of that axis.

The fixture accepts stock 80–180 mm long and 18–50 mm wide/high; the default
is 140 × 36 × 36 mm. Width and height can differ. The stock's chuck-side end
stays at machine X=-55 mm, and its centre is `-.055 + stockLength/2`.
Its axis is 97 mm above the table. Cutting retains 29 mm at the chuck end
and 18 mm at the tail end, in stock-local coordinates. These end allowances
protect the workholding; a separate operation is needed for part-off.
The rotary assembly uses the 6 mm two-flute flat end mill with 18 mm exposed
cutting length. The relief assembly uses a 6 mm ball nose with 17 mm exposed
cutting length. Removal follows the installed tool profile; an incompatible
requested profile/radius, offset or overtravel is rejected.

`machine.rotarySetup({stockLength, stockWidth, stockHeight, quill:0})` adjusts
all four captured jaws and the sliding tailstock, returning the stock datums
and applied joints. `rotaryCarve` calls it automatically. The tailstock travels
-60 to +40 mm on a continuous dovetail bed. Its quill travels ±6 mm and has a
1 mm-pitch handwheel; combining a quill offset with an end-of-travel carriage
can exceed the supported envelope and throws. The jaws grip 13 mm of end stock
and move independently in retained radial guideways with accessible drives.
The tailstock's carriage and quill have separate locks. Eight M6 table studs
engage sliding T-nuts beneath the 8 mm bed-slot mouths. The fixture reuses the
relief clamps' hardware and plate atlas. Inspect `RC table stud 0` /
`RC table T-nut 0` through index 7; nut undersides and exposed mouth surfaces
remain present. The rear “A / INDEX” marking identifies the stock rotation axis.

The `stock-setup` sample demonstrates the carriage, quill, handwheel and four
jaws with varied rectangular sizes. It illustrates adjustment without a
clamped blank; stop a carving job before playing it. The inspector also has
stock presets, length/width/height fields and a **Fit blank and restart carving** button that
fits the fixture and restarts the job. Stock material is an independent choice.

The fixture and optional ball cutter share one 2048-square atlas family
containing base, fixed finish, recolor mask, tangent normal and ORM maps. The
flat cutter reuses the process-head mesh and atlas. Repeated
jaws, table fasteners, braces and lock levers share their primary surfaces.
The standalone cutter keeps its closed shank; mounted variants omit the portion
permanently covered by the collet while retaining the same finish.

The blank starts with a prepared 60° centre seat in its tailstock end: 3 mm
conical depth and a 1.6 mm diameter pilot extending 6 mm from the end face.
That pilot clears the live-centre point. This preparation exists in the GPU
stock before cutting and is excluded from chip generation. The sample does not
depict centre drilling or the final part-off operation.

The GPU subtracts the swept cutter from a tiled 3D distance field and renders its
actual surface/depth. It can expose side and underside cuts, unlike a top-only
heightfield. The default two stock buffers occupy about 39 MB; `resolution` sets
XYZ voxel counts, and `job.stock.cellSize` reports their spacing. Rewind rebuilds
the same field. Chip emission uses a separate one-time volumetric engagement
sample, so repeated cuts and air travel add no false debris. Wood, plywood,
aluminum, brass and steel use the existing appearance/feed presets.

For a metal study, use `material:'aluminum'` or `material:'brass'` with the same
fixture. Their default feeds and depth steps produce more passes and longer
physical cutting times than wood. Omit `duration` to see those rates directly;
equal time-lapse durations conceal that difference. The `rotary_metal` example
includes eight seconds of physical-speed aluminum cutting before its time lapse.
Metal stock uses metallic surfaces and folded chips without wood dust or generic
sparks. The gantry depicts light machining; a steel preset does not establish
machine stiffness, cutting forces or heavy steel capability. Coolant, chip
collisions, heat and tool wear are not simulated.

`job.removal.removedVolume` is a sampled volume estimate. `job.state.angle` is
the unwrapped A-axis angle; `state.stockPosition` is the cutter tip in stock-axis
coordinates, and `state.position` is its position above the machine bed.
`rotaryProgram` exposes both planners without allocating stock buffers;
`rotaryMeshProgram` explicitly selects mesh planning. `FabSim.sourceGeometry`
creates a geometry snapshot; `FabSim.fitSourceGeometry(source,{bounds})` fits to
a Three Box3. For relief, fit above the requested floor and below the stock top
with X/Z inside the machining area before calling `carve`. Dispose temporary
snapshots after planning. Materials on input meshes do not change stock material.
`CNCSim.rotaryCarve` is also available through the injected asynchronous facade.

`duration` changes playback speed only. `physicalDuration`, `path`, `state`,
`time`, `done`, `seek`, `play`, `stop`, and `dispose` expose the job.
`state.position` and `machine.toolTip()` must agree. Workspace checks reject a
bad path before changing the machine; never clamp while extruding/cutting.
Job geometry is prepared once, with GPU position evaluation during playback.
Omit `duration` for physical timing. Spindle rotation, filament feed and chip
motion all use that physical clock even when the process is shown in time lapse.
Position and rotate the machine group freely: stock and deposition follow its
bed frame. Check stock fixtures, workholding and the full tool envelope when
creating a production scene; a valid XYZ path alone is not collision checking.

## Inspector and examples

Run `python eidoverse/robotics/serve_inspector.py` from the checkout and open
`http://127.0.0.1:8989/`. It includes the complete catalog, assembled arms and
mobile robots, motion controls, colors, wireframes, part selection, UV split view,
triangle counts, attachment ports and independent joints. It serves only the
kit and its inspector on localhost. The included Three r184 viewer is MIT and
works without a CDN or account. Three's browser WebGL fallback is also
supported; native scene rendering uses WebGPU. Keep `models/` and `textures/` together.
FDM has a separate filament color picker; CNC has a stock material selector.
Both offer physical-time or time-lapse playback (32 seconds for rotary carving,
18 seconds for the other processes), process readouts,
and an **Inspect workpiece** camera shortcut. **Workpiece source** offers ordinary
mesh examples or local STL/embedded-GLB input. Files stay local; embedded GLBs
must contain their resources. Model dimensions are uniformly fitted to the
selected process region. The same source can be tried in FDM, relief and rotary
CNC; changing the machine changes its physically accessible result. The standard
pocket CNC accepts explicit paths; choose relief or rotary CNC for mesh planning.

Renderable examples are in `eidoverse/examples/robotics/`:
`assembly.json`, `manufacturing.json`, `relief.json`, `rotary.json`,
`rotary_metal.json`, `mesh_fabrication.json`, `motion.json`, `mantis.json`.
The manufacturing scene shows FDM, aluminum pocketing and wood relief together;
the relief scene provides a close view of roughing and finishing; the rotary
scene shows the complete all-around carve from rectangular stock.
`mesh_fabrication` supplies a normal Object3D assembly to the rotary planner;
replace that source with any loaded Mesh/Group to try your own geometry.
Use `python eido.py render eidoverse/examples/robotics/manufacturing.json`.
For a Windows native renderer whose FFmpeg is outside PATH, set `FFMPEG_PATH`
to its executable; this applies to encoding and probe-frame extraction.

The slicer bundles polygon-clipping and splaytree (MIT), robust-predicates
(Unlicense), and an Apache-2.0 licensed transpiler helper. Their preserved notices
are in `eidoverse/robotics/vendor/polygon-clipping/`.

Original runtime: MIT. Original geometry and authored materials: CC0. Source
scan licenses and excluded proprietary authoring tools are recorded in
`eidoverse/assets/robotics/THIRD_PARTY.md`. No manufacturer or Isaac Sim models,
restricted reference images, fonts or proprietary Blender plugins are included.


Run the JavaScript runtime checks with:

```powershell
deno test --no-check --allow-read --allow-env --node-modules-dir=manual --no-lock eidoverse/robotics/tests/
```

`--no-check` avoids requiring separate TypeScript declarations for the installed
Three.js JavaScript package; the runtime assertions still execute. They cover
the complete catalog, deterministic motion, mirrored mating frames, independent
limbs, IK/tool calibration, workspace rejection, bead winding, mesh transforms,
overlap unions, holes, local solid skins, cutter compensation and immutable
fabrication vertex buffers. Visual/GPU review remains necessary. Example scenes
supply studio lighting and disable automatic enhancement to preserve the baked
material presentation. Assembly-audit coverage warnings remain visible;
authored kinematic demos are not a collision or dynamics certification.
