# Placement — intent-based helpers + the audits

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

A model's `position` is its origin — sometimes a corner, sometimes the
front face, sometimes an arbitrary studio pivot — so eyeballed raw
coordinates give you chairs embedded in tables. The placement helpers (all
on `globalThis`, no import) account for both objects' real bounding boxes
and raycast the geometry where it matters. Set `obj.rotation` first — the
helpers read the post-rotation bbox — and read the model's `_preview.jpg`
for its forward/up axes before deciding that rotation.

## The helpers

- **`placeOn(obj, target, { xz, yOffset, xzOffset, grid, surfaceEps, sink })`**
  seats the object's bbox bottom on the highest sampled support under its
  footprint. The current default is `xz: 'auto'`: preserve an already nonzero
  XZ position, otherwise center on the target. Use `xz: [x,z]` for an explicit
  world-space bbox-center anchor or `'centered'` to request recentering.
  `xzOffset: [dx,dz]` adds a relative offset; `yOffset` adjusts seating height.
  The target may be the scene or a group that contains obj — obj's own
  subtree is excluded from the supports, so it never lands on itself.
  `grid` controls footprint sampling (default 7); `surfaceEps` (default
  0.0006 m) lifts the object a sub-millimetre off the support to avoid
  coplanar z-fighting — pass `0` for exact contact. `sink` buries that
  fraction of the object's bbox height into the surface (clamped to 0–0.9;
  0.15–0.35 suits rocks) and sets `userData._sunkPlacement`, which exempts
  the object from the hovering/support audit.
  `placeOn`/`snapToGround` record `userData._supportTarget` for support checks.
  Inspect the result on sloped or concave surfaces; a sampled highest support
  is not proof that every part of an object rests flush.

- **`placeAgainst(obj, ref, side, gap)`** — clearance-aware side placement.
  side: `'front' | 'behind' | 'left' | 'right' | 'above' | 'below'`; gap is
  the real visible clearance between bbox edges in meters. "Chair behind
  desk", "lamp left of monitor". Bbox-based — handles offset origins, but a
  concave leading face can leave a visible gap.
- **`placeTouching(obj, target, side, { gap, dir, grid, allowIntersect })`**
  — the mesh-accurate sibling: raycasts obj's leading face against the
  target's actual geometry and slides obj along one axis until the surfaces
  kiss (or `gap` apart). `side` is the direction obj travels (`left(-x)` /
  `right(+x)` / `front(+z)` / `behind(-z)` / `above(+y)` / `below(-y)`, or
  an explicit `dir: [x,y,z]`). This is the tool for assembling anything out
  of pieces — kit parts, several models, your own meshes — flush instead of
  floating or interpenetrating. Returns `true` on contact, `false` + a
  warning when no target surface lies that way (fall back to
  `placeAgainst`). `gap: -0.02` bites in for a tight seam;
  `allowIntersect: true` tags obj so the clipping audit knows it's meant.
- **`snapToGround(obj, groundMeshes, { yOffset, below })`** — drop obj to
  whatever surface is directly below its origin's **world-space** xz, so it
  works under an offset parent. Handles stairs, slopes, terraced floors. The
  ground list may include the scene or a group containing obj; obj's own
  subtree is excluded. Verify the result on fetched-GLTF props (group
  hierarchies can defeat the snap and leave a prop silently airborne):
  raycast down from above the bbox centre, log the `bbox.min.y − hit.y`
  gap, and correct unintended clearance at the asset's scale. Partial burial
  can help a rock or fallen trunk look settled; use an appropriate negative
  `yOffset`, rather than the same depth for every prop.
- **`alignToSurface(obj, target)`** — rotate obj's +Y to the surface normal
  under it: signs on slanted roofs, props on slopes.
- **`scatterOn(items, target, { count, minSpacing, rngSeed, sink, tiltMax })`**
  — spread N items across target's top footprint in an organic layout,
  deterministic per `rngSeed`. Rocks/boulders/ruins/stumps read planted
  when partially buried: `sink: [0.15, 0.35]` + `tiltMax: 0.3`. (An
  ordered row of books on an interior shelf board is a different task —
  the shelf recipe below.)
