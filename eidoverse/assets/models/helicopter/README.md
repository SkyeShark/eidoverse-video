# Helicopter

[Props and sets guide](../../../../docs/props-and-sets.md#the-helicopter) · [Sources and licences](SOURCES.md) · [How it was made](../helicopter_src/README.md)

A UH-60-pattern helicopter built for the SAME SEED film as a measured high of
290 parts, rendered as its high: its wear and dust masks stored on its own
vertices, one layer stack reading them, its rivets, seams, fasteners and
stencils drawn at real size. Function stencils only: no service title, no
serial, no unit's mark. [`eidoverse/props/helicopter.js`](../../../props/helicopter.js)
loads it and makes its materials in TSL.

| File | Contents |
| --- | --- |
| `helicopter.glb` (19.8 MB) | The whole high: 290 parts, 2,712,455 triangles, 1,577,878 vertices; per vertex `_MASKS` (R the nearness of an exposed arris, G of an inside corner, B the openness near, A the openness far, 8-bit) and on the blades `_BLADE` (R across the chord from the leading edge, G along the span); the Empties `main_rotor` (under `mast_tilt`) and `tail_rotor` (under `tail_rotor_cant`); every part's material named for its role. Positions are float32 in the aircraft's metres; the file is packed with `EXT_meshopt_compression` (82 MB unpacked). |
| `skin_side.png` | Drawn side-on at 2.5 mm a pixel over x −4.7 … 9.5 m, z −0.5 … 3.4 m: R rivet heads along every frame and stringer, G seams and shut lines, B flush fasteners. |
| `marks_left.png`, `marks_right.png` | The stencils as they read from each side (the right one drawn mirrored). |
| `decals.json` | The pictures' rectangle in the aircraft's millimetres. |

The full high is what ships: packed it is 20 MB and its 2.7 M triangles draw
in about 6 ms more than an empty studio frame at 1920 × 1080 on an RTX 5090
Laptop GPU, so no lower-detail version was made.

## Use

```js
// In setup()
const H = await import(new URL('props/helicopter.js', EIDOVERSE_DIR).href);
const heli = await H.build(THREE);           // its own GLTFLoader with three's MeshoptDecoder
scene.add(heli.group);                       // metres: +X aft of the mast, +Y up, +Z the aircraft's left
// per frame
heli.update(t);                              // the rotors: 258 rpm (counter-clockwise from above) and 1190 rpm
```

To load the GLB with a loader of your own, give it the decoder:
`loader.setMeshoptDecoder(MeshoptDecoder)` from
`npm:three@0.184.0/addons/libs/meshopt_decoder.module.js`. The worked examples
are [`studio.js`](../../../examples/helicopter/studio.js) and
[`flight.js`](../../../examples/helicopter/flight.js).
