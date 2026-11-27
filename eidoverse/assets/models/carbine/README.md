# Carbine

[Props and sets guide](../../../../tools-guides/props-and-sets.md#the-carbine) · [Sources and licences](SOURCES.md) · [How it was made](../carbine_src/README.md) · [Tool inventory](../../../../docs/TOOLS.md)

An M4A1-pattern carbine built as a hard-surface game asset for the SAME SEED
film: a 499 k-triangle high drawn again as a low of the same 64 parts, the
high baked onto the low on the GPU, and one layered material on the bakes.
Function markings only (the rail's numbers, the selector's SAFE / SEMI /
AUTO): no maker's marks, no serial.
[`eidoverse/props/carbine.js`](../../../props/carbine.js) loads it and
rebuilds the material in TSL
([`eidoverse/layered_material.js`](../../../layered_material.js)).

| File | Contents |
| --- | --- |
| `carbine.glb` (1.2 MB) | The low: 64 parts, 21,020 triangles, one UV set, MikkTSpace tangents; every part at identity in the carbine's space; the materials `carbine.layered` and `carbine.lens_coated` by name. |
| `carbine_normal.png` (2.4 MB) | The baked normal map, 4096², OpenGL (+Y), MikkTSpace. |
| `carbine_masks_a.png` (11.1 MB) | R ambient occlusion (30 mm), G cavity (2 mm), B fine curvature. |
| `carbine_masks_b.png` (4.3 MB) | R exposed-edge nearness (4 mm), G broad curvature, B inside-corner nearness (8 mm). |
| `carbine_id.png` (0.1 MB) | The substrate ID of every texel × 16 (read unfiltered). |
| `carbine_marks.png`, `carbine_relief.png` | The markings laid at real size; where the grip's moulded chequering and the backstrap's ribs cut in. |
| `carbine_layered.json` | The look's tables: the 13 substrates by ID, the hands' soft boxes, the knocks' and stains' ramps (millimetres in the carbine's Blender axes), the CC0 photographs the stack reads. |

The maps are 4096² because the close views need them: the selector's lettering
is about 3 mm tall and the bake holds 4.9 texels a millimetre (58 % of the set
is filled).

## Use

```js
// In setup()
const C = await import(new URL('props/carbine.js', EIDOVERSE_DIR).href);
const rifle = await C.build(THREE, { condition: { wear: 1.0, polish: 1.0, dust: 1.0, grime: 1.0 } });
scene.add(rifle.group);                  // metres: +X to the muzzle, +Y up, +Z the carbine's right
rifle.parts.magazine.visible = false;    // the 64 parts by name
rifle.dispose();
```

The first build fetches the material's six CC0 photographs into
`eidoverse/assets/cache/`. The worked example is
[`eidoverse/examples/carbine/`](../../../examples/carbine/scene.js).
