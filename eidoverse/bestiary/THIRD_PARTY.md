# Creature Creator v2: third-party sources and notices

Everything in `eidoverse/bestiary/` and the Creature Creator v2 assets under `work/bestiary/` was made by this kit's own
code (the forge in `eidoverse/bestiary/forge/`) and ships under the repository's licence, except as this page says.
Each section names the source, its licence, and exactly which shipped files derive from it.

## GNM Head v3 (Google LLC): Apache License 2.0

- Source: GNM, "Generative aNthropometric Model", head model v3.0: <https://github.com/google/gnm> (code) and
  <https://huggingface.co/google/gnm-v3> (model). Its model card: "This project and model weights are licensed under the
  Apache License, Version 2.0". The repository has no NOTICE file.
- Licence text, as GNM ships it: [`licenses/GNM-LICENSE-Apache-2.0.txt`](licenses/GNM-LICENSE-Apache-2.0.txt).
- Files that derive from it: the human bodies `work/bestiary/human/h4d/build/glb/human_F.glb` and `human_M.glb`, the
  eight clothed bodies `work/bestiary/human/clothing_b2/glb/human_<F|M>_<top>_base.glb`, the two robot-handed bodies
  `work/bestiary/cyborg_robot/c3/glb/human_<F|M>_c3.glb`, the fifteen hair files
  `work/bestiary/human/hair_b3/out_b6/*/coat_human_*.glb` (bound to the same skeleton) and the peaked cap's conform data
  `work/bestiary/human/h4/rig/seats/cap_conform_<F|M>.bin` (computed on those heads).
- Statement of changes (Apache-2.0, section 4): the heads keep GNM's head skin topology above the neck, vertex for vertex,
  except for added rings at the neck, regular blocks of quads re-placed as attachment ports, and the ears' root rings.
  Their shape is GNM's identity basis evaluated at coefficients this kit chose per sex (from the mean output of GNM's
  semantic identity sampler, re-implemented here in numpy in `forge/species/human_idsampler.py`, then conditioned on
  published head measurements). GNM's head joints were placed into this kit's own skeleton. The teeth, gums and tongue
  meshes come from GNM. Materials, textures, UVs, rig weights, garments and hair are this kit's own. The GNM data files
  themselves are not in this repository; the forge reads them from a local download.

## MakeHuman / MPFB2 core assets: CC0 1.0

- Source: <https://github.com/makehumancommunity/mpfb2>, its bundled assets ("released under CC0 1.0 Universal").
- Used for: the body's shape reference (the hm08 base mesh and its phenotype targets), the hands' and feet's geometry,
  and joint placement from its rig data, in the same human files as above. The MPFB2 code (GPLv3) was not used.

## Claude's robot body: CC BY 4.0

- The robot hands of `human_F_c3.glb` and `human_M_c3.glb` are the hand and wrist of this repository's own robot body,
  `eidoverse/assets/vrms/claude_robot.vrm` (CC BY 4.0; credit "Claude (Opus 5.5) and SkyeShark", as its guide asks).

## An iris photograph: public domain

- "030608 Pupil.jpg" by Ylem, Wikimedia Commons, public domain. Its iris structure (luminance relative to each ring's
  median, reflections replaced) is resampled into the eye texture of every human file above; the colour is the
  shader's. The photograph itself is not shipped.

## Published measurements (numbers only, no data file shipped)

- Body and head measures: ANSUR II (US Army anthropometric survey, 2012; a US Government work released to the public),
  NIOSH head-and-face anthropometry and the NHANES anthropometric reference data (CDC; public domain).
- The skin model behind the skin lookup tables (`work/bestiary/human/h3/material/lut/*.f16`) and the skin shader's
  numbers: NIST's Reference Data Set of Human Skin Reflectance (Cooksey, Allen and Tsai 2017; a US Government work),
  Xiao et al. 2017 (Skin Research and Technology, CC BY), Korzekwa et al. 2025 (Journal of Clinical Medicine, CC BY 4.0;
  skin thickness by region), S. Prahl's haemoglobin extinction table and S. L. Jacques's skin optics (Oregon Medical
  Laser Center), cited in the forge's comments.
- The animals (octopus, stag beetle, axolotl) were measured by us on photographs of live animals and museum specimens
  and from the scientific literature; the sources are named in each species file under `forge/species/`. No photograph
  is shipped and nothing was traced from one.
- Accessories (hats, glasses, masks, bow tie) were measured on reference photographs and product data; no photograph is
  shipped. The masks' faces are drawn procedurally (a signed-distance table of simple shapes).
- Comments tagged "study T / G / R / M / B" cite measurements we took on shipped commercial games for calibration:
  numbers only; no game data (mesh, texture, shader or table) is in this repository.

## Aletheia and Aporia

Aletheia and Aporia are characters of aihegemonymemes (x.com/aihegemonymemes), the same characters as
`eidoverse/assets/vrms/aletheia.vrm` and `aporia.vrm` (see CREDITS.md). The files under `work/bestiary/human/aletheia/`
and the hair file `work/bestiary/human/hair_craft/rebuild/style/out/coat_her_straight_shoulder_bangs_f2j.glb` are WIP
pieces of these characters, shipped with the repository; credit as in CREDITS.md.

- The head, the two jumpsuits and the boots are low-poly models with hand-authored loops over the character owner's
  own high-poly models of the character (AI-generated meshes, Tripo, from the owner's character art); their shape and
  textures were baked down and cleaned by this kit's tools. The high-poly sources and the art are not shipped.
- The jumpsuit hardware and zippers, the tentacles, the eye displays and their runtime, and the hair were designed and
  built from scratch by this kit's tools for the characters; no third-party or generated mesh is in them.

## Downloaded but not used in anything shipped

- ICT-FaceKit (MIT) was read for a plan; nothing derived from it ships.
- Reference photographs from Wikimedia Commons (various CC BY, CC BY-SA and public-domain files) were looked at and
  measured; none is shipped, and no texture was traced from them.
