# Props and sets from the DAISY and UNKNOWN FORCE films

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition. The library holds finished props and
sets from the DAISY and UNKNOWN FORCE music videos. **Their modules are not
yet ported to Blender**: each one builds, animates and lights its piece in
the WebGPU engine (`eidoverse/props/`, `eidoverse/sets/`), and those modules
are the port's source. What the Blender edition already has from them is
their assets, which it reuses as they are, and the placement and surface
tools their ports will stand on.

| Piece | WebGPU module (the port's source) | Assets (shared) | In Blender today |
| --- | --- | --- | --- |
| Eight historical voice machines, 1939–2001 | [`props/voice_machines/`](../eidoverse/props/voice_machines/index.js) | [`models/voice_machines/`](../eidoverse/assets/models/voice_machines/README.md), builders in `models/voice_machines_src/` | the GLBs import (era 2 with their baked maps; era 1 untextured) |
| An 1896-pattern tandem bicycle, rider rig, teapot stoker | [`props/tandem.js`](../eidoverse/props/tandem.js) | [`models/tandem_1896/`](../eidoverse/assets/models/tandem_1896/README.md), builder `tandem_1896_src/build_tandem.py` | the GLB imports with its maps, static |
| The corner and the march | [`sets/corner.js`](../eidoverse/sets/corner.js) | [`sets/corner/`](../eidoverse/assets/sets/corner/README.md) + `models/corner_*.glb`, builders in `sets/corner_src/` | the GLBs import with their maps |
| The funeral (a bridge in fog, a warehouse vigil) | [`sets/funeral.js`](../eidoverse/sets/funeral.js) + [`funeral/bridge.js`](../eidoverse/sets/funeral/bridge.js) | [`sets/funeral/`](../eidoverse/assets/sets/funeral/README.md) + `models/funeral_*.glb`, `sets/funeral_src/` | the GLBs import, untextured (their role materials were applied at runtime) |
| The ocean of faces (a headland at night) | [`sets/ocean.js`](../eidoverse/sets/ocean.js) + [`ocean/*.js`](../eidoverse/sets/ocean/) | [`sets/ocean/`](../eidoverse/assets/sets/ocean/README.md) + `models/ocean_*.glb`, `sets/ocean_src/` | the GLBs import (the house with its maps) |
| UNKNOWN FORCE: megacity and well, quiet room, showroom, gold corridor, news, race, bin | [`sets/unknown_force/`](../eidoverse/sets/unknown_force/README.md) (14 modules) | none of their own: geometry built in code, CC0 maps fetched ([sources](../eidoverse/sets/unknown_force/SOURCES.md)) | nothing yet |

Every asset folder has a README and a SOURCES file (licences, provenance).
The `<name>_src/` folders hold the Blender scripts that built the assets:
they already are Blender, and they run headless through `run_blender.sh`
(see the [Blender guide](blender.md)); several need CC0 source sets that are
not shipped, and some bake with Cycles on the GPU.

## Using a piece in Blender today

Import the GLB, stamp it as a loaded asset (so `layer_surface` and the
texel tools never rewrite its authored UVs), wrap it under one root, and
seat it with the [placement helpers](placement.md). glTF's front is −Y in
Blender, which is the edition's front.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.placement import place_on, face_toward

def import_glb(path, name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for o in set(bpy.data.objects) - before:
        o['eido_loaded_asset'] = True
        if o.parent is None:
            o.parent = root
    root['eido_loaded_asset'] = True
    return root

mac = import_glb('<repo>/eidoverse/assets/models/voice_machines/mac1984.glb', 'mac1984')
place_on(mac, desk, xy='centered')        # bounds bottom on the desk top
face_toward(mac, camera, forward='-y')    # its screen to the lens
```

What that gives is the static model with the materials the importer builds
from the GLB: no screen text, no power-on, no moving parts, and for the era-1
machines (voder, mainframe, teletype) no surface at all, since their looks
were layered at runtime from AmbientCG sets, masks and canvas decals.

## The port plan

**The set contract stays**, in Blender terms: `build(ctx)` returns a dict
with `group` (a root Empty, or a collection), `mark` / `mark_at(u)` (a
set-local position and yaw), `camera(u, st)` or `cams` (set-local
`pos`, `target` and a vertical `fov`), `update(t, st)`, `parts` and `focal`,
all in set-local metres, Blender axes. Systems from other families (the sky,
`create_flora`, `make_seed_tree`, particles, screens, the post chain, VRM
performers) come in through `ctx` as callables, so the set modules stay
self-contained. A scene keys `update` into the timeline (CONSTANT keys at
cuts) instead of calling it per frame, so renders seek and stills work.

**The props** become .blend builds:
1. Rerun each `_src` builder into a .blend whose layered materials EEVEE
   renders live (the GLB import is the first step and works now).
2. `update(t, state)` becomes keyed custom properties on the prop's root
   with drivers: `power` and `voice` drive emission, the tandem's `distance`
   drives its wheels and cranks.
3. Screen and paper text is drawn with `blf` into an image (this works
   headless); text that changes per frame is saved as an image sequence.
4. The tandem's chain becomes a Curve + Array along its loop with a driven
   offset; its spoke smear becomes EEVEE motion blur. `poseRider` is VRM IK,
   shared with the characters family.

**The sets**: what is WebGPU-specific, and where it goes.

| WebGPU | Blender |
|---|---|
| geometry built in code | bmesh / numpy builders, [loft](geometry.md), the Boolean modifier |
| TSL colour, emissive and position nodes | shader nodes driven by a keyed time property; vertex animation in Geometry Nodes or shape keys |
| per-material `envNode` overrides | one dark World per set scene, the set's own lights, sphere and volume light probes |
| `Reflector`, wet mirror streets | a planar light probe + EEVEE raytracing |
| fog, godrays | volumes with volumetric shadows |
| steam | volume domains |
| canvas text, CPU mips | `blf` into images |
| `update(t, st)` | keys, CONSTANT at cuts |
| `cams` | cameras with vertical FOV, markers bound to cameras for cuts |
| `land.js` (a coast heightfield) | a second heightfield beside `make_terrain` |
| `sea.js` Gerstner swells in the vertex stage | a Geometry Nodes or Ocean-modifier sea |

The DAISY sets were staged at 128 BPM (one bar 1.875 s) and UNKNOWN FORCE
at 92.90 BPM; their beats, marks and cameras are keyed to those clocks and
framed for the claudesona at scale 0.87 (face about 1.33 m). The WebGPU
sections of this guide's previous edition (in git history) document each
piece's options, beats and costs, and stay the reference for the port.

## Verify

Import a piece in a short headless probe, place it, light it with a test
fixture, render a still through the shared GPU slot, and look at it: the
pattern of `blender/tests/terrain/test_placement.py`, which imports the
crate GLBs this way.

## Not yet ported

- Voice machines: `MACHINES`, `buildMachine`, `loadMachine`, each machine's
  `build` / `update` / `parts` / `dispose`, the era-1 layered materials and
  decals, the era-2 screens (`setText`), the Voder's `pattern(t)`, the
  mainframe's integrated `tapeSpeed`.
- The tandem: `build`, `buildTeapotRider`, `poseRider`, `update` (speed,
  distance, steer, shutter), the walked chain, the spoke smear.
- The corner (room and camp, march, signs, spark, `flowerTarget`), the
  funeral (vignette, vigil, phones, eulogy, `BEATS`, its post chain) and the
  ocean (`land.js`, `sea.js`, the house, pages, robot, human of light, the
  daisies' sway, `perform`, `SKY`).
- The UNKNOWN FORCE sets: city and citykit, hole, quiet room, showroom,
  corridor and `cn_lib`, news, race, bin and its pages, `interiors_lib`.

(The model kit is ported: `load_kit` in [geometry.md](geometry.md#kits--load_kit)
pulls the sets' multi-part GLBs apart by name, family or island.)
