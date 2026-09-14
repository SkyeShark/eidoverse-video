# Terrain and surface materials

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Heightfields, material layers and relief help shape the surfaces in a scene.
Use the tools that fit the intended terrain, manufacture and wear. Foliage
has its own [vegetation guide](vegetation.md).

## `makeTerrain` — procedural heightfield ground

Multi-texture blending (height + slope + noise, baked as vertex paint) in
one call. Use a heightfield for uneven ground, or a plane when the intended
surface is flat:

```js
const terrain = makeTerrain({ size: 80, amplitude: 3, seed: 7, flatRadius: 8,
    layers: [{ map: grass, repeat: 18 }, { map: dirt, repeat: 14 }, { map: rock, repeat: 10 }] });
scene.add(terrain.mesh);
```

`terrain.heightAt(x, z)` gives exact ground height anywhere; `flatRadius`
keeps a level clearing for staging the action.


Foliage, plant species, wind and SeedThree are documented in
[vegetation.md](vegetation.md).

## `layerSurface` — making built geometry look built

`layerSurface` combines density normalization and layered surface masks for
new geometry. Use it when the piece benefits from form-following wear, dust
or material variation. A clean or uniformly coated surface may need less.
Loaded assets already carry authored maps and UVs; preserve those.

```js
globalThis.layerSurface(myMeshes, {
    metresPerTile: 1.15,                 // one texture tile per 1.15 m, on everything
    grunge: { scale: 0.55, seed: 7 },
    layers: [
        { mask: 'cavity', scale: 0.75, color: 0x2b2419, roughness: 1.0, amount: 0.9, range: [0.15, 0.72], grunge: 0.35 },
        { mask: 'edges',  color: 0xc9bda0, roughness: 0.62, amount: 0.6, range: [0.20, 0.72] },
        { mask: 'up',     color: 0x8a7859, amount: 0.38, power: 3, grunge: 0.8 },
        { mask: 'below',  y: WATERLINE, fade: 0.5, color: 0x11423c, roughness: 0.55, amount: 0.85 },
    ],
});
```

**Masks** (each remapped through `range: [a, b]`, scaled by `amount`,
optionally broken up by `grunge: 0..1`):

| mask | driven by | use it for |
|---|---|---|
| `cavity` | baked raycast AO | grime, moss, soot — the workhorse |
| `crease` | concave curvature | sharp dirt lines in inside corners |
| `edges` | convex curvature | polish, chipping, bleached exposure on chamfers |
| `up` | `normalWorld.y^power` | dust, silt, ash, snow |
| `slope` | `1 - abs(normalWorld.y)` | runoff streaking on vertical faces |
| `below` / `above` | world Y, `y` + `fade` | waterlines, tide marks, buried bases |
| `grunge` | triplanar tiling fbm | breakup on its own |

**These tools are for geometry you built, and they refuse fetched assets.**
GLBs, VRMs and kit parts carry an authored UV unwrap corresponding 1:1 to
their own texture (or a shared atlas/trim sheet) — rescaling those UVs makes
every island sample outside its region and the model comes out as confetti.
`GLTFLoader` output is stamped `userData._loadedAsset`; skinned meshes,
morph-target meshes and MToon materials are refused on top of that. Skipped
meshes are named in the log. A mixed scene root can still contain eligible
procedural meshes, so pass the intended subset rather than assuming the
whole scene will be skipped.

- **`normalizeTexelDensity(meshes, { metresPerTile })`** measures each
  mesh's real UV-per-metre (median over triangles, via `matrixWorld`, so a
  kitbashed scaled clone is measured at its apparent size) and scales the
  existing `uv` to a common target, keeping each constructor's UV islands
  (a world-space reprojection would throw away the bevel/cap layouts
  `ExtrudeGeometry`/CSG generate and seam on anything not axis-aligned).
  It warns when a material's texture `repeat` isn't 1, because that
  multiplies on top and undoes the work.
- **The curvature masks are per-pixel TSL — nothing is baked.** `curv`
  comes from screen-space derivatives of the world normal normalized to
  1/metres, so the mask doesn't swim as the camera dollies. Give each layer
  a `scale` in metres for the feature size it answers to (0.6 broad
  hollow, 0.05 tight crease). Derivatives are taken within a triangle, so
  a bevelled edge gives a clean gradient while a hard boolean corner with
  split normals gives only a thin line — model the fillet
  (`bevelEnabled: true`) where dirt should collect.
- **`makeLayeredMaterial({ base, layers, grunge })`** gives the material
  without the baking; **`grungeTexture(size, seed)`** is the
  seamlessly-tiling fbm on its own.
- `normalizeTexelDensity` is geometry authoring — one attribute write at
  build time, same class as `computeVertexNormals()`. Call it after the
  group is positioned (the density measurement reads `matrixWorld`).

## `ProceduralMaterials` — generated PBR surfaces

For surfaces without a fetched-texture match, and for layering wear onto
clean bases:
- Generators: `scratches`, `smudges`, `noise`, `voronoi`, `patches`,
  `pores`, `weave`, `grain`
- Factories: `createPaintedMetal({ color, scratches: true, smudges: true })`,
  `createRubber()`, `createSkin({ color, patches: { patchColor, shape:
  'blob' } })`, `createScaly()`, `createFabric()`, `createWornMetal()`