- **`findClearSpot(obj, around, { radius, scene })`** — spiral-search a
  Vector3 where obj's bbox fits without overlapping anything, for
  placements no specific surface anchors.
- **`faceToward(obj, target, { forward })`** — yaw-only aim at an
  Object3D / Vector3 / [x,z]. `forward` is which local axis the model's
  nose points along — read it off the preview's axis guides ('+z' default;
  many GLBs are '-z' or '±x'). Guessed `rotation.y` constants are where
  statues face the wall.
- **`driveAlong(obj, waypoints, { duration, forward, startTime, loop })`**
  — the way to move a vehicle / creature / anything elongated. Returns an
  function `drive(t)`; call it each frame. Moves obj along a smooth curve through
  the waypoints and yaws it to face travel — coupled, so it can't slide
  sideways (a bare `position.x = lerp(...)` sends a model perpendicular to
  its own wheels; the motion audit flags that as sideways travel;
  deliberate lateral slides — conveyor, crab — declare
  `obj.userData.noMotionCheck = true`). Exemptions describe intended motion;
  they do not correct a mismatched forward axis. `forward` has
  no default because there is no universal nose axis — read the preview;
  for vehicles you build yourself, the house convention is nose along +Z.
  driveAlong cross-checks the declared forward against the model's long
  axis and warns on perpendicular; backwards it can't detect (no geometry
  knows which end is the nose) — only the preview shows that. Models that
  are easy to misread get a curated `driveAlong/faceToward forward axis`
  line from fetch_model — when a hint is printed, it wins.
  ```js
  // read THIS model's preview for its nose axis — per-model, never copied
  const drive = driveAlong(car, [[-8,0],[0,1.5],[6,0]], {
      duration: 30,
      forward: '-x',   // from this car's preview; yours will differ
  });
  // renderFrame: drive(t);   wheels point where it goes
  ```
- **`stationBeside(obj, machine, { gap, side, forward })`** — a worker or
  machine that operates on something stands beside it, facing it: a robot
  arm beside its conveyor, a bartender behind the bar. Places obj clear of
  the machine's working edge, base at floor level, nose aimed at the line.
  The audit flags a conveyor/belt/assembly-line with a tall object planted
  through its surface (riding parcels are fine; intentional intrusion:
  `obj.userData.noIntrusionCheck = true`).
  ```js
  stationBeside(robotArm, conveyor, { gap: 0.3, forward: '+z' });
  ```

## Composition recipes

```js
// Desk on the floor, chair behind it, laptop on it, mug right of laptop.
placeOn(desk, floor);                          // desk bottom on floor
placeAgainst(chair, desk, 'behind', 0.25);     // 25cm of clearance
placeOn(laptop, desk, { xz: 'centered' });     // laptop centered on desk
placeAgainst(mug, laptop, 'right', 0.08);      // mug 8cm to the right
snapToGround(mug, [desk]);                    // seat vertically, preserve its XZ

// Character standing on stairs.
character.position.set(2, 5, 1);               // approximate xz target
snapToGround(character, [stair1, stair2, stair3, landing]);

// Eight boulders settled across a clearing, partly buried and leaning.
scatterOn(boulders, clearing, { count: 8, minSpacing: 1.2, rngSeed: 7,
                                sink: [0.15, 0.35], tiltMax: 0.3 });

// A bench somewhere clear near the fountain.
const spot = findClearSpot(bench, fountain.position, { radius: 3, scene });
if (spot) bench.position.copy(spot);
```

**Filling a shelf / cabinet / bookcase (interior boards):**
`placeOn(item, shelf)` snaps to the unit's *outer top*, and hand-guessed
board heights drop books inside the carcass. The board's true surface comes
from `snapToGround`:

