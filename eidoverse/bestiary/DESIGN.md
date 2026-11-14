# Bestiary — the AAA organic creature creator (design v0, 2026-10-20)

Skye's goal (10-20): an entirely new creature creator for eidoverse-video, built with the rigor of my robot body (high
to low baking, layered materials, measured references, gates, LOOK at everything). It keeps the old creator's creature
types and attachment points; its meshes and textures must read as high-quality AAA organic creatures. The remix layer
follows a shipped game's creature attachment system (study G): attachments picked per slot by level, elemental material families, random affixes.

**Two tiers.**

1. **Forge** (offline: Python with numpy, scipy, numba and Warp/CUDA; `eidoverse/bestiary/forge/`). Part generators
   turn part specs into the ELEMENT MESHES library: an SDF-defined shape, a designed quad low, a subdivided and
   displaced high, a baked low, layered materials, a rig with sockets, and glb export. It is deterministic and
   versioned, with outputs under `work/bestiary/library/`.
2. **Bestiary** (runtime: three.js r184 WebGPU/TSL; `eidoverse/bestiary/`). It assembles a creature from library parts
   on one skeleton:
   - study-G-style slot tables, keyed by level range and variant type;
   - element families, which are parent materials driving each part's masks, plus growth geometry;
   - affix effects;
   - procedural locomotion per stance;
   - the old API names: `speed`, `turn`, `walkTo`, `say`, `talking`, `setTalkEnvelope`, `hasJaw`, `anchor()`,
     `parts()`, `fly` and `land`.

## What the references taught (measured, never copied: Skye 10-20)
These are study tools in `work/creature3/ref_probe/`: `measure_glb.py`, `skel_probe.py`, `clay_view.py` and
`tex_sheet.py`.

- **Budgets.** A shipped game's LOD0 creatures (study T):
  - 1.5-2 m creatures: 16-53k triangles, 41-207 joints, 2-4 material sets.
  - 3-5 m creatures: 25-110k triangles, 95-150 joints.
  - Armoured or "hunter" variants add parts in their own materials: Raptidon 25k → Hunter 68k.
  - Elemental variants add a GROWTHS mesh: ice shards or crystal clusters, 11-38k triangles in their own material.
  - An attachment such as the domestic hood is 5.7k triangles, skinned to the shared 119-joint skeleton.
- **Texture sets.** 2048² per set: head, body and limbs, plus growths and eyes. Texel density runs 1.7-2.8k px/m at
  1.6 m scale, with the head the densest.
- **Channels** (its creature skin master material):
  - Albedo, plus a tangent Normal.
  - SRM: specular, roughness, metalness.
  - TFA: transmission, fuzz, ambient occlusion.
  - M: a detail / flow / emissive mask.
  - A tiling skin MicroNormal (tile 14, strength 0.5) and a subsurface profile.
  - Observed creature skin: roughness p50 ≈ 0.2-0.3 (wet reptile/amphibian) with brighter crevices; AO baked from the
    high; transmission high in thin regions.
  - Ice: roughness ≈ 0.06 with frost patches, strong transmission. Crystal mineral growths: metallic 0.85-1.0.
- **Rigs** (the canine):
  - 3 spine joints, 2 neck, head, jaw, eyelids, throat, 2 tail joints;
  - limbs with twist and volume helper joints (_DM);
  - chest and stomach "breather" joints;
  - attach/detach joints for dismemberment;
  - IK targets at the root, and camera sockets.
- **study G (its creature attachment generator)**:
  - `CAGAttachmentManager.ChooseMeshAndMICTypeFromArray` scans a slot's `AttachDatum {LevelRange, Mesh, MICType}` for
    the current level.
  - `DoVariantAttach(socket, mesh, elemMICs)` attaches a static mesh to a skeletal socket, with the element's material
    instance.
  - Claws REPLACE the hands (a scale-hands-to-zero switch).
  - Variant types: Horns, Blade, Blob, Cube, Attach1, Attach2, TechHunterHead.
  - Elements: Normal, Fire, Ice, Electric, Poison, Player Soul, Moonlight, Dark Gaia.
  - Affixes: DoubleDamage, ExplosiveEnemy, DoubleSpeed, DoubleEXP, DoubleLoot, Invis, each with an MIC plus particles
    on affix sockets.
  - The elemental parent material interprets every part's own Diffuse, Normal, Masks and Emissive-mask, with an
    iridescent sphere-map sheen.

