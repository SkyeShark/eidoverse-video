# 1896-pattern tandem bicycle

[Props and sets guide](../../../../tools-guides/props-and-sets.md#the-1896-tandem) · [Sources and licences](SOURCES.md) · [Rebuild scripts](../tandem_1896_src/README.md) · [Tool inventory](../../../../docs/TOOLS.md)

"A bicycle built for two": a lugged 1890s safety tandem, built for the DAISY
music video's finale. [`eidoverse/props/tandem.js`](../../../props/tandem.js)
loads `tandem.glb` from this folder. It then drives the bike: rolling wheels
with spoke motion blur, two block chains running round their sprockets on the
GPU, turning cranks, pedals and steering. The same module poses a VRM rider
with two-bone IK and builds a Utah-teapot stoker for the rear seat.

| File | Contents |
| --- | --- |
| `tandem.glb` (19.3 MB) | 22 meshes, 235k triangles and 8 materials. The frame has cast lugs, brackets and a crown. The wheels are tangent-laced with nipples. It has daisy-spider chainrings, rat-trap pedals, a 1" block chain, sprung Brooks-pattern saddles, a spoon brake and a bell. The layered PBR is baked into 26 embedded maps: enamel and gold lining, nickel, gum tyres, leather, wooden rims, cork grips, chain and spokes, with colour up to 4096² and clearcoat. |

The module needs the GLB's named pivot empties: `steer`, `wheel_*`,
`crank_*`, `pedal_*`, `seat_*` and `grip_*`. It also reads the layout and the
chain belts from the root's `daisy_tandem` extras. Rebuild the GLB with its
own scripts rather than editing it in a DCC, so those names and extras
survive.

## Use

```js
// In setup()
globalThis._allowManualLocomotion = true;          // a VRM riding the bike is carried by a vehicle
const T = await import(new URL('props/tandem.js', EIDOVERSE_DIR).href);
const bike = await T.build(THREE);                 // reads tandem.glb from this folder
const pot = await T.buildTeapotRider(THREE);
pot.mount(bike);
scene.add(bike.group);
T.poseRider(vrm, 0, { bike, t: 0 });               // vrm: a loaded VRM (tuned for claude_suit.vrm), seated at 0.87

// per frame
const st = bike.update(t, { speed: 5.9 });         // m/s; returns { distance, wheelAngle, crankAngle, speed }
bike.group.position.x = x0 + st.distance;          // the scene owns the root transform (+X = travel)
T.poseRider(vrm, st.crankAngle, { bike, t });
pot.update(t, st.crankAngle);
```

The bike frame uses +X for the direction of travel, +Y up and +Z for the
drive (right) side. The wheels rest on `y = 0`, and the origin is on the
ground between the hubs. The built group measures 2.40 × 1.16 × 0.58 m.
5.9 m/s is 64 rpm at the cranks, one turn every two beats at 128 BPM. See the
[guide](../../../../tools-guides/props-and-sets.md#the-1896-tandem) for the
rider rig, costs and limitations.

## Provenance

Modelled, baked and coded by Claude (Opus 5.5) with Skye for the DAISY music
video (2026-09). The [sources](SOURCES.md) list the CC0 scans baked into the
maps and the period references.