```js
// Books standing upright, spines out, on the second board from the top.
// 1. Rotate each book upright + spine-out first (check its preview — many
//    book GLBs sit flat by default).
// 2. Position inside the shelf footprint, a little above the target board,
//    then snapToGround({below:true}) onto the board beneath it.
for (let i = 0; i < n; i++) {
    const b = bookProto.clone();
    b.rotation.set(0, spineOutYaw, 0);          // upright, spine out
    b.position.set(shelfX - 0.3 + i * 0.05,     // along the board
                   boardApproxY + 0.25,         // just above the target board
                   shelfZ);                     // inset from the front edge
    snapToGround(b, [shelf], { below: true });  // drops onto the board
    scene.add(b);
}
```

The books touch the board because the ray finds its true top. Keep them
inset from the front edge with a sliver of spacing so they don't z-fight.

## How placement goes wrong

- **Absolute coordinates with offset pivots:** `obj.position.x = x` places
  the origin at x, not the bbox center. A relative translation moves both
  origin and geometry together; it is valid when the offset is deliberate.
  Use an explicit helper anchor when you mean the visible bbox center.
- **Mixing raw world coords and helpers for related props**: helper-placed
  desk + raw-coord props on it means the props assume the desk surface is
  at world 0 (it usually isn't) and float while the helper-placed ones sit
  right. Once a surface is helper-placed, everything on it places relative
  to it.
- **Skipping the preview**: a fetched GLB can face any axis and sit on any
  side — the preview tells you the rotation to set before placing.

## The audits (they run after `setup()`)

All audits operate on whole placed objects — a multi-part desk or shelf is
checked as one thing. Warnings are observations to investigate. Bounding-box
heuristics, nested groups, GPU deformation and intentional overlaps can produce
false positives or missed cases. Inspect the named geometry and actual motion.

- **`checkClipping(scene)`** — pairwise bbox intersection, reported
  (intentional parent/child nesting skipped). With the repair opt-in below,
  intersecting pairs are pushed apart along the shortest-overlap axis. It
  also runs a mesh-accurate
  deep-interpenetration pass and prints, by name:
  `[checkClipping] ⚠ N object(s) substantially INSIDE another` — a whole
  object engulfed by another (a tree inside a car), as opposed to the bbox
  "clipping pairs" list, which is mostly resting-contact noise. The engulfed
  case is a detector: it moves nothing, and the fix is a clear xz
  (`findClearSpot`) or a proper seat (`placeOn` / `placeTouching`).
  Intentional overlap (a stake driven into ground, a sword through a body)
  declares itself: `obj.userData.allowIntersect = true`.
- **`checkHovering(scene)`** — floating-object audit, descending through a
  single wrapper group to reach your props. For every placed object it
  footprint-samples the surface below: **near** (a 0.005–1.0 m gap — the
  "laptop slightly off the desk" smell) is measured and reported (snapped
  down only by the repair opt-in); **far** (>1 m
  above the nearest surface) and **void** (nothing beneath at all — the
  hand-coords tell) escalate to `[placement] ⚠ RE-RENDER REQUIRED`, since
  there's no safe snap target. An object goes unflagged three ways: it
  rests at/near ground level; all its meshes are transparent (glow planes,
  holograms — auto-skipped); or you declare it a floater:
  `obj.userData.noSupportCheck = true`. Floating is fully supported —
  drones, balloons, chandeliers, a character mid-jump — the declaration is
  what separates them from an accidental float, which stays caught.
  Objects buried by `placeOn`/`scatterOn` `sink` are skipped.
- **`checkZFighting(scene)`** — coplanar-surface audit. A poster/screen/label/sign placed at the exact depth of the
  surface behind it flickers frame-to-frame (the depth buffer can't pick a
  winner) — offset flat things a few mm proud (`wall.z + 0.005`) or set
  `material.polygonOffset = true; polygonOffsetFactor = -1`. The repair
  opt-in nudges flagged panels a few mm out; an intentional flush decal
  opts out with `obj.userData.noZFightCheck = true`.

**The audits are warn-only by default.** A scene that sets
`globalThis._autoFixPlacement = true` (in `setup()` — the flags are
snapshotted when setup ends) gets a repair pass before the audits:
`checkClipping`, `checkHovering` and `checkZFighting` run once with
`autoFix: true`, then the warn-only audits judge the repaired scene.
`globalThis._noAutoPlacementCheck = true` skips both the repair and the
placement audits. Repair is a safety net, not a placement method — things
placed right don't need it, the `far`/`void` cases can't be repaired at all,
and it pushes apart geometry that overlaps on purpose (see
[vegetation.md](vegetation.md) for trees).

**TSL caveat:** vertex deformation in a `positionNode` happens at render
time, so `Box3.setFromObject` (and every helper above) sees the undeformed
extent. A TSL-warped mesh wants `mesh.geometry.boundingBox = new
THREE.Box3(min, max)` set to the deformed extent before placing relative to
it — the helpers honor a pre-set `geometry.boundingBox`.


## Hinged parts

`hinge(mesh, edge)` returns a pivot Group at an edge of the mesh's measured
bounds and reparents the mesh while preserving its placement. Edges are
`back`, `front`, `left`, `right`, `top` and `bottom`.

```js
const lidPivot = hinge(lidMesh, 'back');
lidPivot.rotation.x = -Math.PI / 3;
```

Back/front edges commonly rotate around X; vertical left/right door edges
rotate around Y; horizontal top/bottom flaps use X or Z. The helper only sets
the pivot position, not a constrained rotation axis. Check its result and mesh axes
before animating. Rotate the returned pivot, not the original mesh's center,
and inspect clearance through the full swing. This is a generic rigid pivot,
not an IK solver or a replacement for authored robotics ports/joints.

## Surface mounts and interior placement

- `surfacePoint(obj, dir, { exclude })` raycasts inward from outside the
  object's bounds along a world-space `THREE.Vector3` direction. It returns
  `{ point, normal, distance }` in world space, or `null` if no surface is hit.
- `mountOn(part, mount, { dir, standoff, faceAxis, exclude })` seats a part at
  that surface. `faceAxis` is the part's local back axis to align into the
  mount; omit it to retain rotation. `standoff` adds clearance in meters.
  It returns `{ point, normal }` or `null`. The helper assumes an unrotated
  parent; use the robotics port API for authored joints and transformed
  assemblies. Check clearance around a spinning part through its full motion.
- `placeInside(obj, container, { aimY, matchYaw, xzOffset })` centers an item
  inside a compartment and snaps it to a surface below `aimY` in world meters.
  `matchYaw` defaults true; `xzOffset` shifts the footprint. Choose `aimY`
  between the desired shelf and the shelf above. Returns the snap result.
- `placeRelativeTo(obj, ref, side, gap)` is a deprecated alias of
  `placeAgainst`; use the latter name for new scenes.

```js
const bearing = mountOn(rotor, housing, {
  dir: new THREE.Vector3(0, 1, 0),
  faceAxis: new THREE.Vector3(0, -1, 0), standoff: 0.01,
});
if (!bearing) console.warn('Rotor mount surface was not found');
const seated = placeInside(bookProp, bookcase, { aimY: 1.1, xzOffset: [0.1, 0] });
```

## Additional observations

`checkDensity(scene, { min: 5, exclude: [] })` returns a count of top-level
objects containing visible mesh geometry. It is a grouping/density observation,
not a quality requirement. A whole village can be one group.

`checkFacing(scene, { minSize: 1.2, thinFrac: 0.28, buriedAt: 0.3 })` returns
findings about buried or obstructed thin textured panels without moving them.
VRM and other skinned characters are skipped (their bind-pose parts are not
panels).
It does not know which side carries readable text. Inspect both sides and
the authored forward direction. `noFacingCheck` records an intentional exemption.

`checkLineIntrusion(scene)` returns `{ obj, line }` findings for tall objects
passing through name-matched transport lines. It uses bounding-box/name
heuristics, not a manufacturing simulation. `noIntrusionCheck` declares an
intentional intrusion; it does not make an arm clear of a conveyor.