- Compositing: `composite(texA, texB, 'multiply')` layers procedural detail
  onto Poly Haven base textures so surfaces look used rather than
  catalog-fresh.
- All factories output NodeMaterial with basecolor + roughness + metalness
  + normal. Uniform properties can use constant values; map count is not a
  measure of surface quality.

## SPOM — silhouette parallax relief

Ray-march a height map to give a surface real interior depth *and* an
outline that follows the relief, so the mesh edge shows the bumps in
profile instead of a flat polygon line. Backed by `parallax_occlusion.js`
(`parallaxOcclusionUV`). Two helpers: **`createReliefColumn`** (curved
surfaces — the easy, correct path) and **`createParallaxMaterial`** (flat
surfaces + full control). The height field is `fetch_texture`'s
**displacement** map. One of the most under-used surface showpieces.

**First decide flat vs curved — this is the whole game.** Plain POM only
fakes interior depth; the outline still ends at the polygon edge. The
"silhouette" reads at the mesh edge against the background at a grazing
angle:
- **Flat** (wall, plate, floor, tread): the outline crenellates along the
  tile trim. `createParallaxMaterial({ silhouette: true })`.
- **Curved** (column, pipe, sphere): the relief must overhang the round
  base outline, which takes three things together — (1)
  `curvedSilhouette: true` + per-axis `curvature`, (2) `inflate` = the
  relief peak in world units (a `positionNode` pushing the shell past the
  base outline), (3) a plain core just inside to fill where the shell
  clips. Missing any one renders as plain interior POM (the classic "it
  looks flat"). **`createReliefColumn` wires all three.**

```js
// CURVED — a column/pipe whose flanges + bolts overhang the round outline.
const col = globalThis.createReliefColumn({
    heightMap, albedoMap,              // THREE.Texture; height in .r, WHITE = peak
    radius: 0.5, height: 3.2, aroundTiles: 3,   // relief tiles around the barrel
    depthScale: 0.15,                  // relief depth; reliefFactor:0.7 tames thin pipes
    lightDir: KEY_DIR,                 // WORLD dir TOWARD the key light (self-shadow)
    roughness: 0.55, metalness: 0.18,  // + any MeshStandardNodeMaterial opts
});
scene.add(col);                        // rotate the Group to lay a pipe on its side

// FLAT — a wall/plate that carves its outline along the relief trim.
const geo = new THREE.PlaneGeometry(9, 4.2);  geo.computeTangents();  // tangent-space march
const wall = new THREE.Mesh(geo, globalThis.createParallaxMaterial({
    heightMap, albedoMap,              // heightMap IS fetch_texture's displacement map
    depthScale: 0.05,                  // SMALL for a whole-face tile; ≲0.06 or it shears
    minViewZ: 0.14,                    // bounds grazing-ray smear (raise for big walls)
    silhouette: true,                  // false = interior POM only (e.g. a floor)
    lightDir: KEY_DIR,
    roughness: 0.7, metalness: 0.15,
}));
wall.castShadow = wall.receiveShadow = true;  scene.add(wall);
```

The material is a real lit `MeshStandardNodeMaterial` — the relief is lit,
self-shadowed (a second march toward `lightDir`), and its shading normal
derives from the height field by default (`heightNormal: true`), so it
shades like geometry with no normal map needed. `maskShadowNode` makes cast
shadows follow the carved outline. `computeTangents()` matters (POM marches
in tangent space) — as a safety net, the helper audits at first render: a
POM mesh with no tangents gets them auto-computed (the warning names the
mesh); when they can't be computed (merged non-indexed geometry) the relief
shading normal is disabled instead of miscompiling into an invisible mesh
(`THREE.Node: Recursion detected` on a POM surface means exactly this). It
also warns on `curvedSilhouette` without `inflate` and other footguns — the
warnings name the exact fix. `MeshBasicNodeMaterial` renders all-black
under the march; the Standard-based material is the path.

**Evaluating a SPOM render:** pull the camera back so the whole object, its
silhouette against the background, and its floor shadow are all in frame;
put it in a lit scene with a real floor; orbit so the silhouette sweeps. A
zoomed-in, barely-moving shot of a dark panel can't show whether the
silhouette works. On a curved surface, the relief peaks should visibly
bulge past the round base outline.

Field notes: the silhouette reads as bumpy where the relief reaches the
UV-tile edge — relief inset from the boundary trims a clean strip.
Discarding on a closed box reveals the culled interior (fine on exterior
walls; see-through on a lone box). Raw PolyHaven `_disp` maps are
low-contrast mid-gray — contrast-stretch them or the carve is invisible,
and floor the stretch (map to ~[0.15, 1]; pure-black wells = degenerate
full-depth rays). `depthScale` is in UV-tile units: small (≲0.06) for a
whole-face tile; with world-projected metre UVs pass `depthScale = metres ×
uvScale`. Debug ladder: `debugMarch: true` paints the raw march unlit,
`debugSilhouette: true` paints discards magenta.

For custom relief meshes, `checkReliefGeometry(geometry, label)` reports
whether the tangent attribute exists and returns a boolean. It is an early
setup check, not a general topology or bake validator. `computeTangents()`
requires indexed geometry with normals and UVs; inspect the silhouette and
shading in addition to the helper's result.
