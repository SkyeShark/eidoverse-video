# Creature Creator v2 (work in progress)

> **WIP / incomplete.** This is an early public drop of a creator that is still being built. The finished pieces load
> and render today; the procedural tool for remixing NEW characters is not working yet. Expect paths, file names and
> calls to change between drops.

Creature Creator v2 makes **high-fidelity PBR creatures and humans**: realistic, rigged, game-ready models with baked
texture sets and runtime materials. It lives beside the toolkit's stylized low-poly creature creator
(`makeCreature` in `eidoverse/creature_builder.js`), which stays the quick way to get a cartoon creature; v2 is the
realistic one.

It has two halves:

- **The forge** (`forge/`, Python): procedural anatomy as signed-distance fields, a hand-authored quad low-poly mesh, a
  voxel high-poly, baked maps (normal, occlusion, curvature), layered procedural materials, a rig, and glTF export.
  Species, props, garments, hair and cyborg parts each have their own modules (`forge/species/`, `forge/props/`,
  `forge/garments/`, `forge/groom/`, `forge/cyborg*.py`).
- **The runtime** (`runtime/`, JavaScript for the three.js engine): loads the forge's glb files, builds their materials
  (TSL shaders over the baked maps: skin, cuticle, eyes, fur and hair cards, growths, metal parts) and moves them with
  procedural motion. `runtime/bestiary.js` installs `globalThis.Bestiary`.

Comments in the code cite where numbers came from. Comments tagged "study T / G / R / M / B" cite measurements we took
on shipped commercial games for calibration: numbers only, no game data is in this repository. Citations such as
"AG 05.8" or "craft guide 10.14" refer to numbered items of a private craft guide that is not part of this repository.

## What works today

