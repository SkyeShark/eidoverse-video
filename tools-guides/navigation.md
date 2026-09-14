# VRM autonomous navigation, sensors and memory

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the character navigation stack, independent of the modular robotics
asset kit. The renderer injects its classes. Read [characters.md](characters.md)
for VRM loading, collision-aware locomotion and foot IK first.

## Control a body

```js
const body = await VRMRobotBody.create(vrm, mixer, _s, options);
// Start an action without blocking setup; it resolves as frames advance.
const arrival = body.walkTo(4, -2);
// In renderFrame(t): body.update(t, dt);
```

The body owns its controller's updates. Do not update that controller or mixer
a second time. Movement promises need the frame loop to run; awaiting arrival
inside `setup()` prevents the movement that would resolve it.

Actions include `walkTo(x,z)`, `runTo(x,z)`, `walkToLandmark(name)`,
`lookAt(x,y,z)`, `faceDirection(radians)`, `scanArea({yawRange,duration})`,
`performAction(name,seconds)` and `stop()`. Observe with `observe()`,
`canSee(x,y,z)`, `distanceTo(x,z)`, `pathTo(x,z)`, `getPosition()`,
`getHeading()`, `getHeadDirection()` and `isMoving()`.
Use `tagLandmark(name,x,z,options)`, `getLandmarks()` and `getMap()` to inspect
its learned map. Check rejected/unreachable actions instead of teleporting
the character to make a route appear successful.

For explicitly choreographed waypoints, use `EidoverseRobotController` or
`VRMCharacterController` as shown in [characters.md](characters.md).

## The three underlying systems

```js
const sensors = new RobotSensors(_s, {
  hFov: 110, vFov: 70, range: 6, hRays: 24, vRays: 16,
  excludeObjects: [vrm.scene]
});
const memory = new RobotMemory({size: 50, cellSize: 0.2});
const planner = new RobotPlanner({agentRadius: 0.35, optimistic: true});
const reading = sensors.sense(headPosition, headingRadians, pitchRadians);
memory.applySensorReading(reading, {floorY: 0});
const path = planner.findPath(memory, startX, startZ, goalX, goalZ);
```

Sensor field-of-view options use degrees; heading/pitch use radians. Exclude
the character's own geometry. Readings contain hits, distance, position, normal
and object. Memory stores unknown/free/blocked/cliff/hazard cells with confidence
on an XZ grid; serialize it explicitly if persistence is needed. A planner path
is an array of `{x,z}` or `null`. `isPathBlocked(memory,path)` supports replanning.
Optimistic planning treats unknown cells as potentially walkable; it does not
establish that a route is clear before observation.

`RobotDebug` supplies sensor, occupancy and path overlays. Use these to diagnose
navigation, then remove diagnostic geometry from a finished shot unless it is
part of the intended visual language. The controller's collision/foot support still needs inspection
on stairs, slopes and obstacles; an A* route alone is not a motion validation.

`terrain_base.js` is a complete locomotion scene template driven by
`TERRAIN_CONFIG` and `ASSETS.character_vrm`. It defines `setup`, `renderFrame`
and `cleanup`; do not eval it into an already-running scene as a passive helper.
The obstacle-course example demonstrates the controller vocabulary.
