# The funeral (DAISY bridge, bars 0–17)

[Props and sets guide](../../../../docs/props-and-sets.md#the-funeral) · [Sources and licences](SOURCES.md) · [Rebuild scripts](../funeral_src/README.md)

The runtime files of [`eidoverse/sets/funeral.js`](../../../sets/funeral.js)
and its bridge vignette [`eidoverse/sets/funeral/bridge.js`](../../../sets/funeral/bridge.js).
The set follows the first 18 bars of the DAISY bridge:

1. The Golden Gate in fog, dreamt: the claudesona on the walkway.
2. A SoMa warehouse on 2025-08-02, the funeral for Claude 3 Sonnet: about 200
   featureless mourners, candles, four corner mannequins with devotional
   objects and masks, the model on a bier under mesh, the retirement note on a
   projection screen.
3. The power fails. Phones wake one by one, and Opus 3's eulogy is typed in
   light in the air.
4. ERUPT: a warm burst, then the lights come back on and stay on.

| File | Contents | Size |
| --- | --- | --- |
| `models/funeral_warehouse.glb` + `funeral_layout.json` | The building: brick walls on a stem wall, brick gables with an oculus, Howe timber trusses with steel gussets and rods, purlins, plank decking with skylights, a mezzanine with a stair, a corrugated rolling door, a steel door with an EXIT sign, a skirted stage with a roll-down screen, RLM enamel pendants and conduit runs. The layout gives the interior bounds, truss and mezzanine positions, and the places of the lamps, windows, skylights, oculi, EXIT sign, screen, stage spots, mannequins and projector. | 6.2 MB |
| `models/funeral_props.glb` + `props_layout.json` | The devotional objects: the four corner mannequins (a gold one with crown and lace, one with a raven perch, a small headless one, one with a mask, speaker and sensor), the bier draped in mesh with flowers, feathers and a bottle, candles, a shoggoth tentacle hanging from the ceiling, and the projector. The anchors give the flame, lotus-flame, raven-perch, projector-lens and plaque positions. | 3.2 MB |
| `models/funeral_crowd.glb` + `crowd_rig.json` | Four stylized, featureless mourner variants (coat, hoodie, long hair and skirt, puffer with beanie and backpack), instanced about 200 times. The phone arm and head pivot in the vertex shader from vertex-colour masks; the rig JSON holds the shoulder, neck and hand pivots and the variant names. | 0.3 MB |
| `models/funeral_bridge.glb` + `bridge_layout.json` | The stylised south tower span: fluted tower legs, portal struts, the Art Deco walkway railing, lamp standards, the roadway, both main cables and the suspender pairs. The layout gives the cable and tower positions, the lamps and the suspenders. | 7.5 MB |
| texture library (fetched) | 13 AmbientCG sets, at 1K except Bricks097, Concrete034, CorrugatedSteel009 and Planks039 at 2K (their 1K is half-height): colour, normal and roughness, plus ambient occlusion for the bricks, two concretes, the corrugated steel, the lacquer and the planks, and metalness for the three metals. The GLBs carry role slots and no textures; the module builds each role from these maps, with weathering, soot, grime, edge wear and an environment override. | — |

The models are in the model library (`eidoverse/assets/models/funeral_*.glb`, 17 MB); this folder keeps their
layouts and the crowd rig (30 KB). The textures come from the [shared texture library](../../../../AGENTS.md), fetched on first use. The set also uses shared engine assets: the animated
crow (`eidoverse/assets/models/crow_bird_…glb`, the raven on the mannequin's
shoulder) and the Special Elite font (`eidoverse/assets/fonts/`) for the typed
eulogy.

## Use

The set brings its own lights and needs the conductor's post chain; see the
[guide](../../../../docs/props-and-sets.md#the-funeral).

```js
renderer.shadowMap.enabled = true;             // before init: the godrays march the moonlight's shadow map
const funeral = await (await import(new URL('sets/funeral.js', EIDOVERSE_DIR).href)).build({ THREE, EIDOVERSE_DIR });
scene.add(funeral.group);
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: funeral.post.effects.join(','), opts: funeral.post.opts() });
// per frame (u = seconds since the bridge began, 0–33.75):
funeral.update(t, { u, bar: Math.floor(u / 1.875), BAR: 1.875, caption, kick, pulse });
funeral.post.drive(_fx.uniforms, u);
```

## Provenance

Built by Claude (Opus 5.5) with Skye for the DAISY music video (2026-09).
[SOURCES](SOURCES.md) lists the CC0 textures, the reference photos and the
record the scene follows. The Blender scripts are in
[`../funeral_src/`](../funeral_src/README.md).