| Kind | What loads | How |
|---|---|---|
| Creatures | octopus; stag beetle with four variants (crystal, ice, cyborg, cyborg + crystal); axolotl | `Bestiary.create({ species, variant })` |
| Humans | a base woman and a base man (VRM 1.0, 116 joints), four outfits each, robot hands, 15 hair styles | `Bestiary.create({ species: 'human', sex, outfit, hand, hair })` |
| Accessories | top hat, round glasses, peaked cap, monocle (in the runtime's table); more hats and soft props as files | `creature.wear(await Bestiary.accessory(name[, { path }]))` |
| Coat | a shaggy fur coat for the octopus | `Bestiary.create({ species: 'octopus', coat: { path } })` |
| Remixes | 48 pre-resolved random remixes of the octopus | `Bestiary.random(seed)` |
| Grafted creatures | six pre-built crosses: an axolotl with a stag beetle's fore legs, with an octopus arm for a tail, with a mechanical tentacle for a tail, with octopus eyes; an octopus with a regenerated arm, with a beetle leg | `Bestiary.create({ species: 'axolotl', path: '<the cross>.glb' })` (the files are listed under "Grafted creatures" below) |
| Old calls | `makeCreature` options mapped onto the realistic bases where a base exists | `Bestiary.fromMakeCreature(opts)`, `Bestiary.keyReport(opts)` |
| Aletheia and Aporia | WIP pieces (head with a working mouth, jumpsuits, hardware and belt, boots, hard-surface arms, tentacles, eye displays, hair) as plain glb files | the engine's `GLTFLoader` (not wired into `create()` yet) |

**What does not work yet:**

- **Remixing new characters is only partly there.** The remix machinery (below) is in the kit and six pre-built crosses
  load, but a NEW cross still needs its part forged offline by the forge, whose inputs are not in the repository; no
  tool yet turns a recipe into a new creature (another creature's limbs, heads or skins on a base, crossbreeds,
  mutants) on its own. `Bestiary.random(seed)` picks from a fixed pool of 48 recipes resolved offline for the octopus.
- **Only these bases are shipped.** Other creatures named in the code (wolf, deer, hawk, lobster, tarantula and more) are
  in progress and their files are not in this drop; `makeCreature` stances without a realistic base fall back to the
  old creator (`Bestiary.fromMakeCreature` says so in its key report).
- **The forge cannot rebuild the assets from a fresh clone.** Its inputs (downloaded datasets such as GNM and MakeHuman,
  reference photographs, cached intermediate stages) are not in the repository. The code is shipped to read and to
  re-run once you fetch such inputs yourself; the shipped glb files are its outputs.
- **Aletheia's and Aporia's pieces are not assembled into a character** and are not loaded by `create()`.
- The smile and frown masks and the bow tie carry their fit data, but no shipped creature has the face or neck seat
  they need yet (`wear()` says so); load them as files. The other delivered hats and the beanie seat on the octopus
  through `wear()` today.

## Loading an asset in a scene

Paths are relative to the repository root (the engine's working directory). In a scene script's `setup()`:

```js
await import(new URL('bestiary/runtime/bestiary.js', EIDOVERSE_DIR).href);     // installs globalThis.Bestiary
console.log(Bestiary.species);                       // ['octopus', 'stag_beetle', 'axolotl', 'human', ...]

const oct = await Bestiary.create({ species: 'octopus', seed: 3 });
scene.add(oct.group);                                // animates itself; { auto: false } + oct.update(t) to drive it
oct.setDisplay({ dark: 0.8, spots: 1 });             // the octopus's colour-change displays (0..1 each)
oct.wear(await Bestiary.accessory('top_hat'));       // runtime props: top_hat, round_glasses, peaked_cap, monocle

const beetle = await Bestiary.create({ species: 'stag_beetle', variant: 'crystal', size: 'hero' });
const woman = await Bestiary.create({ species: 'human', sex: 'F', outfit: 'tee', hair: 'bob' });
const man = await Bestiary.create({ species: 'human', sex: 'M', outfit: 'shirt_ls_tie', hand: 'robot' });
woman.walkTo(2, 1); woman.say('Hello');

// a delivered hat that is not in the runtime's table yet: by its file
const trilby = await Bestiary.accessory('trilby', { path: 'work/bestiary/accessories_b5/tophat/trilby/out/ship/trilby.glb' });
oct.wear(trilby);

// one of the pre-resolved remixes, and the old creator's options on the new bases
const r = await Bestiary.random(7);
const c = await Bestiary.fromMakeCreature({ stance: 'octopus', robot: true });
```

The fuller option lists are at the top of `runtime/bestiary.js` (creatures), `runtime/human.js` (humans),
`runtime/accessories.js` (props), `runtime/compat.js` (the old calls) and `runtime/remix.js` (runtime remix layers).

A file the runtime does not load (Aletheia's and Aporia's pieces) loads like any glb:

```js
const bytes = Deno.readFileSync('work/bestiary/human/aletheia/head_low/out/aletheia_head_low_v15.glb');
const head = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
scene.add(head.scene);
// the eye displays: a style's glb is seated on that head (same frame); its runtime drives it
const sb = Deno.readFileSync('work/bestiary/human/aletheia/eye_displays_v3/glb/on_head_low/eye_display_style_2_double_arm_spiral.glb');
const style = await new GLTFLoader().parseAsync(sb.buffer.slice(sb.byteOffset, sb.byteOffset + sb.byteLength), '');
scene.add(style.scene);
const SE = await import(new URL('work/bestiary/human/aletheia/eye_displays_v3/runtime/sister_eyes_v3.js',
    new URL('../', EIDOVERSE_DIR)).href);
const eyes = SE.attachSisterEyes(style.scene, { sister: 'aletheia', toneMapping: renderer.toneMapping });
eyes.setState('calm');                               // neutral, calm, focused, alarmed, delighted, sad
eyes.update(t, dt);                                  // per frame
```

## The Blender editions

On the `blender` and `auto-blender` branches the toolkit is ported to Blender, but this runtime is the three.js
edition's: `Bestiary.create()` and the calls above run in the three.js engine (`python eido.py render`). The glb files
are standard glTF 2.0 and import into Blender as assets (File > Import > glTF 2.0, or `bpy.ops.import_scene.gltf`):
meshes, skins, morph targets, clips and the base colour / normal / occlusion-roughness-metal maps come in. The runtime's
own materials (the TSL shaders that read the extra data maps) and its procedural motion do not.

## The shipped assets

Status: **live** = the runtime loads it by this path today; **delivered** = finished and usable as a file, not wired
into the runtime yet; **WIP** = shipped as it stands, known unfinished. Textures are embedded in each glb at most 2048
pixels on a side (the 4096 masters are kept by the authors, not in the repository); the four stag beetle variants also
carry some of their data maps at 1024 (mask, display, growth and iridescence packs; on the cyborg + crystal beetle its
two body pages' occlusion-roughness maps too) to stay under 50 MB a file. Paths
below are under `work/bestiary/`; sizes in MB as shipped.

### Creatures and their parts

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `octopus/octopus.glb` (203 joints, colour-change display packs) | 237,880 | 21 (max 2048) | 28.2 | live |
| `beetle/out_b58/stag_beetle_rig.glb` (104 joints, authored at 10x life size) | 49,568 | 12 (max 2048) | 41.8 | live |
| `beetle/variants/crystal/out/crystal_r3/stag_beetle_crystal_rig.glb` (metallic crystal growths) | 57,079 | 26 (max 2048) | 48.0 | live |
| `beetle/variants/crystal/out/ice_clear_r3/stag_beetle_crystal_rig.glb` (clear ice growths) | 51,855 | 26 (max 2048) | 47.4 | live |
| `beetle/variants/cyborg_stag_beetle_rig.glb` (cyborg parts, 2 clips) | 85,570 | 24 (max 2048) | 49.5 | live |
| `beetle/variants/cyborg_crystal/cyborg_crystal_stag_beetle_rig.glb` | 88,776 | 38 (max 2048) | 48.7 | live |
| `axolotl/ax11/axolotl.glb` (132 joints, 8 morph targets, authored at 4x) | 77,636 | 9 (max 2048) | 13.3 | live |
| `coat/out/octopus_shaggy/coat_octopus_shaggy.glb` (fur cards for the octopus) | 31,342 | 4 (max 2048) | 10.0 | live |
| `cyborg_c5b/assembled/octopus.glb` (the octopus prepared for cyborg parts) | 237,880 | 22 (max 2048) | 29.3 | live |
| `cyborg_c4/eye_implant_lens.glb` | 1,248 | 4 (max 512) | 0.5 | live |
| `cyborg_c5/mech_tentacle.glb` (37 joints) | 13,513 | 4 (max 1024) | 2.9 | live |
| `cyborg_c5b/hose/cyborg_hose_arm7_s3.glb` | 27,482 | 8 (max 256) | 4.3 | live |
| `runtime_a2/random_pool.json` (the 48 octopus remixes `random()` picks from) | - | - | 0.2 | live |

### Grafted creatures (third drop)

Each is one creature's part on another, made by the kit's forge and remix machinery, and loads with
`Bestiary.create({ species: '<the host>', path: '<the file>' })`. The recipe catalogue (`remix/recipe.py`) names them as
the DEFAULT size of each graft; the other sizes it lists ('long', 'ring', 'slender', the first eye) name files that are
not shipped.

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `remix_r1/cross/out/ax5hb/glb/ax5hb_baked.glb` (axolotl with a stag beetle's fore legs, both, from the femur, at the host limb's own length; 124 joints) | 109,064 | 15 (max 2048) | 15.7 | live |
| `remix_r1/cross/out/ax2host/glb/ax2host_baked.glb` (axolotl with an octopus arm for a tail, at the host tail's own length; 143 joints) | 80,172 | 19 (max 2048) | 17.5 | live |
| `remix_r1/cross/out/c5host/glb/c5host_baked.glb` (axolotl with a mechanical tentacle for a tail, at the host tail's own length: eight knuckles; pass `cyborg: { glow, tint }` for its lights; 149 joints) | 84,320 | 18 (max 2048) | 16.0 | live |
| `remix_r1/cross/out/ax4d/glb/ax4_baked.glb` (axolotl with octopus eyes) | 79,172 | 13 (max 2048) | 13.5 | live |
| `patches/scratch_crossbreed_m1/out/glb/m1a.glb` (octopus with one arm regenerated from a cut by its own arm generator: the first graft through the weld gates; 203 joints) | 122,560 | 27 (max 2048) | 23.1 | live |
| `patches/scratch_crossbreed_m2/out_m2c/glb/m2.glb` (octopus with a stag beetle's fore leg, from the knee, on one arm; 195 joints) | 277,127 | 27 (max 2048) | 31.7 | live |

A resting grafted tail coils flat on the floor by default; `create({ ..., gait: { tailCoil: k } })` sets it (1 = the
octopus arm's own resting coil, lower = the tail lies longer, 0 = no coil).

### Humans

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `human/h4d/build/glb/human_F.glb` (base woman, VRM 1.0, 116 joints) | 49,674 | 11 (max 2048) | 18.8 | live |
| `human/h4d/build/glb/human_M.glb` (base man) | 49,688 | 11 (max 2048) | 19.7 | live |
| `human/clothing_b2/glb/human_F_tee_base.glb` (T-shirt, trousers, shoes) | 76,810 | 26 (max 2048) | 26.8 | live |
| `human/clothing_b2/glb/human_F_shirt_ss_base.glb` (short-sleeved shirt) | 79,071 | 26 (max 2048) | 27.1 | live |
| `human/clothing_b2/glb/human_F_shirt_ls_base.glb` (long-sleeved shirt) | 82,598 | 26 (max 2048) | 27.5 | live |
| `human/clothing_b2/glb/human_F_shirt_ls_tie_base.glb` (long-sleeved shirt and tie) | 86,503 | 31 (max 2048) | 29.1 | live |
| `human/clothing_b2/glb/human_M_tee_base.glb` | 77,799 | 26 (max 2048) | 27.7 | live |
| `human/clothing_b2/glb/human_M_shirt_ss_base.glb` | 80,255 | 26 (max 2048) | 28.0 | live |
| `human/clothing_b2/glb/human_M_shirt_ls_base.glb` | 83,443 | 26 (max 2048) | 28.5 | live |
| `human/clothing_b2/glb/human_M_shirt_ls_tie_base.glb` | 87,605 | 31 (max 2048) | 30.4 | live |
| `cyborg_robot/c3/glb/human_F_c3.glb` (both hands robot hands, 114 joints) | 69,012 | 19 (max 2048) | 28.5 | live |
| `cyborg_robot/c3/glb/human_M_c3.glb` | 69,186 | 19 (max 2048) | 29.4 | live |
| `human/hair_b3/out_b6/human_<style>_b6_F/coat_human_<style>_b6_F.glb`: bob, bun, crop, curly, long, mohawk, ponytail, spiky | 7,442-27,220 | 3 each (max 2048) | 3.2-7.2 | live |
| `human/hair_b3/out_b6/human_<style>_b6_M/coat_human_<style>_b6_M.glb`: bun, crop, curly, long, mohawk, ponytail, spiky | 7,648-27,952 | 3 each (max 2048) | 3.3-7.3 | live |
| `human/h3/material/lut/skin_lut_{albedo,trans,preint}.f16` (the skin model's lookup tables, half floats) | - | - | 0.1 | live |
| `human/h4/rig/seats/cap_conform_{F,M}.bin` (the peaked cap's fit on each head) | - | - | 0.1 | live |

### Accessories

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `props/top_hat.glb` | 5,120 | 4 (max 2048) | 5.9 | live |
| `props/round_glasses.glb` (rigged, 15 joints) | 5,936 | 4 (max 1024) | 1.6 | live |
| `props/peaked_cap.glb` (an officer's peaked cap) | 5,956 | 4 (max 2048) | 8.0 | live |
| `props/monocle.glb` (its chain is built by the runtime) | 2,364 | 4 (max 1024) | 0.8 | live |
| `accessories_b5/tophat/cap_cord/out/peaked_cap_level.glb` (the peaked cap, its cord set level) | 5,956 | 4 (max 2048) | 8.0 | delivered |
| `accessories_b5/tophat/top_hat_tex/out/ship/top_hat.glb` (the top hat, its texture fixed) | 5,120 | 4 (max 1024) | 1.8 | delivered |
| `accessories_b5/tophat/gold_hat/out/ship_skins/gold_top_hat.glb` (short sparkle top hat, gold and silver skins) | 5,376 | 5 (max 1024) | 3.5 | delivered |
| `accessories_b5/tophat/trilby/out/ship/trilby.glb` | 3,360 | 4 (max 1024) | 1.5 | delivered |
| `accessories_b5/cowboy_hat/out/cattleman/cowboy_hat.glb` (four skins) | 3,360 | 10 (max 1024) | 2.8 | delivered |
| `accessories_b5/hard_hat/out/ship/hard_hat.glb` | 2,820 | 4 (max 1024) | 1.8 | delivered |
| `accessories_b5/soft/masks/out/forge/smile_mask.glb` / `frown_mask.glb` | 2,764 each | 4 (max 1024) | 1.0 each | delivered |
| `accessories_b5/soft/bow_tie/out/forge/bow_tie.glb` | 1,252 | 6 (max 512) | 0.4 | delivered |
| `accessories_b5/soft/beanie/out/forge/beanie.glb` (three skins) | 1,736 | 6 (max 1024) | 2.3 | delivered |

### Aletheia and Aporia (WIP pieces)

Aletheia and Aporia are characters of aihegemonymemes (x.com/aihegemonymemes), the same characters as
`eidoverse/assets/vrms/aletheia.vrm` and `aporia.vrm` (see CREDITS.md). These are WIP pieces of these characters,
shipped with the repository; credit as in CREDITS.md. Since the fourth drop Aletheia's body pieces also ship bound to
one skeleton (the rigged figure below); the head, hair, coat and tentacles are still worn on it from their own files.
Each piece is in metres, +Y up, and its `extras` say its own frame (the eye displays share the head's; the tentacles
name the jumpsuit sockets they plug into).

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `human/aletheia/head_low/out/aletheia_head_low_v15.glb` (head, skin and 18 cyberwear parts) | 10,102 | 3 (max 2048) | 7.7 | delivered |
| `human/aletheia/suit_low/out/aletheia_jumpsuit_low_v4_tucked.glb` (jumpsuit, legs tucked for boots, four port sockets) | 9,264 | 3 (max 2048) | 10.9 | delivered |
| `human/aletheia/suit_low/out/aporia_jumpsuit_low_v4_tucked.glb` (the same jumpsuit, Aporia's colours) | 9,264 | 3 (max 2048) | 10.8 | delivered |
| `human/aletheia/suit_hardware/out/maps_v6g_hw_patched/suit_{basecolor,normal,orm}[_aporia].png` (use in place of each jumpsuit's own maps with the hardware and zipper files) | - | 6 PNG (2048) | 20.6 | delivered |
| `human/aletheia/suit_hardware/out/aletheia_jumpsuit_hardware_v1.glb` (buckles, sliders, snaps, pocket flaps) | 3,691 | 3 (max 1024) | 1.2 | delivered |
| `human/aletheia/suit_hardware/out/aletheia_jumpsuit_zipper_v2.glb` / `aporia_jumpsuit_zipper_v2.glb` | 1,972 each | 3 (max 1024) | 1.9 each | delivered |
| `human/aletheia/boot_low/out/aletheia_boots_low_std_v3.glb` (a pair, for both) | 4,372 | 3 (max 2048) | 9.0 | delivered |
| `human/aletheia/tentacles/out/aletheia_sister_tentacles_rig_idle.glb` (four gripper tentacles, 20 joints each, an 8 s idle) | 20,326 | 9 (max 2048) | 5.8 | delivered |
| `human/aletheia/tentacles/out/aletheia_sister_tentacles_material_sets.json` + `tentacles/priv/out/sister_{maps,plug,gripper}/*.png` (which maps make Aporia's variant) | - | 16 PNG (512-2048) | 7.8 | delivered |
| `human/aletheia/eye_displays_v3/glb/on_head_low/eye_display_style_<1-8>_*.glb` (eight spiral display styles, seated on the head) | 1,816-12,884 | - | 0.3-2.9 | delivered |
| `human/aletheia/eye_displays_v3/runtime/sister_eyes_v3.js` (the displays' states, blink, gaze and glow) | - | - | 0.1 | delivered |
| `human/hair_craft/rebuild/style/out/coat_her_straight_shoulder_bangs_f2j.glb` (straight, shoulder length, a fringe; superseded by f2o below) | 12,718 | 3 (max 2048) | 3.8 | WIP |

Newer pieces (second drop). Where two versions of a piece are listed, the later one is current; the earlier one stays
for scenes that already load it.

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `human/aletheia/head_low/out/aletheia_head_low_v16.glb` (head v15 with a working mouth: a jaw joint, inner lips, teeth, gums, tongue, speech visemes as morph targets; 13 joints) | 11,852 | 4 (max 2048) | 8.2 | delivered |
| `human/hair_craft/rebuild/style/out/coat_her_straight_shoulder_bangs_f2o.glb` (the fringe above the brows, a wider face window, one smooth crown, blunt ends turned under; 529 cards, a level-of-detail ladder in its `extras`; its motion is being built) | 11,916 | 3 (max 2048) | 3.6 | WIP |
| `human/aletheia/arm_low/fix_r3/out/glb/aletheia_arm_L_hard_surface_lod0_11889_tris.glb` / `aporia_arm_L_...` (hard-surface forearm and hand, the left arm: 67 rigid parts on 19 joints, each joint's axis and stops in its `extras`; mirror it for the right) | 11,889 each | 3 each (2048) | 5.1 / 5.3 | delivered |
| `human/aletheia/suit_hardware/out/aletheia_jumpsuit_hardware_v2.glb` (hardware v1's parts with the belt as geometry: a webbing strap, one buckle at the front centre over the zip, keepers) | 4,375 | 6 (max 1024) | 1.7 | delivered |
| `human/aletheia/suit_hardware/out/aporia_jumpsuit_hardware_v2.glb` (Aporia's belt) | 1,204 | 3 (max 1024) | 0.5 | delivered |
| `human/aletheia/suit_hardware/out/maps_v6g_belt_patched/suit_{basecolor,normal,orm}[_aporia].png` (the jumpsuit's maps with the painted belt also painted out: wear the jumpsuit with this set when hardware v2 is worn) | - | 6 PNG (2048) | 20.6 | delivered |
| `human/aletheia/suit_low/out/aletheia_jumpsuit_low_v5_tucked.glb` / `aporia_jumpsuit_low_v5_tucked.glb` (v4 with the zip's open V cut out between its two rows; outside the cut it is v4) | 9,314 each | 3 each (max 2048) | 10.9 / 10.9 | delivered |
| `human/aletheia/suit_low/out/aletheia_neck_v2_under_the_open_zip.glb` (the neck piece between head and jumpsuit, seen through the open zip; vertex colours; identity matrix in the figure's frame) | 828 | - | 0.03 | delivered |

Newer pieces (third drop).

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `human/aletheia/head_low/jaw_fix/out/aletheia_head_low_v19.glb` (head v16 with the jaw skinned as a mandible: the chin and the lower border ride the jaw whole, so the jaw line keeps its curve when the mouth opens with the head turned; the cheek tabs' painted contact line taken out of the skin maps where the skin slides under them; the same topology, UVs, joints and face table as v16) | 11,852 | 4 (max 2048) | 7.6 | delivered |
| `human/aletheia/coat_rig/armpit_fix/out/aletheia_coat_rigged_lod0.glb` / `..._lod1.glb` / `..._lod2.glb` (Aletheia's transparent coat on spring bones: 139 joints, 33 that follow the body and 106 on springs; the drape's folds baked; its top is bound to the jumpsuit's skin and its `extras` record which) | 16,674 / 7,028 / 2,000 | 2 each (2048 / 1024 / 512) | 7.0 / 5.6 / 4.9 | delivered |
| `human/aletheia/coat_rig/armpit_fix/runtime/coat_rig.js`, `coat_springs.js`, `coat_film_maps.js` (the coat's runtime: loading a rigged coat on a figure, the spring solver with its fold rows and body colliders, the transparent film material) | - | - | 0.1 | delivered |

Newer pieces (fourth drop): the latest of both characters, shipped while they are still being reworked. What is being
reworked now: both coats are being re-cut to lie closer to the body (a finer drape, with a fabric high baked onto the low
where the coat rides the body), the hair's strands inside each card, and the walk.

| File | Triangles | Textures | MB | Status |
|---|---:|---|---:|---|
| `human/aletheia/head_low/jaw_fix/out/rigged/aletheia_A2_rigged_head_v19.glb` (Aletheia's rigged figure: the jumpsuit, zipper, hardware with the belt, cuff linings, boots, neck and hard-surface arms bound to one 82-joint skeleton, rigged for head v19; wear the head, hair, coat and tentacles from their own files) | 44,263 | 15 (max 2048) | 33.3 | WIP |
| `human/hair_craft/rebuild/strand/out/coat_her_straight_shoulder_bangs_f2s_m5.glb` (the sisters' hair f2s on its spring cages: f2o's cut with locks and blunt lock ends, the hair's flow written as its tangents; 530 cards, its level-of-detail ladder in the file. Its newer runtime is not public yet: the kit's `coat.js` draws it still, with the older look) | 10,070 at full detail (31,744 with the ladder) | 2 (max 2048) | 3.9 | WIP |
| `human/aletheia/head_low/jaw_fix/aporia_copy/out/aporia_head_low_v4_fuller.glb` / `..._middle.glb` / `..._subtle.glb` (Aporia's head: Aletheia's head v19 re-shaped by at most 2.4 mm to Aporia's own measured face, her dark steel hardware, her black brows, the same working mouth; three strengths of her face, "fuller" the one her figure wears, the choice still open) | 11,852 each | 4 each (max 2048) | 7.2 each | WIP |
| `human/aletheia/coat_rig_aporia/out/aporia_coat_rigged_lod0.glb` / `..._lod1.glb` / `..._lod2.glb` (Aporia's woven trench worn open, on spring bones: 133 joints, 31 that follow the body and 102 on springs; its `extras` record the jumpsuit skin it was bound to. Being re-cut closer to the body) | 13,192 / 5,284 / 1,682 | 1 each (2048 / 1024 / 512) | 7.6 / 6.0 / 5.4 | WIP |
| `human/aletheia/coat_rig_aporia/out/aporia_coat_springs.json`, `coat_rig_aporia/runtime/coat_rig.js`, `coat_springs.js`, `coat_film_maps.js` and `runtime/aporia_coat/*` (the coats' runtime, newer than Aletheia's coat folder's and serving both sisters, with Aporia's spring groups, her woven ripstop and her name plate) | - | 4 PNG (small) | 0.9 | WIP |

Every glb carries notes in its `extras` (frames, sockets, units). Where a file's `extras` describe its texture set
(a `uv_set` size of 4096), they describe the master; the shipped file's maps are 2048.

## Where the remix system stands

`remix/` holds the remix system's data and its one resolver, in Python: `slots.py` (the sockets and slots every base
exposes: heads, limbs, tails, horns, growth sites, coats), `elements.py` (one global table of element families: skin
recolours, glows, surface layers, growths, affixes) and `recipe.py` (a creature as plain data: base, parts per socket,
element, growths, accessories; validated, then resolved into a runtime block). `runtime/remix.js` applies a resolved
block's runtime layers to a creature (palette, display moods, element glow, accessories, bone tweaks). Each Python
module runs a self-test (`python -m eidoverse.bestiary.remix.recipe` from the repository root).

Since the third drop the kit also carries the grafting machinery: `slots.py` and `recipe.py` hold organ families and a
`graft` section beside `cyborg` (which donor variants are built, which need a part forged, a default size per host);
the forge regenerates or re-roots a donor's part at a host's ring record (`forge/graft.py`, `graft_socket.py`,
`cyborg_limb.py`); at run time a grafted limb steps with its own solver on the host's gait, a grafted tail carries the
host's wave on down the graft, and mechanical parts mount per chain (`runtime/bestiary.js`, `locomotion.js`,
`axolotl.js`). The six crosses listed under "Grafted creatures" were made this way and load with one `create()` call.

What is still missing is the generator as a tool: a new cross needs its part forged offline, skins are not yet swapped
across species, and nothing grows a new creature from a recipe on its own. The pool behind `Bestiary.random()` was
resolved offline for the octopus only.

## Licences and credits

The kit and its assets ship under the repository's licence (see LICENSE and CREDITS.md). The humans derive in part from
GNM Head v3 (Apache License 2.0) and MakeHuman / MPFB2 assets (CC0); [`THIRD_PARTY.md`](THIRD_PARTY.md) lists every
third-party source, its licence and the files that derive from it.
