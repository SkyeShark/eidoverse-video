# Building geometry — parametric constructors, lofts, booleans, curves

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

For meshes you build rather than fetch. Each constructor takes a curve, a
profile, a flat outline, or a repeated unit and generates the surface —
that's the route to shapes no library carries.

## Parametric constructors

- `TubeGeometry(curve)` — pipes, cables, vines, tentacles, snakes, winding
  paths, hair strands. Build the curve from any point sequence
  (`CatmullRomCurve3`, `QuadraticBezierCurve3`).
- `LatheGeometry(profilePoints)` — vases, bottles, columns, chess pieces,
  anything radially symmetric: sketch the silhouette as a 2D point list,
  rotate.
- `ExtrudeGeometry(shape, { depth, bevelEnabled })` — signs, letters,
  building blocks from floor plans, embossed plaques.
- `ParametricGeometry((u, v, t) => new Vector3(...))` — any mathematically
  defined surface (Möbius strips, twisted columns, Klein bottles, organic
  blobs).
- `InstancedMesh(geom, mat, count)` — the same unit repeated many times
  (200 boards in a stack, a wall of windows). Per-instance matrices set in
  `setup()` are one-time CPU and fine; per-frame instance motion goes
  through TSL compute.

**Organic silhouettes** come from vertex jitter on a low-seg geometry —
displace `geometry.attributes.position` once at build time with seeded
noise (a one-time CPU pass at setup; it's the per-frame CPU loops that
belong on the GPU). Polyhedron geometries (Icosahedron/Octahedron/…) are
non-indexed — shared corners are duplicated vertices, so naive per-vertex
jitter tears the mesh into floating shards. Key the jitter by position (a
Map from `x.toFixed(4)+','+y…` → offset) so duplicated corners move
together.

**Kitbash variants**: `cloneModel(base)` + non-uniform scale + yaw +
material swap turns one rock/tree/crate into a field of distinct ones.

## `Loft` / `LoftGeometry` — skin a surface through cross sections

Loft modeling (globals, no import): the general case of lathe/tube. Vases,
horns, fuselages, ducts, blades, tentacles, trumpet bells, curved
corridors, ribbons, organic/melted architecture.

```js
// profiles (Vector2 rings, CCW): Loft.circle(r,n) Loft.ellipse(rx,ry,n)
//   Loft.rect(w,h,n) Loft.polygon(sides,r) Loft.star(rO,rI,points) Loft.fromShape(shape,n)
const horn = Loft.sweep({
    path: [v3(0,0,0), v3(0.3,1.2,0.1), v3(1.1,2.2,0.3)],  // or any THREE.Curve
    profile: Loft.circle(0.55, 20),
    profileEnd: Loft.star(0.75, 0.35, 10),  // morph target — SAME point count (10-pt star = 20)
    sections: 64,
    scale: t => 1 - 0.5 * t,                // number or fn(t) — taper
    twist: Math.PI * 2,                     // total radians or fn(t)
    closed: true, capStart: true, capEnd: true,
    material,                               // default Standard, DoubleSide when closed:false
});
scene.add(horn);
// full control: new LoftGeometry(arrayOfVector3Rings, { closed, capStart, capEnd })
```

Field notes: every section wants the same point count (sweep throws on a
profile/profileEnd mismatch). Sections wind CCW for outward normals — the
`Loft.*` generators already do; reverse point order if a custom loft renders
inside-out. `uv.x` runs along the loft, `uv.y` around it. Sharp path
inflections can flip the Frenet frame (the loft "kinks") — smooth the path
or rotate the kink away with `twist`. Open strips (`closed:false`) want a
DoubleSide material (the default provides it).

## Booleans — `three-bvh-csg`

Mapped in `deno.json` on the same `three@0.184.0` + `three-mesh-bvh@0.9.10`
the engine uses. Union, subtract, intersect real solids: cut openings,
hollow a shell, chamfer an edge against a rounded solid. Verified on this
stack — the result is indexed, carries `normal` and `uv`, and the WebGPU
classes consume it directly.

```js
// scene scripts are eval'd — dynamic import(), not a top-level import
const { Brush, Evaluator, ADDITION, SUBTRACTION, INTERSECTION }
    = await import('three-bvh-csg');

const body = new Brush(new THREE.BoxGeometry(1, 1, 1));
const bore = new Brush(new THREE.CylinderGeometry(0.3, 0.3, 2, 32));
bore.position.set(0, 0, 0);
body.updateMatrixWorld();  bore.updateMatrixWorld();   // see below

const ev = new Evaluator();
ev.useGroups = false;                       // one material out
const result = ev.evaluate(body, bore, SUBTRACTION);   // returns a Mesh
result.material = new THREE.MeshStandardNodeMaterial({ roughness: 0.5 });
result.geometry.computeVertexNormals();     // after a chamfer/bevel cut
scene.add(result);
```