## Coordinates and units
Metres, right-handed, +Y up. A creature faces +Z (glTF front); +X is its LEFT (suffix `_L`). The bind pose stands on
y = 0.

## The shape → topology → detail pipeline (per part)
1. **Anatomy spec**: bones (chains with roles), per-station cross-section profiles (polar radius functions), and
   feature stamps (muscle masses, bony landmarks, carves). Everything is in anatomical frames, so it moves with the
   bones.
2. **SDF shape** (Warp): smooth unions of lofted sections, ellipsoids and round cones; subtractive carves only where
   meshed topology follows them (mouth, eye sockets, nostrils); voxel dents and stamps as backward field warps
   (SPECIMEN's lesson: hollows via boolean subtraction are fragile).
3. **Designed quad cage = the low.**
   - Ring lofts along chains (K vertices per ring).
   - Limb ports: a 2(a+b)-edge block removed from the trunk grid, bridged to the limb's root ring with fillet rings.
   - Heads from per-archetype generators: eye loops, a lip seam rolling into a mouth bag, nostril pits, ear roots.
   - Every cage vertex is PROJECTED onto the SDF surface: a ray from the station axis along the profile direction,
     then Newton steps on the field. The silhouette is the shape's; the edge flow is designed for deformation.
4. **High** = the cage, Catmull-Clark subdivided (a sparse subdivision matrix, 3-4 levels), projected exactly onto the
   SDF, then DISPLACED on the GPU with medium and fine detail: joint folds, wrinkles, scales and scutes, tubercles,
   pores, striations. The low's own subdivision gives near-orthogonal bake rays and no marching-cubes faceting.
5. **UVs**:
   - Ring lofts unwrap analytically (cut along the belly or inner line); ports and heads by LSCM (scipy sparse).
   - Texel density per set is uniform within a set.
   - Symmetric parts get mirrored UVs only where the bake allows (never across a visible seam).
6. **Bake** (Warp ray casting from the low's cage-averaged normals to the high):
   - tangent normal in the EXPORTED tangent basis (the runtime's own math);
   - AO, bent normal, cavity, curvature (fine and broad), thickness/transmission (rays inward), position and part ID;
   - gates: coverage, misses, back-facing, UV overlap.
7. **Layered material stack** (numpy/Warp, the robot body's method, organic families):
   - base pigment: countershading, mottling, stripes and spots in anatomical coordinates, so they are continuous
     across part seams;
   - capillary and vein tints in thin skin; cavity grime; curvature edge pale;
   - wet regions (mouth, eyes, nostrils); keratin, enamel and horn finishes;
   - roughness breakup; transmission from thickness;
   - masks out for runtime recolour and elements.
8. **Rig and weights**:
   - bones per the stance standard;
   - weights by heat diffusion on the cotangent Laplacian (scipy sparse), at most 4 influences, smoothed;
   - seam rings weighted identically on both sides.
9. **Export**: glb with skin, MikkT-style tangents, the texture set and sockets as child nodes of joints.

## Parts and seams (the element meshes)
- **Kinds**:
  - per-stance TORSO;
  - NECK and TAIL chains;
  - HEAD archetypes: canid, feline, reptile/raptor, bird (with a beak attachment), insect, fish, primate, serpent;
  - LIMB chains;
  - FEET and HANDS: paw, hoof, webbed, lizard, talon, shoe-foot, ball, hand;
  - EARS, plus ATTACHMENTS: horns (spike, ram, antler, moose, narwhal), claws, beaks, tusks, spikes, armour plates,
    shells;
  - WINGS (feather, membrane, bat, butterfly), FINS, TENTACLES;
  - ELEMENT GROWTHS.
- **Seam rings**: a port is a ring of K ∈ {8, 12, 16, 24, 32} vertices in a canonical frame. Both sides evaluate the
  same profile function, so positions match bit for bit, weights are identical and normals are continuous. Seams
  never sit in UV islands that would show a colour jump: the pigment is evaluated in anatomical space.
- **Sockets**: glTF nodes parented to joints, outside the skin's joints, named `socket_<slot>`:
  - `head`, `crown`, `eye_L/R`, `jaw`, `horn_L/R`, `horn_mid`, `claw_L/R`, `footclaw_L/R`, `back_0..n`,
    `tail_tip`, `chest`, `hips`;
  - `wrist_L/R` and `ankle_L/R`;
  - `affix_0..n`;
  - `growth_*` (element scatter roots).

## Runtime material (TSL)
- One node material per texture set, on the three.js SSS path (thickness → translucency), with clearcoat for wet
  masks and sheen for fuzz.
- A tiling micro-normal is blended over the baked normal.
- Palette recolour from masks: base, belly, accent, pattern A/B and eye colours are uniforms, so families remix without
  re-baking.
- The ELEMENT parent material (Normal, Fire, Ice, Electric, Poison, Player Soul, Moonlight, Dark Gaia) drives:
  - the emissive-mask colour and pulse;
  - frost, crystal or char overlays by world-up, curvature and AO;
  - sheen;
  - its growths' material.

## Remix (study G semantics)
- `Bestiary.create({stance, level, seed, element, affix, slots: {head, horns, claws, feet, back, tail}, ...old
  makeCreature options})`.
- The slot tables are JSON: `{levelRange: [a, b], part, variant}`. A variant maps to a material family per element.
- Rolls are seeded and deterministic. Claws or feet on a slot hide the base part (the study-G scale-hands-to-zero switch, done here by
  a part swap).
- Affixes:
  - DoubleDamage: a red rim pulse;
  - ExplosiveEnemy: glowing ticking pustules, then an end burst;
  - DoubleSpeed: speed streaks;
  - DoubleEXP: a gold sparkle;
  - DoubleLoot: a glint;
  - Invis: a refractive cloak.

## Realistic species, then remixes (Skye 10-20)
The creator must make REALISTIC creatures first, then remix them: octopus, wolf, beetle and other bugs, raptor, bird,
fish, serpent, snail, spider.
- A species preset is a stance plus an anatomy spec (proportions, profiles, stamps), parts per slot, a skin family and a
  pattern, all measured against real-animal references.
- Remixes swap slots across presets, for example a wolf with a beak and webbed feet, or an octopus with horns, and add
  element and affix rolls.
- The octopus's body plan is measured from 13 live animals and the literature (work/bestiary/research/
  BLOCKOUT_V4_SPEC.md, BODY_PLAN_PHOTOS.md) and checked against traced live outlines: the mantle lies back behind the
  head as an egg (its apex a little below the eyes), the eyes stand on the head's top as two turrets, the head is one
  broad mass running into thick arm bases, the funnel leaves from under the mantle's free margin and lies forward
  under the head, and the web is deepest at the sides (by sector).

## Claude's Creatures: the remix system (Skye 10-20: "cool whacky new creatures, Claude's Creatures!")
The bases are the vocabulary; the remix system writes new sentences with it. The unit is a creature RECIPE, plain
data, so a remix is an edit or a merge of recipes and every creature rebuilds from its recipe (craft guide 00.86):

    {name, seed, family: 'radial' | 'limbed' | 'axial' | 'arthropod' | 'mollusc',
     spec:    the family generator's proportions (the octopus SPEC: arm count, arm length, mantle, web, eyes, ...),
     sculpt:  layer recipes in anatomical coordinates (suckers, papillae, warts, scales, ridges, spines, crystal or ice
              growths, armour plates, nodules), each with its mask (dorsal, oral, arm s-range, patch sites) and seed,
     skin:    the skin recipe (patch network, palette, paint passes, display patterns, roughness, element overlay),
     parts:   {socket: part} (eyes, heads, horns, claws, shells, tails: study G slot tables with level ranges),
     accessories: [{socket, item}] (hats, glasses, ties: fitted per head archetype),
     element, affixes}

Two speeds of remix:
- OFFLINE (the forge, minutes): anything that changes the surface. A new spec, sculpt layer or part re-runs cage, UVs,
  plan, voxel high, bake and skin (the octopus: ~6 s + 4 s + 1 min + 6 min + 3 min at 4K). Layers mix across species
  because they all speak anatomical coordinates and the shared proc vocabulary (a crocodile's crack-network skin on an
  octopus's mantle; papillae replaced by crystal growths at the same patch sites).
- RUNTIME (the engine, instant, per instance): palette recolour from the masks (fixed pigment + region masks, craft
  guide 11.25), display patterns (the octopus's white spots, eye ring, bands, blotches: the colour-change channels),
  element overlays and affix effects, accessories on sockets, proportion tweaks through bones.

Each family generator exposes its SOCKETS from anatomy (the octopus: eyes, head top (the mantle's crest behind the
turrets), mantle apex, crown centre, mouth, arm tips, funnel), so parts and accessories seat without per-species code.

What the study-G creatures teach about wiring (a study note, structure only; study G's shading is legacy):
- A study G creature is one skeletal mesh plus data layers. A per-class ELEMENT table re-parents the body's material. Part
  HOOKS put static meshes on sockets: the first `{LevelRange, Mesh, MICType}` row that matches the tier, with no
  randomness. An AFFIX roll spawns effects at FX sockets. STATE parameters (dissolve, hit, stun) go by name to every
  component, so parts follow the body.
- **The socket does the fitting.** A borrowed helmet sits on the bug-dog creature's crest because the bug's `head`
  socket carries a half scale and a rotation. Our sockets carry a fit transform per part archetype (hat, glasses, horn,
  beak), so one hat serves every creature.
- **A build validator, because study G shipped without one.** Its data had parts on sockets their meshes lack, class
  defaults naming bones that don't exist, three part rows whose texture family doesn't match their UVs (every
  elemental medium bug-dog creature wears a mis-mapped horn), and a creature-hat path that never shipped. Every recipe build
  checks sockets, bones, UV families and material slots before anything renders.
- Elements recolour zones and switch on a glow mask (spike tips, rims). The shell goes neutral and the element shows
  in the soft tissue and the glow. One global element table, not palettes inherited per part (study G's part palettes
  drift from the wearer's).

GROWTH families (sculpt layers that grow from a creature's own patch sites, scales or ridges, each with its own full
PBR family; Skye 10-20: "shiny metallic growths and stuff too"):
- ICE: clear shards, roughness ~0.06, transmission and a blue thickness tint (the study-T element variants' numbers);
- METALLIC CRYSTAL: chrome / gold / gunmetal clusters, metalness 0.85-1.0, roughness 0.08-0.3 (the reference's
  metallic growth crystals), facets that catch the environment;
- BISMUTH: stepped hopper crystals with a thin-film iridescence (runtime);
- LIQUID METAL: smooth blobs and drips, mirror-rough, flowing at runtime;
- OXIDE / VERDIGRIS: copper spikes going green in their cavities; RUST-iron spines;
- BONE / CHITIN / KERATIN plates and horns; FLESH nodules and blisters; EMBER veins (fire), ARC veins (electric).
The sculpt carries MATERIAL IDS (the game-mesh rule: tag the sculpt's materials before the bake): every
stroke batch writes its material id into the voxels it wins, the bake samples the id under each texel, and the
material pass builds that texel from the id's family (skin, metal crystal, ice ...), with the metalness channel and
an id mask shipped for the runtime's view-dependent terms (iridescence, transmission, emissive pulse).

SKIN DISPLAY families: colour shifting at runtime (Skye 10-20: "skin color shifting effects ... would be a cool
creature option"). Cephalopod skin changes colour with layered cell types, and each layer maps to one runtime term.
Any creature can carry a display recipe; the octopus ships the first. Its display masks, `setDisplay`, the passing
clouds, the blue rings (iridescent) and the photophores all exist in runtime/bestiary.js and rendered in the engine
(work/bestiary/engine_test):
- CHROMATOPHORES (pigment sacs opening and closing): the display masks (spots, bands, blotches, eye ring, mottle)
  weighted by uniforms. Moods are presets of the weights: blanch (alarm, near white), flush (dark red-brown), mottle
  (camouflage), eye bar (threat).
- PASSING CLOUDS (cuttlefish, octopus): one or two broad, soft dark-brown fronts per body length sweeping out from the
  crown (~0.15 m/s), mostly over the mantle, head and webs and fading along the arms. The study T creature skin shader
  carries the same idea: its mask's green channel is the phase of a travelling emissive pulse (REF_SKIN_STUDY).
- IRIDOPHORES (structural colour): thin-film iridescence through the physical material's iridescence nodes, masked:
  the blue-ringed octopus's rings flashing, the sheen round octopus eyes, beetle shells on the bugs. The rings sit on
  a low-jitter cell network (no two touch, none fills solid): a dark brown disc, a thin blue band (~13 % of its
  diameter), black borders both sides, on an ochre flood; the flood and borders hold for the display, only the blue
  flashes (covered blue-black to full blue, one hue).
- LEUCOPHORES (white reflectors): the white spots' brightness (at most ~70 % broadband, inside the skin envelope)
  against a whole-body dark state (`darkAll`), and a diffuse white scatter (alarm).
- PHOTOPHORES (bioluminescence): a remix family (no benthic octopus has them): small ventral organs flashing in waves
  travelling from the crown (firefly squid, deep-sea fish).
Every procedural pattern reads the BIND-POSE position (TSL positionGeometry), so it rides the skin as the body moves.
- PAPILLAE (texture change): a runtime blend between a smooth and a raised normal map, both baked, so the skin goes
  from smooth to spiky with the mood.
The runtime needs coordinates to move patterns: the anatomical s and the patch-cell id go into a display channel, so
every pattern can travel and every spot can switch on its own.

## Accessories (the old creator's fun, at AAA quality)
- Hats: cap, top, beanie, cowboy, officer. Helmets: space, hardhat. Also glasses, sunglasses, masks (smile, frown) and
  ties.
- They are hard-surface and cloth props built with the robot body's craft: high to low, baked and layered (felt, knit,
  leather, acetate, metal, glass).
- They seat on the standard sockets every head archetype provides:
  - `socket_crown`, with a crown radius and a fit cage, so a hat scales to the skull;
  - `socket_eyes` (bridge point, eye spacing, ear-hook points), so glasses fit any face;
  - `socket_chest` for a tie.
- A per-accessory fit transform comes from the head archetype's measured socket data, so the same top hat sits on a
  wolf and on a beetle.
- Built (work/bestiary/patches/accessories_fit.md): forge/fit.py measures a SEAT on the block-out SDF (the skin's top
  along a tilted up, its frame, and a seat TABLE of the skin's section per depth) and validates each library prop on
  it (`fit_hat` deepens a hat until the brim clears and the opening touches); the export writes `seat_hat` under
  `socket_head_top` (the octopus: the mantle's crest behind the turrets, up along the mantle's dorsal normal, on the
  collar joint, which does not breathe) and `socket_eyes` / `seat_glasses` on the head joint as glTF extras. A prop
  carries its own fit
  data (opening, probes). runtime/accessories.js: `oct.wear(await Bestiary.accessory('top_hat'), {palette, size})`
  seats it from the table, with a per-zone palette tint over the baked maps. The first prop: forge/props/top_hat.py
  (REVOLVE crown, a SHELL brim, felt, grosgrain band and bow, binding, sweatband).

## Locomotion
Gait controllers are per stance, driven by speed and turn:
- foot planting with IK, support-polygon weight shift and a seeded swing;
- SPECIMEN's gait lessons: the pelvis load model, digits flat in stance, phase-indexed swing.
Radial bodies (the octopus) rest by a solved pose: each arm's path is laid on the ground every frame (a wander, a
distal spiral rising toward the tip, a drape from the crown to contact) and its chain aimed along it at the bind
lengths; the life motion is the same path's parameters moving (coils curling and uncurling, tips exploring), so
contact holds; the mantle ventilates (~0.4 Hz) with the funnel in counter-phase.

Jaw talk follows the old API.

## Quality gates (each run prints them; renders are for my eyes)
- Topology: manifold, symmetric, quad-dominant low; triangle quality.
- UVs: overlaps 0, texel-density spread within a set.
- Bake: coverage, misses, back-facing (≤ 0.05 % per part, the robot body's gate); per UV island (more than 1 % of
  its texels fully missed fails, named) and per miss cluster (more than 20 texels in size or extent fails), so a
  lumen or an eye cup missed whole cannot hide under a global percentage.
- Seams: normal angle < 1° and position Δ < 1e-6 m.
- Skin: ≤ 4 influences, normalized, Laplacian smoothness.
- Deformation probes at pose extremes: volume, candy-wrapper, self-intersection.
- Review: clay and material sheets beside the reference studies, in-engine renders and motion videos. The forge's
  look-dev renderer shades as the engine does (three r184's physical model: F0 from each material's ior, split-sum
  environment, per-pixel mips, AgX), so a map judged there reads the same in the engine.

## Budgets (from the references)
- Medium creature LOD0: 25-50k triangles with its attachments; 60-150 joints; 2-4 sets at 2048 (head ≈ 2.5-3k px/m
  at 1.6 m).
- Large creature: up to ≈ 100k.
- Attachments: 0.5-6k each. Element growths: 5-15k.
- LODs later: 50 / 25 / 12 %.