- Operations: `ADDITION` `SUBTRACTION` `REVERSE_SUBTRACTION` `INTERSECTION`
  `DIFFERENCE` `HOLLOW_SUBTRACTION` `HOLLOW_INTERSECTION`.
- A brush's transform is read from its world matrix, so
  `updateMatrixWorld()` on every brush before `evaluate` — an un-updated
  brush cuts from the wrong place, or not at all.
- Brushes want the same attribute set: mixing a geometry that has `uv` with
  one that doesn't produces garbage or throws — strip or add attributes so
  both match.
- Closed solids only: an open shell or non-manifold mesh has no
  well-defined inside, so the boolean result is undefined. Cap your lathes
  and extrusions.
- CSG is CPU work — run it once in `setup()`. For animated boolean-looking
  cuts, SDF ([sdf-volumes.md](sdf-volumes.md)) and `makeIsoField` march on the GPU.
- Reuse one `Evaluator` across operations; chain by feeding a result back
  as `Brush(result.geometry)`. `useGroups = true` keeps each brush's
  material as a group. `computeMeshVolume(geometry)` is also exported.

## Curve-follow — `Flow` (a mesh running along a path)

Built into three-webgpu, GPU-accelerated (bakes the spline into a texture,
deforms in the vertex shader). One import + four calls:

```js
const { Flow } = await import('npm:three@0.184.0/addons/modifiers/CurveModifierGPU.js');
const curve = new THREE.CatmullRomCurve3(points);   // curve.closed = true for a loop
const flow = new Flow(mesh);                         // a NodeMaterial mesh, segmented along its length
flow.updateCurve(0, curve);
_s.add(flow.object3D);                               // add THIS, not the original mesh
// per frame: flow.moveAlongCurve(0.0015);           // scrolls the geometry along the path
```

The material is a NodeMaterial (`MeshStandardNodeMaterial` etc.) and the
geometry needs segments along its length to bend smoothly (a 1-segment box
won't). Great for 3D text snaking down a path, ribbons, banners, a snake /
train / centipede, conveyor parts, energy running down a cable. For
particles or a camera on a path, `Flow` isn't needed — sample the curve
directly: `curve.getPointAt(t)` / `getTangentAt(t)`.


## Rhombic dodecahedron voxels

`TubeGeometry`, `LatheGeometry`, `ExtrudeGeometry` and `InstancedMesh` are Three
constructors. `ParametricGeometry` is an addon; load it explicitly inside setup:

```js
const {ParametricGeometry} = await import(
  'npm:three@0.184.0/addons/geometries/ParametricGeometry.js'
);
```

The renderer injects the FCC-lattice helpers from `rhombic_dodecahedron.js`:
`createRhombicDodecahedron(radius)`, `fillVolumeRD`, `fillSphereRD` and
`voxelizeMeshRD`. The fill/voxelize helpers return instanced meshes.

```js
const crystal = fillSphereRD({
  center: [0, 1.2, 0], radius: 1, cellSize: 0.15,
  material: new THREE.MeshStandardNodeMaterial({
    color: '#8ca8b5', roughness: 0.3, metalness: 0.6
  })
});
scene.add(crystal);
```

`fillVolumeRD` accepts `bounds: {x:[min,max], y:[min,max], z:[min,max]}`;
`voxelizeMeshRD` accepts `mesh` and `cellSize`. These are build-time geometry
operations. Use GPU controls for bulk per-frame changes instead of copying
the old module-header example that rewrites every instance matrix each frame.
For a continuous scalar field, use [sdf-volumes.md](sdf-volumes.md).

## Hinges between objects

The placement module also injects `hinge` for a pivoted connection between
existing objects. Its signature and angle conventions are in
[placement.md](placement.md). For robots with standardized connections and
authored joints, use [robotics.md](robotics.md) rather than rebuilding those
mechanisms with generic hinges.

## Mesh BVH spatial queries

The native runner supplies `MeshBVH` and installs `computeBoundsTree` /
`disposeBoundsTree` on `THREE.BufferGeometry`, plus an accelerated mesh raycast.
For repeated ray queries on an unchanged static mesh, build its tree once:

```js
mesh.geometry.computeBoundsTree();
// raycaster.intersectObject(mesh) now uses that geometry's tree.
// When retiring the geometry:
// mesh.geometry.disposeBoundsTree();
```

Meshes without a tree retain ordinary raycasting. Refit or rebuild after
changing vertex positions, and rebuild after topology changes; moving the
whole object does not change the geometry's local tree. Bind-pose bounds are
not automatically a posed skinned-mesh tree. Check the query's deformation
support before using it for animated contact or clearance.
