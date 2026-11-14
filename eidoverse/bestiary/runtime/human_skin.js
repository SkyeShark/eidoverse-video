// H4b MERGED (the H4b integrator, 11-02): the H4b face builder's Edits from its copy h4b/face/engine/human_skin.js (sha1
// cbdf7036, a copy of this file at 19dcec77; only the copy's header not landed), each marked (H4b face): THE MOUTH'S CAVITY (K.MOUTH:
// the lips' opening as an aperture the face driver sets each frame through setAperture(), humanUniforms' mouthC / mouthN /
// mouthU / mouthAB / mouthOn, and apertureVisibility() / apertureSpecVis() / apertureDirect(): each inside point's view of
// the outside through it, on the ambient, the reflection and the direct light of the teeth, gums, tongue and the HEAD's wet
// tissue behind the lips; markMouthSock() finds the sock by its UV islands); the tongue and gums as tissue (pigments, a
// wrapped diffuse); the lips' transmission path near the opening (LIP_MIN_MM); the iris in zones (K.IRIS, the EYES set's
// iris_mode 'structure', irisInnerL / R). mouthOn stays 0 until a driver calls setAperture (the cavity term then off). The
// file as it stood before is h4b/integrate/before_merge/human_skin.js (19dcec77): the BEFORE renders read it.
//
// H4 MERGED (the H4 integrator, 11-01 09:1x): the close-up builder's Edits from its copy h4/close/engine/human_skin.js (sha1
// 61e85ba6), each marked (H3c): the moles' melanin cap and range (K.MOLE.MEL_CAP, MEL); the inner corner's wedge (the
// shell's SHELL_POW, SHELL_GAIN, SHELL_TINT, RING_AO_FLOOR); the EYES set in eyeMaterial (the iris from a photo at the
// refracted point, the pupil remapped onto the set's reference pupil, the identity's colour over the photo's mean; the
// sclera at uv()); the MOUTH set and the per-vertex AO in mouthMaterial (humanMaterial passes the geometry). The skin's
// albedo stays physical (H3b's LUT): the lead did not take the copy's display LUT (x1.45 chroma); the human is judged
// under AgX + Punchy (human_scene.js). The file as it stood before is h4/integrate/before_merge/human_skin.js (8de3e0c9).
//
// H3b MERGED (the H3b integrator, 10-31 18:1x): this file is the material builder's h3b/material/human_skin.js (sha1
// 9aa4d5db, copied verbatim over H3's beda8006, which is kept as h3b/integrate/before_merge/human_skin.js), with the
// integrator's Edits after the copy, each marked (H3b integrator). The material builder's own header, as it was:
// H3b (the material builder, 10-30): A PRIVATE COPY of engine_test/human_skin.js (sha1 beda8006, copied verbatim
// 16:3x) until the integrator merges it. Its changes are the Edits after the copy (h3b/material_notes/NOTES.md).
//
// human_skin.js — the HUMAN's runtime materials (H3, the material builder, 10-30): skin, eyes, teeth, gums, tongue.
// STAGED: H4's runtime patch lands this file as eidoverse/bestiary/runtime/human_skin.js; until then the human's test
// scene (engine_test/human_scene.js) imports it from here. three r184 WebGPU / TSL.
//
// THE SKIN (HUMAN_PLAN §5.1). Its colour is NOT a baked albedo: the maps hold each anatomical zone's MULTIPLIERS of
// the identity's base pigments, and the albedo comes from the skin LUT (forge/species/human_skin_lut.py: a two-layer
// spectral model fitted to NIST's 100 measured forearms, dE*ab 1.47 mean; zones from Xiao et al. 2017), so one set of
// maps serves every identity and the tone space is continuous (the uniforms melanin / blood; tint for beyond-human
// skins: Hege's red, a green alien).
//   channels (forge/species/human_skin.py), read in this layout below:
//     PIGMENT  R melanin zone multiplier, G blood zone multiplier (log2(f) / LOG_RANGE + 0.5), B freckle zone, A pores
//     SURFACE  R curvature / CURV_MAX (1 / mm), G thickness to the other side / THICK_MAX mm, B roughness, A wet
//     AUX      R ambient occlusion, G skin tissue thickness / TISSUE_MAX mm (Korzekwa 2025 by region)
//   TEXTURED (the H3 integrator's switch, 10-30: h3/integrate/glb/human_<sex>.glb): the forge's split LOW with its
//   normal map and MACRO normal map, and three RGB packs per texel (h3/integrate/i01_packs.py) that skinMaterial
//   rebuilds into that layout (no data in alpha: the engine's Deno decoder un-premultiplies it; the tissue scale
//   folded into the curvature, the mip-0 normal variance into the roughness). The stand-in (vertex attributes
//   _PIGMENT / _SURFACE / _AUX on the H2b clay) still reads as before.
// THE SHADING, a lighting model of its own (SkinLightingModel, PhysicalLightingModel's direct() replaced):
//   * PRE-INTEGRATED DIFFUSE (Penner & Borshukov 2011) through the LUT of the fitted dermis's own diffusion profile:
//     per channel a lookup at (N.L, curvature), each channel at its own normal between the geometry's and the detail's
//     (red scatters furthest: DIFF_NORMAL), the curvature scaled by the region's tissue thickness (thin lids scatter
//     less);
//   * a DUAL-LOBE GGX specular at the stratum corneum's F0 0.028 (ior 1.4): lobes at roughness x LOBE0 and x LOBE1,
//     mixed LOBE_MIX (the dual-lobe skin specular of the plan's §5.1 [E: Epic's Digital Human defaults]);
//   * TRANSMISSION through thin tissue that is not one binary map: the light reaching the tissue's BACK face (the shadow
//     tested there, P - N x thickness: a back-lit ear glows, a nose behind the head does not) times the LUT's
//     transmittance E^2 exp(-k t), E the epidermis's (by melanin), k the dermis's extinction per mm (by blood), t the
//     thickness channel: red through a 3 mm ear, nothing through a cheek;
//   * the environment is three's (split-sum specular, irradiance diffuse), with the AO channel;
//   * the runtime MICRO RELIEF (relief tier R): pores and the primary-line network as a procedural height on the bind
//     pose (mm), faded below ~2 px, its filtered slope variance moved into the roughness (Toksvig's variance; the beetle's
//     rule), plus Tokuyoshi-Kaplanyan specular AA on the shading normal.
// THE EYE (§5.2): the globe of forge/species/human_eye.py; the iris read through the cornea by a refracted view ray onto
// its plane (ior 1.376), a procedural human iris (pupil by light, collarette, radial fibres, crypts, limbal ring), the
// sisters' spiral irises as a uniform option with C4's organic glow.
const THREE = globalThis.THREE;

export const K = {
    MEL_MAX: 1.0, BLOOD_MAX: 0.20, CURV_MAX: 1.0, LOG_RANGE: 12.0,
    THICK_MAX: 50.0, TISSUE_MAX: 4.0, TISSUE_REF: 1.4,
    IOR: 1.4,
    LOBE0: 0.75, LOBE1: 1.30, LOBE_MIX: 0.85,
    // (H3b integrator, 10-31) the per-channel share of the DETAIL normal in the diffuse: [0.10, 0.20, 0.33], the H3b
    // forge's derivation (h3b forge_notes 05:20: Burley's profile fitted to this file's own dermis, r50 0.81 / 0.41 /
    // 0.24 mm, transfers R 0.08-0.15, G 0.15-0.28, B 0.24-0.42 of a 0.5-1 mm relief). Since H3 the macro normal map
    // carries the macro forms, so this decides only how much T tier (pores, the furrow network) the diffuse sees; the
    // relief stays in the specular. H3's / the material builder's [0.55, 0.80, 0.92] ('olddn') read the forge's network as
    // crumpled paper in its twin; in the engine the two differ little (h3b/integrate/look/compare/ab_dn_*.png)
    DIFF_NORMAL: [0.10, 0.20, 0.33],
    TRANS_FWD: 1.2,          // the forward-scattering lobe's weight in the transmission [E: look-dev; skin's g ~0.8]
    TRANS_MAX_MM: 12.0,      // the back-face shadow test reaches at most this far in
    TRANS_PAST_MM: 0.8,      // ... and lands this far past the back face (out of its own shadow bias)
    TRANS_SHADOW: true,      // false: the transmission takes the unshadowed light (the geometric back term only)
    TRANS: true, MICRO: true, PREINT: true,   // the terms' switches (the scene's diagnostic switches set these)
    F90_HONOUR: true,        // (H3b) direct lobes read the material's specularF90, not three's hard-coded 1
    // H3's soft-shadow term, per-channel powers s^[0.55, 0.95, 1.2] of the filtered shadow: OFF since H3b (the scene's
    // 'oldpen' switch brings it back for the before / after). Its slope is infinite at s = 0, so at every penumbra's dark
    // end red jumped from ~12 % of the key to 0 within a texel: a saturated orange line (h3b p01: a chroma excess of 8.2
    // whatever the penumbra's width, its edge 7-16x steeper than the scattered edge's)
    PENUMBRA: null,
    // (H3b) THE SCATTERED SHADOW: per channel, the shadow convolved with the fitted dermis's own diffusion profile
    // (forge/species/human_skin_lut.radial_profile: half the red light leaves within 0.81 mm of where it entered, 90 %
    // within 3.75 mm; green 0.41 / 1.49 mm; blue 0.24 / 0.96 mm), approximated by the shadow re-evaluated at taps on
    // the tangent plane: the centre (the PCF itself) and two rings of 5 (radius mm, taps, phase), the second turned
    // 36 deg so the ten interleave; W the weights per channel [centre, ring 1, ring 2], fitted to the exact scattered
    // edge over our shots' penumbra widths and every edge orientation (h3b/material/p01_penumbra.py, layout C10:
    // |taps - exact| <= 0.051 R / 0.043 G / 0.036 B of the light; the warm excess 4.9 chroma over 2.1 mm on the face
    // close-up's facing skin, 2.7 over 2.4 mm at N.L 0.45, its steepest slope 1.04-1.19x the exact edge's).
    // CONCAVE_MM: each tap is lifted off the tangent plane by the sagitta of a fold this tight, so in a lit fold the
    // outer taps do not dip under the skin (the shadow test would read them as occluded and steal red).
    // AO: the rings fade out by the baked ambient occlusion between these values (their weight goes to the centre):
    // in a cavity the tangent plane crosses AIR to lit skin outside (the nostril's floor reached the lit ala 3.6 mm
    // away and glowed red in the sharp stills, 17:0x), where real light would travel round the rim through tissue.
    // null: off
    SHADOW_SCATTER: {
        RINGS: [[1.6, 5, 0.0], [3.6, 5, Math.PI / 5]],
        W: [[0.4845, 0.3070, 0.2084], [0.7058, 0.2864, 0.0078], [0.8356, 0.1644, 0.0]],
        CONCAVE_MM: 20.0,
        AO: [0.35, 0.70],
        COARSE: true,        // each ring tap one hardware compare, not a 16-call PCFSoft filter ('ringpcf': the full filter)
    },
    TRANS_LOOKUP: true,      // (H3b) the transmission's back-face shadow through shadowLookup (false: H3's form)
    TRANS_COARSE: true,      // ... one hardware compare ('ringpcf': the full filter)
    PORE_CELL_MM: 1.55,      // Flament 2015: cheek pores 21-91 / cm2 at 18-29 -> spacing 1.0-2.2 mm
    LINE_CELL_MM: 0.55,      // the primary-line network's polygons (Gougeon 2022: primary lines 30-100 um deep)
    PORE_DEPTH_MM: 0.06, LINE_DEPTH_MM: 0.035,
    MICRO_FADE: [0.03, 0.10], // mm per pixel: the relief fades out between these footprints (at [0.05, 0.22] it read
    //                          as grain on the neck at the face close-up's 0.25 mm / px; the HEAD normal map carries
    //                          the pores there once baked)
    MICRO_VAR: 0.035,        // the faded relief's slope variance at full pore strength (alpha^2 added)
    SAA_SIGMA2: 0.15915494, SAA_KAPPA: 0.18,
    // (the H3 integrator, 10-30) THE TEXTURED PATH (the forge's bakes + h3/integrate/i01's packs in the glb):
    TOKSVIG_DEAD: 0.0035,    // the 8-bit normal codes' own length error, read as no variance (the beetle's measure)
    ANISOTROPY: 16,          // every pack anisotropically filtered (the beetle's 10-29 look check: the glb's sampler
    //                          is trilinear only, and a grazing view's mip by the footprint's long axis flattened it)
    // (H3b) THE EYE'S PARTS (h3b/material/e01_eyeparts.py, the glb eyeparts_<sex>): true once the scene has them, so the
    // eye's own stand-in band goes and its aoNode is the opening's measured AO (the extras' shell_ao_ref)
    EYE_PARTS: false,
    // (H3c, 11-01) THE MAN'S DARK WEDGE AT THE INNER CORNER (the H3b check's k7): the A / B with the parts off (h4/close/look/
    // scratch/wedge_ab_v1.png: default, nomsh, noeye, both) put it on the parts, not the micro-shadow: the shell multiplied the
    // ball's corner down to ~25 % (its measured occlusion reaches 0.85 there, x a near-black tint), and the ring's tissue in the
    // corner sat at its AO floor. A cosine AO counts the caruncle, the plica and the lids round the corner as black walls, but
    // they are pink tissue that bounces the light back (and the ball is a scatterer too), and the shadow map already takes the
    // direct key off the tucked ball: so the shell takes occlusion^SHELL_POW x SHELL_GAIN (the corner's 0.85 -> 0.62, the
    // opening's median 0.31 -> 0.14), its tint the tissue's bounce, and the ring's floor is higher
    SHELL_GAIN: 0.80,        // the shell's measured occlusion^SHELL_POW x this (H3b: 1.0, linear)
    SHELL_POW: 1.5,
    SHELL_TINT: [0.30, 0.17, 0.14],    // what a fully occluded ball shows: the pink tissue's bounce (H3b: 0.17, 0.095, 0.08)
    SHELL_LASH: 0.32,        // the upper lashes' shadow on the ball until H4's lashes exist: a band under the upper lid
    SHELL_LASH_MM: 1.5,      //   of this width (0 when real lashes land) [E: the eye photos' band]
    TISSUE_ROUGH: 0.30,      // the wet conjunctiva and caruncle under the same film [E]
    TEAR_IOR: 1.336,         // tears (water-like; the film over the ring)
    TEAR_ROUGH: 0.14,        // a liquid surface reads ~0; at 0.07 the key's line was narrower than a pixel at the
    //                          macro's 0.02 mm / px (a few sparkles along the lid), so the strip's lobe is wider and
    //                          filtered by its own normal's screen derivative (specular AA) beyond that
    RING_MEL: [0.30, 0.10],  // the ring's tissue: melanin x, the lid's posterior edge .. the corners' conjunctiva [E]
    RING_BLOOD: [9.0, 40.0], //   blood x: at the zone table's x12-15 it rendered dull mauve (albedo a* 17); the eye
    //                          photos' caruncle is salmon red, and it is a mucosa over a dense capillary bed [E]
    RING_AO_FLOOR: 0.75,     // (H3c: 0.60 -> 0.75, the wedge) the ring sits in a wedge whose measured AO reaches 0; the tissue is lit by scatter
    //                          through the lid and off the white ball, not only by the sky it sees [E]
    WET_AO_FLOOR: 0.40,      // the skin's wet tissue likewise (the lid's wet wall baked AO ~0: a black pit at each
    //                          corner, where the eye photos show pink) [E]
    RING_SHADOW_LIFT_MM: 1.4, // the shadow map's texel (0.31 mm) is wider than the wedge the strip sits in: read at
    //                          the strip the ball and the lid wall shadow it; read here, off the surface, the strip
    //                          still takes the brow's and the nose's real shadows
    // (H3b) MULTI-BOUNCE AO on the skin (Jimenez et al. 2016, "Practical Real-Time Strategies for Accurate Indirect
    // Occlusion", its fit per channel by the albedo): light in a fold bounces between walls of skin, so a crease is a
    // warm dark, red-orange, never the grey-black of a bare AO multiply
    AO_BOUNCE: true,
    // (H3b) SKIN VARIATION at runtime, on the bind pose: nothing here needs a UV, a map or a texel, so it survives any
    // layout, the mirrored limbs are not mirrored in it, and a crowd sharing one set of maps differs by its seed.
    // THE MOTTLING: a periodic 3D noise volume (noiseVolume below) read at three scales, in log2 of each pigment.
    // Its target is what the photos' skin holds per octave (h3b/material/s01_skin_stats.py: a* RMS 0.14-0.45, b* 0.2-0.35
    // per octave from 0.25 to 16 mm, against H3's 0.05-0.15: 2-6x too clean). VOL_MM: mm per volume texel per layer
    // (64 texels a period); BLOOD / MEL: log2 amplitude per layer (unit-variance noise); the fine layer fades out by the
    // footprint so it never crawls.
    MOTTLE: { VOL_MM: [0.30, 1.21, 4.83], BLOOD: [0.20, 0.20, 0.24], MEL: [0.10, 0.10, 0.09] },
    // THE SPOTS: per layer a grid, each cell holding one candidate spot wholly inside it (so ONE cell lookup, no search:
    // H3's Worley read 27), its centre, radius and strength hashed from the cell. A spot is a ball in the bind pose's
    // volume, and the skin's surface cuts it: g / cell^3 balls per mm3 for a cell's existence probability g, so a surface
    // crosses g * 2 R / cell^3 of them per mm2 (the mean R; a first build with cell^2 here drew 1 / 14 of the moles).
    // FRECKLE: from the photos, s01: detected spots (d >= 0.45 mm) 5.7 / cm2 on a freckled cheek, 9.1 on the nose's side,
    // 3.7-4.0 on sun-worn shoulders and arms, 1.2 on a light shoulder; d p10 / p50 / p90 0.6 / 0.96 / 2.5 mm (classic
    // ephelides are "1-2 mm", Susinna 2024, who grade density but give no counts); contrast dL* -5, da* +2, db* +2.
    // D_CM2 is the crossing density at freckles = 1 in zone weight 1; the detector sees about a third of them (a ball's
    // small sections and the faint spots fall under its threshold), which is why it sits above the photos' counts.
    // Three rotated grids so no lattice shows.
    // LARGE: one sparser layer on a coarser grid for the big patches (the photos' p90 d 2.5 mm: a 1.9 mm cell can not hold a
    // ball that size), its density a share of the small layers'
    FRECKLE: { CELL: 1.9, R: [0.20, 0.94], D_CM2: 36.0, MEL: 0.54, BLOOD: 0.12, LAYERS: 3, WARP_MM: 0.10, EDGE_MM: 0.17,
        LARGE: { CELL: 3.4, R: [0.75, 1.65], SHARE: 0.10 } },
    SPOT_FINE_MM: 0.11,      // mm per volume texel of the spots' fine read (rim and interior)
    // MOLE: common acquired naevi >= 2 mm: mean total 12-58, men 9-36, women 14-58 (Jayasinghe 2022, 12 studies, 9,593
    // people); the small ones densest on the chronically exposed face, neck and forearms, the large on the back. `moles`
    // is the identity's whole-body count (1.7 m2 of skin); zone weight 1 + ZONE_GAIN x the freckle zone (the exposed
    // skin). Radius 1 .. 3 mm (d 2-6 mm; the NCI ruler photographs: 1.2, 2.2, 5.6 mm flat and dark, a 9 mm raised pale one);
    // round, nearly flat, an even dark body with a soft ~0.25 mm rim. H: dome height x R (0.18 read as a shiny blister
    // beside the ruler photos, whose flat naevi carry the skin's own texture across them).
    // MEL: log2 of the melanin at a mole's centre, hashed per mole across this range. The photos' display luminance inside / the
    // skin around is 0.06-0.43, median ~0.2 (h3b/material/s05_moles.py). Read at the display, because the view transform lifts
    // the darks: ratio on screen ~ ratio in the albedo ^ 0.75, the specular on top (1.35-2.7 read a median of 0.4 on the back).
    // Past ~2.9 the LUT's hue turns over (db* goes negative: black, not brown), and a first 2.1-3.9 drew black dots at a portrait's
    // distance. BLOOD: log2, for the brown moles' a* (+6 .. +11 against the skin in the photos; the melanin alone gives +3).
    // (H3c, 11-01) MEL_CAP: the mole's melanin VOLUME FRACTION never past this (unless the skin's own is), so a mole stays brown
    // on every zone: the face's zones already hold ~1.4x the back's melanin, and the old range's dark end crossed the LUT's
    // turnover there (probe h4/close/probes/q05: the face's m 2.0 read db* -5 against the skin through the display LUT, a
    // grey-black dot) while the back's moles stayed light (the material builder's s05: median display ratio 0.35-0.38 against
    // the photos' 0.21). Now the range starts darker, [1.9, 2.9], and the cap 0.45 (u 0.67, db* +8..+15 against the skin
    // through h4/close/lut) holds the brown: display ratio ~0.22-0.28 on the back, ~0.3 on the face. (H4 integrator: the cap is
    // a melanin fraction, so it holds on H3b's LUT too; the lead kept these two with the physical albedo)
    MOLE: { CELL: 14.0, R: [1.0, 3.0], ZONE_GAIN: 2.0, AREA_CM2: 17000.0, MEL: [1.9, 2.9], MEL_CAP: 0.45, BLOOD: 0.90, H: 0.05, WARP_MM: 0.04, EDGE_MM: 0.14 },
    // (H3b integrator) MICRO-SHADOWING of the DIRECT light by the baked AO (Uncharted 4's: saturate(|N.L| + 2 AO^2 - 1)):
    // a fold narrower than the shadow map's texel, or one the LOW bridges, gets no shadow from the map, so its walls read
    // lit under a raking key. The forge's case (h3b forge_notes 17:36, probes p19 / p20): the woman's gluteal cleft, the
    // LOW bridging it, its wall a narrow lit strip in back views; the bake already holds the occlusion there (AO p50 0.33
    // within 4 mm of the midline). The AO read is the skin's own aoNode (the wet tissue's floor in: the lid's wet wall
    // bakes AO ~0, and the eye ring's tissue answers for it). Two changes from the textbook form, both from the first A / B
    // (h3b/integrate/look/compare/ab_msh_F.png, 18:5x): N.L is the MACRO normal's (the detail normal carries the pores and
    // the runtime relief, and the threshold turned their slopes into a black stipple round the cleft), and the AO is
    // remapped by smoothstep(AO[0], AO[1]) first: ours is a 25 mm AO (the bake's 24 rays), not a crease-scale one, and
    // raw it darkened a band 8-15 mm wide; remapped, the skin past AO 0.6 is untouched and the crease itself goes dark.
    // ON since the third A / B (19:0x): the cleft's lit tab and its hard step are gone under the back key, the raking key's
    // lit sliver is fainter, the face and hands move by p99 2-3 levels. false (the scene's 'nomsh'): off
    MICRO_SHADOW: true,
    MICRO_SHADOW_AO: [0.10, 0.60],
    MICRO_SHADOW_BIAS: 1.0,  // its AO read this many mips coarser than the pixel's own level (the bake's ray noise) ...
    MICRO_SHADOW_LOD_MIN: 2.5, // ... and never finer than this level (magnified, a bias reads mip 0: the eye A / B's blotches)
    // the skin's deep folds gather pigment (axilla, groin, the nose's wing, neck creases): melanin up where the baked AO
    // is low [E]; the mean photo's folds read warm-dark, and this is what keeps them from reading as shadow alone
    FOLD_MEL: 0.30,
    // (H4b face, 11-02) THE MOUTH'S CAVITY: what lights the inside of an open mouth. The H4 parts' AO counted the parts alone
    // and the mouth sock is skin with the wet tissue's AO floor, so the sky lit the tongue, the teeth and the sock as if the
    // lips were not there (h4b/face/out/diag/d01_mouth_terms_F.png: with the sky off the tongue went black; with the key off
    // nothing changed: the key's shadow map already keeps the key out). The cavity is a closed box with one window, the
    // lips' opening: an APERTURE (an ellipse: centre, outward normal, half-width and half-height, from the lip joints each
    // frame: humanUniforms' mouthC / mouthN / mouthAB, mouthOn 1 once a driver sets them) and each inside point's cosine-
    // weighted view of the outside through it (a disc of the ellipse's area: Frostbite's disc illuminance with its horizon,
    // over pi) multiplies the ambient light; the light the walls pass between them is Jimenez's multi-bounce on the
    // tissue's albedo. The reference (h4b/face/out/speech/fl_t18.37_mouth.png, a public-domain address): under a frontal
    // key the tongue's front lit, its back ~15 L* darker within a few mm, the corners near black (L* 9-11)
    MOUTH: {
        ON: true,
        WET_MASK: [0.35, 0.75],      // the HEAD's skin: its wet zones (the mouth zone's mucosa 1.0; the vermilion 0.15) ...
        NEAR_M: [0.095, 0.085],      // ... within 85-95 mm of the opening's centre (the pharynx's wall lies 75-85 mm back:
        ABOVE_M: [0.025, 0.035],     //   at 62 mm it was left sky-lit, d11) and no higher than 25-35 mm above it along the
        //                              opening's vertical (the lid margins sit ~65 mm above)
        DEEP_ABOVE_M: [0.012, 0.016], // the deep interior's (zone-free) height limit (the nose's underside is 18-25 mm up)
        DEEP_BELOW_M: [0.024, 0.030], // ... and depth limit below the centre (the mouth's floor; the skin under the jaw,
        //                               40-60 mm down, faces the opening too and went black, d20)
        SIDE_M: [0.0015, 0.005],     // the outside: 1.5-5 mm in front of the opening's plane (the plane runs between the lip
        //                              joints; the lips' own inner surfaces bulge up to ~3 mm past it and took the full sky
        //                              as 'outside' at [-1, 2.5] mm, d11; the disc's formula holds there)
        BOUNCE_ALBEDO: 0.55,         // the walls' mean albedo in the multi-bounce: the pink tissue ~0.3 and the teeth ~0.6 by
        //                              the opening, lit by the key and the sky (at 0.30 the tongue went black under the
        //                              film's 42 deg key: h4b/face/out/diag/d04_rim.png, rim off) [E]
        LIP_MIN_MM: 8.0,             // the lips' and the mucosa's transmission path near the opening, at least (the free
        //                              margin's thickness, ~8-12 mm) [E]
        INNER_MEL: 0.6,              // the mouth's wet tissue (the sock, the lips' inner rolls): melanin x, roughness, and
        INNER_ROUGH: 0.24,           //   the share of the relief faded toward the smooth normal (0.16 drew a pin-sharp key
        //                              highlight on the lower lip's wet top, d12) [E]
        INNER_SMOOTH: 0.9,
        MUCOSA_BLOOD: 2.2,           // the HEAD's wet tissue there: the mouth zone's blood x this (a deeper red: the oral
        //                              mucosa is not keratinised; the zone's x14 rendered a saturated orange strip) [E]
        // the tongue and the gums as tissue: pigments over the skin LUT (melanin x, blood x the identity's), roughness, a
        // wrapped diffuse per channel (red scatters furthest in muscle and mucosa); the tongue one lobe between its papillae's
        // matte and its wet film (a clear coat would hand the direct light to three's model and lose the wrap).
        // The tongue at blood x40: albedo L* 51, a* 22, b* 9 (H4's x10: L* 65, a* 16, b* 7.5, a pale grey-pink that the sky's
        // reflection turned lavender); the gums x24: L* 57, a* 20, b* 8 (attached gingiva, coral) [E: checked in the renders
        // against the reference's tongue front 16 L* under the lit lower teeth]
        TONGUE: { mel: 0.03, blood: 28.0, rough: 0.42, spec: 0.8, wrap: [0.45, 0.22, 0.14] },   // x28: L* 56, a* 20, b* 8
        GUMS: { mel: 0.15, blood: 24.0, rough: 0.30, wrap: [0.35, 0.16, 0.10] },
        DEBUG: null,                 // 'vis': the parts and the masked skin show the visibility as emission (diagnostic)
    },
    // (H4b face, 11-02) THE IRIS IN ZONES (the EYES set's iris_mode 'structure': h4b/face/e01_eyetex.py keeps only the photo's
    // fine structure, each ring's luminance over its median): the colour is the identity's, by zone, as a real iris is laid
    // out: the PUPILLARY zone inside the collarette (irisInner x the colour: a hazel's golden-amber ring, a brown's darker
    // one), the CILIARY zone outside it (the colour itself), a soft LIMBAL ring darkening its outer edge and the dark
    // pupillary RUFF at the margin. H4 tinted the whole photo one hue (copper under Punchy: hue ~49 deg at chroma ~40 in
    // every zone; the photos' hazel and light brown 60-80 deg with zonal contrast, h4b/face/probes/i01_iris_photos.py).
    // COLLARETTE in t (0 the pupil's margin .. 1 the iris's edge) [Snell & Lemp: about a third of the way out];
    // LIMBAL [t from, darkening]; RUFF [width in t, its dark level]; CONTRAST the structure's power
    IRIS: { COLLARETTE: [0.24, 0.40], LIMBAL: [0.80, 0.45], RUFF: [0.05, 0.55], CONTRAST: 1.15 },
};

// ------------------------------------------------------------------------------------------------- the skin LUTs
function halfTexture(bytes, w, h) {
    const u16 = new Uint16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
    if (u16.length !== w * h * 4) throw new Error(`[human_skin] LUT: ${u16.length} halves, expected ${w * h * 4}`);
    const t = new THREE.DataTexture(new Uint16Array(u16), w, h, THREE.RGBAFormat, THREE.HalfFloatType);
    t.minFilter = THREE.LinearFilter;
    t.magFilter = THREE.LinearFilter;
    t.wrapS = THREE.ClampToEdgeWrapping;
    t.wrapT = THREE.ClampToEdgeWrapping;
    t.generateMipmaps = false;
    t.flipY = false;
    t.colorSpace = THREE.NoColorSpace;
    t.needsUpdate = true;
    return t;
}

export function skinLUT(assets) {
    // the forge's packs (lut/skin_lut_{albedo,trans,preint}.f16: float16 RGBA, rows then columns, row 0 first)
    return {
        albedo: halfTexture(assets.albedo, 64, 64),
        trans: halfTexture(assets.trans, 64, 2),
        preint: halfTexture(assets.preint, 64, 64),
    };
}

export function humanUniforms(opts = {}) {
    const U = THREE.uniform;
    const seed = opts.seed ?? 0;
    return {
        melanin: U(opts.melanin ?? 0.1045),     // f_mel0: the inner arm's (NIST median: light, ITA ~50)
        blood: U(opts.blood ?? 0.00184),        // f_blood0 (NIST median; Jacques's typical 0.2 %)
        tint: U(new THREE.Color(opts.tint ?? 0xffffff)),
        flush: U(opts.flush ?? 0.0),            // blood flow display (H7): x (1 + flush) on the blood
        // (H3b) the identity's generator options: mottle x the measured amplitudes (0 clean .. 1 the photos' adult skin);
        // freckles (0 none .. 1 the heavy cheek of the reference: 9-11 / cm2 at zone weight 1; 0.5 a typical freckled
        // face); moles, the whole-body count (12-58 means in the literature, 0 none); seed, the identity: every pattern
        // is offset by it, so two people share maps and no pattern
        mottle: U(opts.mottle ?? 1.0),
        freckles: U(opts.freckles ?? 0.0),
        moles: U(opts.moles ?? 0.0),
        seedOffset: U(new THREE.Vector3(seed * 97.13, seed * 53.71, seed * 211.37)),
        pores: U(opts.pores ?? 1.0),            // the micro relief's strength
        wet: U(opts.wet ?? 0.0),                // a whole-skin wetness (sweat, rain) over the zones' own
        // the eyes, per side (L, R): iris colour (linear), pupil diameter (mm), spiral, glow
        irisL: U(new THREE.Color(opts.irisL ?? opts.iris ?? 0x4a2a14)),
        irisR: U(new THREE.Color(opts.irisR ?? opts.iris ?? 0x4a2a14)),
        // (H4b face) the iris's PUPILLARY zone as a multiplier of its colour (inside the collarette: K.IRIS), linear, per eye
        irisInnerL: U(new THREE.Color(...(opts.irisInnerL ?? opts.irisInner ?? [1.0, 1.0, 1.0]))),
        irisInnerR: U(new THREE.Color(...(opts.irisInnerR ?? opts.irisInner ?? [1.0, 1.0, 1.0]))),
        pupil: U(opts.pupil ?? 3.6),            // mm (Lazar 2024: 3.55 at 100-1000 lux, 2.57 over 1000, 8.13 dark)
        spiral: U(opts.spiral ?? 0.0),
        eyeGlow: U(opts.eyeGlow ?? 0.0),
        t: U(0.0),
        // (H4b face) THE MOUTH'S APERTURE (K.MOUTH), world space, metres: the opening's centre, its outward unit normal, its
        // half-width and half-height; mouthOn 0 until a driver sets them (then the cavity term is off: the H4 look)
        mouthC: U(new THREE.Vector3(0, 0, 0)),
        mouthN: U(new THREE.Vector3(0, 0, 1)),
        mouthU: U(new THREE.Vector3(1, 0, 0)),      // the opening's long axis (the corners' line), in its plane
        mouthAB: U(new THREE.Vector2(0, 0)),
        mouthOn: U(0.0),
    };
}

// (H4b face) THE MOUTH'S APERTURE FROM THE LIP JOINTS (call each frame after the face's joints are posed: the face driver's
// update, then the skeleton's world matrices): the centre between the lips' centre joints, set back `back` m along the
// normal onto the inner lip line (the joints lie ~3 mm under the vermilion); the normal across the corners' line and the
// lips' opening direction, turned to face forward; the half-width from the corners (the inner lip line's ends) x kw; the
// half-height from how far the centre joints have parted beyond their rest distance (cal.d0: measured on the rest pose,
// the lips sealed): the midline opening = kh x gap - c0 (fitted on both baselines' visemes, m02's midline openings against
// the joints' gap: F 0.87 x gap - 1.2 mm from ee 0.68 to aa 1, M the same within 0.1 mm), halved.
// cal: { d0, kw, kh, c0, back } from apertureCalibration() on the rest pose.
export function apertureCalibration(vrmScene) {
    const p = (n) => vrmScene.getObjectByName(n)?.getWorldPosition(new THREE.Vector3());
    const u = p('lip_upper_C'), l = p('lip_lower_C');
    if (!u || !l) return null;
    return { d0: u.distanceTo(l), kw: 0.90, kh: 0.87, c0: 0.0012, back: 0.0012, fwd: new THREE.Vector3(0, 0, 1) };
}
export function setAperture(U, vrmScene, cal) {
    if (!cal) return;
    const g = (n, v) => vrmScene.getObjectByName(n)?.getWorldPosition(v);
    const u = g('lip_upper_C', new THREE.Vector3()), l = g('lip_lower_C', new THREE.Vector3());
    const cl = g('lip_corner_L', new THREE.Vector3()), cr = g('lip_corner_R', new THREE.Vector3());
    const head = vrmScene.getObjectByName('head');
    if (!u || !l || !cl || !cr) return;
    const across = cl.clone().sub(cr);
    const width = across.length();
    across.normalize();
    const vert = u.clone().sub(l);
    const gap = Math.max(0.0, cal.kh * (vert.length() - cal.d0) - cal.c0);     // the midline opening (m)
    vert.normalize();
    const n = new THREE.Vector3().crossVectors(across, vert).normalize();
    // forward is the head's +z (the VRM faces +z at rest)
    const fwd = cal.fwd.clone();
    if (head) fwd.applyQuaternion(head.getWorldQuaternion(new THREE.Quaternion()));
    if (n.dot(fwd) < 0) n.negate();
    const c = u.clone().add(l).multiplyScalar(0.5).addScaledVector(n, -cal.back);
    U.mouthC.value.copy(c);
    U.mouthN.value.copy(n);
    U.mouthU.value.copy(across.addScaledVector(n, -across.dot(n)).normalize());
    U.mouthAB.value.set(0.5 * width * cal.kw, 0.5 * gap + 1e-5);
    U.mouthOn.value = 1.0;
}

// (H4b face, session 2) THE MOUTH SOCK BY ITS UV ISLANDS: GNM's mouth sock (and the inner lips beside it) is its own UV
// island in the HEAD's atlas, four islands after the forge (the left and right halves of the roof's and the floor's
// sides); the masks in skinMaterial find the cavity by geometry (the wet zone, the deep interior's facing and depth
// tests), and they left the floor beside the back of the tongue, 61 mm in, sky-lit: the pale vertical sliver between the
// side teeth and the tongue at every open viseme (h4b/face/probes/p07_pick.py: HEAD tri 9166, an island of the sock).
// Each UV island (triangles joined by shared vertex indices: glTF splits the vertices at UV seams) whose rest centroid
// lies more than 12 mm behind the lips' centre joints, within 50 mm across and 35 mm up or down, and reaches no more
// than 12 mm in front of them, is the sock: a float vertex attribute 'mouthSock' (1 on it) that skinMaterial adds to the
// cavity's lighting mask (the ambient through the opening, the direct light through it, the reflection's way out), never
// to the mucosa's look (its seam is the inner lip line). Both baselines: the four islands, 526 / 526 vertices (F / M).
// Call once per mesh before its material is made; returns the count of sock vertices (0: no attribute added).
export function markMouthSock(mesh) {
    const g = mesh.geometry;
    if (!g || !g.index || !mesh.skeleton || g.attributes.mouthSock) return g?.attributes?.mouthSock ? -1 : 0;
    const bone = (n) => mesh.skeleton.bones.find((b) => b.name === n);
    const bu = bone('lip_upper_C'), bl = bone('lip_lower_C');
    if (!bu || !bl) return 0;
    bu.updateWorldMatrix(true, false);
    bl.updateWorldMatrix(true, false);
    mesh.updateWorldMatrix(true, false);
    const lc = bu.getWorldPosition(new THREE.Vector3()).add(bl.getWorldPosition(new THREE.Vector3())).multiplyScalar(0.5);
    const pos = g.attributes.position, idx = g.index.array, n = pos.count;
    const par = new Int32Array(n);
    for (let i = 0; i < n; i++) par[i] = i;
    const find = (i) => { while (par[i] !== i) { par[i] = par[par[i]]; i = par[i]; } return i; };
    const join = (a, b) => { a = find(a); b = find(b); if (a !== b) par[a] = b; };
    for (let t = 0; t < idx.length; t += 3) { join(idx[t], idx[t + 1]); join(idx[t + 1], idx[t + 2]); }
    const acc = new Map();
    const v = new THREE.Vector3();
    for (let i = 0; i < n; i++) {
        v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld).sub(lc);
        const r = find(i);
        let a = acc.get(r);
        if (!a) { a = { s: [0, 0, 0], zmax: -1e9, k: 0 }; acc.set(r, a); }
        a.s[0] += v.x; a.s[1] += v.y; a.s[2] += v.z; a.k++;
        a.zmax = Math.max(a.zmax, v.z);
    }
    const sock = new Set();
    for (const [r, a] of acc) {
        const cx = a.s[0] / a.k, cy = a.s[1] / a.k, cz = a.s[2] / a.k;
        if (cz < -0.012 && Math.abs(cx) < 0.05 && Math.abs(cy) < 0.035 && a.zmax < 0.012) sock.add(r);
    }
    if (!sock.size) return 0;
    const m = new Float32Array(n);
    let k = 0;
    for (let i = 0; i < n; i++) if (sock.has(find(i))) { m[i] = 1.0; k++; }
    g.setAttribute('mouthSock', new THREE.BufferAttribute(m, 1));
    return k;
}

// (H4b face) THE DIRECT LIGHT THROUGH THE OPENING (K.MOUTH): a light reaches a point inside the mouth only along a ray that
// leaves through the lips' opening. In VIEW space (the lighting models' lightDirection): the ray from the point toward the
// light meets the opening's plane inside the ellipse (soft over 0.85-1.15 of its radius), or the point is in front of the
// plane; a light behind the opening's plane never reaches in. The shadow map does this for a light that casts shadows,
// coarsely; a light that casts none (the films' rim) lit the inside through the head (h4b/face/out/diag/d04_rim.png).
// Float 0..1
export function apertureDirect(U, Lv) {
    const { float, vec4, smoothstep, mix, cameraViewMatrix, positionView } = THREE;
    const M = K.MOUTH;
    const Cv = cameraViewMatrix.mul(vec4(U.mouthC, 1.0)).xyz;
    const nv = cameraViewMatrix.mul(vec4(U.mouthN, 0.0)).xyz.normalize();
    const uv_ = cameraViewMatrix.mul(vec4(U.mouthU, 0.0)).xyz.normalize();
    const vv = nv.cross(uv_);
    const P = positionView;
    const ln = Lv.dot(nv);
    const t = Cv.sub(P).dot(nv).div(ln.max(1.0e-4));
    const Q = P.add(Lv.mul(t)).sub(Cv);
    const ex = Q.dot(uv_).div(U.mouthAB.x.max(1.0e-5)), ey = Q.dot(vv).div(U.mouthAB.y.max(1.0e-5));
    let D = float(1.0).sub(smoothstep(0.85, 1.15, ex.mul(ex).add(ey.mul(ey)).sqrt())).mul(smoothstep(0.0, 0.05, ln));
    D = mix(D, float(1.0), smoothstep(M.SIDE_M[0], M.SIDE_M[1], P.sub(Cv).dot(nv)));
    return mix(float(1.0), D, U.mouthOn.mul(M.ON ? 1.0 : 0.0)).clamp(0.0, 1.0);
}

// (H4b face) EACH INSIDE POINT'S VIEW OF THE OUTSIDE THROUGH THE APERTURE (K.MOUTH): P, N world (the point and its normal,
// unit); the aperture a disc of the ellipse's area seen at its own tilt; Frostbite's illuminanceSphereOrDisk (Lagarde & de
// Rousiers 2014, "Moving Frostbite to PBR", the disc's horizon handled) over pi = the share of a uniform sky the point
// receives; points in front of the opening's plane are outside (1); then the walls' inter-reflections (Jimenez et al. 2016's
// multi-bounce fit at K.MOUTH.BOUNCE_ALBEDO). Returns a float node 0..1
export function apertureVisibility(U, P, N) {
    const { float, sqrt, acos, atan, select, smoothstep, mix, max } = THREE;
    const M = K.MOUTH;
    const d = U.mouthC.sub(P);
    const dist = d.length().max(1.0e-5);
    const L = d.div(dist);
    const cosA = U.mouthN.dot(L).clamp(0.0, 1.0);                  // the opening's tilt to the point
    const r2 = U.mouthAB.x.mul(U.mouthAB.y).mul(cosA);               // the disc of the ellipse's area, projected
    const s2 = r2.div(r2.add(dist.mul(dist))).clamp(1.0e-6, 0.9999);  // sin^2 of its angular radius
    const cosT = N.dot(L).clamp(-1.0, 1.0);
    const sinT = sqrt(float(1.0).sub(cosT.mul(cosT)).max(1.0e-6));
    const x = sqrt(float(1.0).div(s2).sub(1.0));
    const y = x.negate().mul(cosT.div(sinT)).clamp(-1.0, 1.0);
    const sTy = sinT.mul(sqrt(float(1.0).sub(y.mul(y)).max(0.0)));
    const partial = cosT.mul(acos(y)).sub(x.mul(sTy)).mul(s2).add(atan(sTy.div(x.max(1.0e-6)))).max(0.0);
    const full = s2.mul(cosT.max(0.0)).mul(Math.PI);
    let V = select(cosT.mul(cosT).greaterThan(s2), full, partial).div(Math.PI).clamp(0.0, 1.0);
    // in front of the opening's plane: the outside
    const side = P.sub(U.mouthC).dot(U.mouthN);
    V = mix(V, float(1.0), smoothstep(M.SIDE_M[0], M.SIDE_M[1], side));
    // the walls' inter-reflections (Jimenez 2016, grey at the tissue's mean albedo)
    const a = 2.0404 * M.BOUNCE_ALBEDO - 0.3324, b = -4.7951 * M.BOUNCE_ALBEDO + 0.6417, c = 2.7552 * M.BOUNCE_ALBEDO + 0.6903;
    V = max(V, V.mul(a).add(b).mul(V).add(c).mul(V));
    return mix(float(1.0), V, U.mouthOn.mul(M.ON ? 1.0 : 0.0)).clamp(0.0, 1.0);
}

// (H4b face) THE ENVIRONMENT'S REFLECTION INSIDE THE MOUTH: does the reflected view ray leave through the opening? A grazing
// look at the tongue's top reflects the palate, not the sky (the first after-render, h4b/face/out/diag/d02_a1_vs_h4_F.png:
// a lavender sky sheen on a tongue the cosine-weighted visibility had already darkened, since three's specular occlusion
// is only the AO). The reflection direction against the opening's disc (its angular radius from the same disc as
// apertureVisibility), widened by the lobe's spread (rough x LOBE_RAD); 1 in front of the opening's plane. Float 0..1
export function apertureSpecVis(U, P, N, rough) {
    const { float, sqrt, asin, cos, min, smoothstep, mix, reflect, normalize, cameraPosition } = THREE;
    const M = K.MOUTH;
    const R = reflect(normalize(P.sub(cameraPosition)), N);
    const d = U.mouthC.sub(P);
    const dist = d.length().max(1.0e-5);
    const L = d.div(dist);
    const cosA = U.mouthN.dot(L).clamp(0.0, 1.0);
    const r2 = U.mouthAB.x.mul(U.mouthAB.y).mul(cosA);
    const s2 = r2.div(r2.add(dist.mul(dist))).clamp(1.0e-6, 0.9999);
    const alpha = asin(sqrt(s2));
    const spread = float(rough).mul(M.LOBE_RAD ?? 0.8);
    let S = smoothstep(cos(min(alpha.add(spread), float(1.55))), cos(alpha.mul(0.5)), R.dot(L));
    const side = P.sub(U.mouthC).dot(U.mouthN);
    S = mix(S, float(1.0), smoothstep(M.SIDE_M[0], M.SIDE_M[1], side));
    return mix(float(1.0), S, U.mouthOn.mul(M.ON ? 1.0 : 0.0)).clamp(0.0, 1.0);
}

// --------------------------------------------------------------------------------------- the skin lighting model
// (H3b) THE SHADOW MAP READ AT OTHER POINTS. three r184's ShadowNode cannot be re-sampled elsewhere in one shader: its
// setup() re-assigns a single shared shadowPositionWorld but returns one filter graph built once (this._node), and
// isolate()'s cache falls back to the parent's, so every lightNode.shadowNode.isolate().context({ shadowPositionWorld })
// reads the first result. The skin's dumped WGSL showed it (h3b/material/engine/*_skin_frag.wgsl, 16:48): ONE
// shadowPositionWorld assignment and 16 compares however many taps (with setParent(false) the taps' assignments appear,
// still 16 compares). So H3's transmission back-face test never ran either: the back took the front's own shadow.
// This builds the lookup as ShadowNode.setupShadowCoord / setupShadowFilter do (the light's shadow matrix uniform, its
// bias, normal bias and intensity, the frustum test, the renderer's filter) on the depth texture ShadowNode made
// (light.shadow.map). Called at BUILD time (inside an Fn), after the light's own shadow has been set up in the same
// build; null before that (the caller falls back to the plain shadow).
// coarse: one hardware compare (under PCF and PCFSoft maps the depth texture's comparison sampler is linear, so that is already
// a 2 x 2 PCF) instead of the renderer's filter, for a reading that is averaged again or sits behind tissue anyway
function shadowLookup(lightNode, builder, coarse = false) {
    const light = lightNode && lightNode.light, shadow = light && light.shadow;
    const map = shadow && shadow.map;
    if (!map || !map.depthTexture) return null;
    const { reference, renderGroup, lightShadowMatrix, normalWorld, vec3, vec4, float, mix } = THREE;
    const full = shadow.filterNode || ({
        [THREE.BasicShadowMap]: THREE.BasicShadowFilter, [THREE.PCFShadowMap]: THREE.PCFShadowFilter,
        [THREE.PCFSoftShadowMap]: THREE.PCFSoftShadowFilter })[builder.renderer.shadowMap.type];
    if (!full) return null;                                     // VSM samples another texture: not handled
    const filter = coarse && !shadow.filterNode ? THREE.BasicShadowFilter : full;
    const bias = shadow.biasNode || reference('bias', 'float', shadow).setGroup(renderGroup);
    const nBias = reference('normalBias', 'float', shadow).setGroup(renderGroup);
    const inten = reference('intensity', 'float', shadow).setGroup(renderGroup);
    const M = lightShadowMatrix(light);
    const rev = !!builder.renderer.reversedDepthBuffer;
    return (P) => {
        const sp = M.mul(vec4(P.add(normalWorld.mul(nBias)), 1.0));
        const c = sp.xyz.div(sp.w);
        const coord = vec3(c.x, c.y.oneMinus(), rev ? c.z.sub(bias) : c.z.add(bias));
        const inside = coord.x.greaterThanEqual(0.0).and(coord.x.lessThanEqual(1.0))
            .and(coord.y.greaterThanEqual(0.0)).and(coord.y.lessThanEqual(1.0)).and(coord.z.lessThanEqual(1.0));
        const s = inside.select(filter({ depthTexture: map.depthTexture, shadowCoord: coord, shadow }), float(1.0));
        return mix(1.0, s, inten);
    };
}

class SkinLightingModel extends THREE.PhysicalLightingModel {
    direct({ lightDirection, lightColor, lightNode, reflectedLight }, builder) {
        const S = builder.material.skin;
        if (!S) { super.direct({ lightDirection, lightColor, lightNode, reflectedLight }, builder); return; }
        // (r184's public TSL exports leave out diffuseContribution / specularColorBlended: the skin passes its own
        // diffuse (the colour node; metalness 0) and its F0 (the ior's) in S)
        const { vec2, vec3, float, mix, texture, exp, normalView, normalViewGeometry, positionViewDirection,
            roughness, BRDF_GGX, specularColor, specularF90 } = THREE;
        const diffuseContribution = S.diffuse;
        const L = lightDirection;
        // (H4b face) the mouth's wet tissue (S.mouthMask): only the light through the lips' opening (apertureDirect), on the
        // specular, the diffuse in every shadow branch and the transmission alike
        const mD = S.mouthDirectFn ? mix(float(1.0), S.mouthDirectFn(L), S.mouthMask) : null;
        if (mD) lightColor = lightColor.mul(mD);
        const baseLight = lightNode && lightNode.baseColorNode ? (mD ? lightNode.baseColorNode.mul(mD) : lightNode.baseColorNode)
            : null;
        // the smooth surface's normal: the geometry's on the stand-in clay; on the textured LOW the forge's MACRO bake
        // (the high's shape without the T tier), since a level-0 LOW's own interpolated normal is not the surface (its
        // facet normals turn p50 1.8, p99 18 deg from the clay's: forge NOTES p31) and the red channel's diffuse took
        // 55 % of it
        const nG = S.nGeo || normalViewGeometry;
        const nD = normalView;
        // PRE-INTEGRATED DIFFUSE, per channel at its own normal. (H3b) ONLY WHERE THE TWO NORMALS AGREE: in the lip seam the
        // bake's fallback texels leave the macro and detail normals far apart, red (45 % macro) fell past the terminator
        // while green and blue stayed lit, and the seam showed a dark teal sliver (sRGB 7, 28, 30, in H3 too; found at the
        // mole's macro; 'nopre' cleared it, teeth, gums, tongue, tone map and transmission did not). Blurring a channel's
        // normal is a model of scattering round a smooth surface, so it fades out where there is no smooth surface to scatter
        // round; everywhere else agree = 1 and this is the same lookup
        const agree = THREE.smoothstep(0.25, 0.75, nG.dot(nD));
        const ndl = (w) => mix(nD, mix(nG, nD, w), agree).normalize().dot(L).mul(0.5).add(0.5);
        const y = S.curv;
        // the shadow's PENUMBRA scatters too: light entering the skin on the lit side of a shadow edge leaves it on the
        // shadow side, red furthest. (H3b) THE SCATTERED SHADOW (K.SHADOW_SCATTER's note): the shadow map read at taps
        // on the tangent plane (shadowLookup), mixed per channel by weights fitted to the exact scattered edge. Each tap
        // is a full PCF lookup, so the result is as smooth as the shadow map's own filter and reaches past the
        // penumbra's dark end (where the exact edge's red tail lies) with no step
        let diffLight = lightColor;
        const hasShadow = !!(lightNode && lightNode.baseColorNode && lightNode.shadowNode);
        // THE SPECULAR FIRST (below): its lightColor builds the light's own shadow, so the shadow map exists when the
        // scattered shadow's Fn runs in the same build (shadowLookup's note)
        const dotNL = nD.dot(L).clamp();
        // (H3b integrator) the micro-shadow (K.MICRO_SHADOW's note), on the direct diffuse and specular alike: the macro
        // normal's N.L, the AO remapped to the crease's scale
        const aoMS = K.MICRO_SHADOW && S.aoDirect ? THREE.smoothstep(K.MICRO_SHADOW_AO[0], K.MICRO_SHADOW_AO[1], S.aoDirect)
            : null;
        const ms = aoMS ? nG.dot(L).abs().add(aoMS.mul(aoMS).mul(2.0)).sub(1.0).clamp() : null;
        const r0 = roughness.mul(K.LOBE0).clamp(0.045, 1.0);
        const r1 = roughness.mul(K.LOBE1).clamp(0.045, 1.0);
        // DUAL-LOBE SPECULAR. (H3b, the r184 trap) f0 and f90 are the material's own specular inputs, as the
        // environment's lobe reads them (PhysicalLightingModel.computeMultiscattering: specularColor, specularF90), no
        // longer a private f0 with f90 = 1: three's own direct() hard-codes f90 = 1 (PhysicalLightingModel.js:626), so
        // a specularIntensity below 1 (a matte powder, a crossbreed underwater: the axolotl's relative ior 1.035) left
        // every light's grazing lobe at full Fresnel. At ior 1.4 and intensity 1 this is the same lobe as H3's
        const f90 = K.F90_HONOUR ? specularF90 : float(1.0);      // (false: the trap, for the before / after only)
        const spec = BRDF_GGX({ lightDirection: L, f0: specularColor, f90, roughness: r0 })
            .mul(K.LOBE_MIX).add(BRDF_GGX({ lightDirection: L, f0: specularColor, f90,
                roughness: r1 }).mul(1.0 - K.LOBE_MIX));
        reflectedLight.directSpecular.addAssign(ms ? dotNL.mul(lightColor).mul(spec).mul(ms) : dotNL.mul(lightColor).mul(spec));
        if (K.SHADOW_SCATTER && hasShadow) {
            const SS = K.SHADOW_SCATTER;
            diffLight = THREE.Fn((_, builder) => {
                const at = shadowLookup(lightNode, builder, SS.COARSE);
                if (!at) {
                    console.warn('[human_skin] the shadow map is not set up yet in this build: a plain penumbra');
                    return lightColor;
                }
                const { positionWorld, normalWorldGeometry, select } = THREE;
                const n = normalWorldGeometry;
                // a tangent frame from the geometric normal, continuous everywhere but at n = -z (Duff et al. 2017,
                // "Building an Orthonormal Basis, Revisited", JCGT 6(1)): the taps' pattern never jumps across the skin
                const sg = select(n.z.greaterThanEqual(0.0), float(1.0), float(-1.0));
                const a = float(-1.0).div(sg.add(n.z));
                const b = n.x.mul(n.y).mul(a);
                const T = vec3(float(1.0).add(sg.mul(n.x).mul(n.x).mul(a)), sg.mul(b), sg.negate().mul(n.x));
                const B = vec3(b, sg.add(n.y.mul(n.y).mul(a)), n.y.negate());
                const ringMean = ([rMM, m, phase]) => {
                    const r = rMM * 1e-3, lift = (rMM * rMM) / (2.0 * SS.CONCAVE_MM) * 1e-3;
                    let acc = null;
                    for (let j = 0; j < m; j++) {
                        const ang = phase + 2.0 * Math.PI * j / m;
                        const sj = at(positionWorld.add(T.mul(r * Math.cos(ang)).add(B.mul(r * Math.sin(ang)))
                            .add(n.mul(lift))));
                        acc = acc ? acc.add(sj) : sj;
                    }
                    return acc.mul(1.0 / m);
                };
                const s0 = vec3(lightNode.shadowNode).x;
                const s1 = ringMean(SS.RINGS[0]), s2 = ringMean(SS.RINGS[1]);
                // the rings' share fades in cavities (SS.AO's note): the centre takes it back, so the sum stays 1
                const g = SS.AO ? THREE.smoothstep(SS.AO[0], SS.AO[1], S.ao) : float(1.0);
                const ch = (w) => s0.add(s1.sub(s0).mul(g.mul(w[1]))).add(s2.sub(s0).mul(g.mul(w[2])));
                return baseLight.mul(vec3(ch(SS.W[0]), ch(SS.W[1]), ch(SS.W[2])));       // (H4b face) baseLight
            })();
        } else if (K.PENUMBRA && hasShadow) {
            // H3's per-channel power of the filtered shadow (the before, for comparisons: the scene's 'oldpen')
            const sv = vec3(lightNode.shadowNode);
            diffLight = baseLight.mul(vec3(sv.x.pow(K.PENUMBRA[0]), sv.y.pow(K.PENUMBRA[1]),       // (H4b face) baseLight
                sv.z.pow(K.PENUMBRA[2])));
        }
        let D;
        if (K.PREINT) {
            const dR = texture(S.lut.preint, vec2(ndl(K.DIFF_NORMAL[0]), y)).r;
            const dG = texture(S.lut.preint, vec2(ndl(K.DIFF_NORMAL[1]), y)).g;
            const dB = texture(S.lut.preint, vec2(ndl(K.DIFF_NORMAL[2]), y)).b;
            D = vec3(dR, dG, dB);
        } else {
            D = vec3(nD.dot(L).clamp());
        }
        reflectedLight.directDiffuse.addAssign(ms ? diffLight.mul(D).mul(diffuseContribution).mul(ms).mul(1.0 / Math.PI)
            : diffLight.mul(D).mul(diffuseContribution).mul(1.0 / Math.PI));
        // TRANSMISSION through thin tissue: the light at the back face (its shadow tested there), the LUT's
        // transmittance E^2 exp(-k t), a diffuse exit plus a forward lobe toward the light
        if (!K.TRANS) return;
        let backLight = lightColor;
        if (lightNode && lightNode.baseColorNode) {
            backLight = baseLight;                  // (H4b face) the opening's share on the mouth's wet tissue
            if (K.TRANS_SHADOW && lightNode.shadowNode) {
                const { positionWorld, normalWorldGeometry } = THREE;
                // just PAST the back face, toward the light (a point on it or inside reads as shadowed by its own
                // surface: the first back-lit look's ear glowed only at the rim)
                const pBack = positionWorld.sub(normalWorldGeometry.mul(S.thickM.add(K.TRANS_PAST_MM * 1e-3)
                    .min(K.TRANS_MAX_MM * 1e-3)));
                // (H3b) read through shadowLookup: H3's lightNode.shadowNode.isolate().context({ shadowPositionWorld:
                // pBack }) compiled to the FRONT's own shadow (shadowLookup's note), so the back face was never tested
                // ('oldtrans' brings the H3 form back for comparisons)
                if (K.TRANS_LOOKUP) {
                    backLight = THREE.Fn((_, builder) => {
                        const at = shadowLookup(lightNode, builder, K.TRANS_COARSE);
                        return at ? baseLight.mul(at(pBack)) : lightColor;          // (H4b face) baseLight
                    })();
                } else {
                    backLight = baseLight.mul(lightNode.shadowNode.isolate()          // (H4b face) baseLight
                        .context({ shadowPositionWorld: pBack }));
                }
            }
        }
        const E = texture(S.lut.trans, vec2(S.uMel, 0.25)).rgb;
        const k = texture(S.lut.trans, vec2(S.vBlood, 0.75)).rgb;
        // (H4b face) the lips' and the mouth's tissue near the opening: the transmission's path at least LIP_MIN_MM (the bake
        // measured the thickness with the mouth closed, so the inner roll's "other side" was the opposite lip, ~0 mm away,
        // and the key came through the open upper lip at full strength: the H4 film's saturated red-orange strip,
        // h4b/face/out/diag/d05_strip.png)
        const thick = S.lipMask ? S.thickMM.max(S.lipMask.mul(K.MOUTH.LIP_MIN_MM)) : S.thickMM;
        const T = E.mul(E).mul(exp(k.mul(thick).negate()));
        const back = nG.negate().dot(L).mul(0.5).add(0.5).clamp().pow(2.0);
        const fwd = positionViewDirection.dot(L.add(nG.mul(0.2)).normalize().negate()).clamp().pow(4.0);
        reflectedLight.directDiffuse.addAssign(backLight.mul(T).mul(back.mul(1.0 / Math.PI).add(fwd.mul(K.TRANS_FWD))));
    }

    // (H3b) THE AMBIENT OCCLUSION, per channel on the diffuse (K.AO_BOUNCE's note); the specular's is three's own
    ambientOcclusion(builder) {
        const S = builder.material.skin;
        if (!S || !K.AO_BOUNCE) { super.ambientOcclusion(builder); return; }
        const { ambientOcclusion, reflectedLight } = builder.context;
        const { normalView, positionViewDirection, roughness, vec3 } = THREE;
        const dotNV = normalView.dot(positionViewDirection).clamp();
        const aoNV = dotNV.add(ambientOcclusion);
        const aoExp = roughness.mul(-16.0).oneMinus().negate().exp2();
        const aoSpec = ambientOcclusion.sub(aoNV.pow(aoExp).oneMinus()).clamp();
        const x = ambientOcclusion, rho = S.diffuse;
        const a = rho.mul(2.0404).sub(0.3324), b = rho.mul(-4.7951).add(0.6417), c = rho.mul(2.7552).add(0.6903);
        const bounce = a.mul(x).add(b).mul(x).add(c).mul(x).max(vec3(x));
        reflectedLight.indirectDiffuse.mulAssign(bounce);
        // (H4b face) inside the mouth the reflection sees the outside only through the opening (apertureSpecVis)
        reflectedLight.indirectSpecular.mulAssign(S.specVis ? aoSpec.mul(S.specVis) : aoSpec);
    }
}

// (H3b) THE r184 TRAPS, for every human material:
//  * three r184's MeshPhysicalNodeMaterial.setupSpecular reads the plain specularIntensity / specularColor properties
//    and never the declared specularIntensityNode / specularColorNode (the axolotl's finding): honoured here, scaling
//    the environment's lobe and (through specularColor / specularF90) every direct lobe alike;
//  * its direct() hard-codes f90 = 1 (PhysicalLightingModel.js:626): the skin's model and HumanLightingModel below
//    pass specularF90;
//  * its sheen lobe's visibility term V_Neubelt = 1 / (4 (N.L + N.V - N.L N.V)) has no floor (inf x 0 = NaN where both
//    reach 0: M2c's black slivers): no human material takes three's sheen path (useSheen is never passed on); a sheen
//    a human needs is drawn by its own model with N.V and N.L floored at 1e-3 (sheenLobe below).
function honourSpecularNodes(m) {
    if (!m.specularIntensityNode && !m.specularColorNode) return;
    const { float, vec3, min, pow2, mix, materialSpecularIntensity, materialSpecularColor, ior, specularColor,
        specularF90, metalness } = THREE;
    const si = m.specularIntensityNode ? float(m.specularIntensityNode) : materialSpecularIntensity;
    const sc = m.specularColorNode ? vec3(m.specularColorNode) : materialSpecularColor;
    specularColor.assign(min(pow2(ior.sub(1.0).div(ior.add(1.0))).mul(sc), vec3(1.0)).mul(si));
    specularF90.assign(mix(si, 1.0, metalness));
}

// a Charlie sheen lobe (Estevez & Kulla 2017, three's D_Charlie) with a FLOORED visibility (Neubelt & Pettineo 2013):
// N.L and N.V at least 1e-3, so the term stays finite at the silhouette's terminator (three's has no floor)
export function sheenLobe(nrm, L, V, sheenRough) {
    const { float } = THREE;
    const dotNL = nrm.dot(L).max(1e-3), dotNV = nrm.dot(V).max(1e-3);
    const dotNH = nrm.dot(L.add(V).normalize()).clamp();
    const alpha = float(sheenRough).max(0.07).pow2();
    const invA = float(1.0).div(alpha);
    const sin2h = dotNH.pow2().oneMinus().max(0.0078125);
    const D = invA.add(2.0).mul(sin2h.pow(invA.mul(0.5))).div(2.0 * Math.PI);
    const Vis = float(1.0).div(dotNL.add(dotNV).sub(dotNL.mul(dotNV)).mul(4.0));
    return D.mul(Vis);
}

class SkinNodeMaterial extends THREE.MeshPhysicalNodeMaterial {
    static get type() { return 'HumanSkinNodeMaterial'; }
    constructor(params) { super(params); this.skin = null; }
    setupLightingModel() {
        return new SkinLightingModel(false, false, false, false, false, false);
    }
    setupSpecular() {
        super.setupSpecular();
        honourSpecularNodes(this);
    }
}

// the multi-scattering GGX of three r184's direct light (BRDF_GGX_Multiscatter.js, Turquin's compensation, not
// exported), its f90 an input instead of 1
function ggxMultiscatter({ lightDirection, f0, f90, roughness: rgh }) {
    const { float, normalView, positionViewDirection, BRDF_GGX, DFGLUT } = THREE;
    const single = BRDF_GGX({ lightDirection, f0, f90, roughness: rgh });
    const dotNL = normalView.dot(lightDirection).clamp();
    const dotNV = normalView.dot(positionViewDirection).clamp();
    const dfgV = DFGLUT({ roughness: rgh, dotNV });
    const dfgL = DFGLUT({ roughness: rgh, dotNV: dotNL });
    const fV = f0.mul(dfgV.x).add(f90.mul(dfgV.y)), fL = f0.mul(dfgL.x).add(f90.mul(dfgL.y));
    const emsV = float(1.0).sub(dfgV.x.add(dfgV.y)), emsL = float(1.0).sub(dfgL.x.add(dfgL.y));
    const favg = f0.add(f0.oneMinus().mul(0.047619));
    const fms = fV.mul(fL).mul(favg).div(float(1.0).sub(emsV.mul(emsL).mul(favg).mul(favg)).add(1e-6));
    return single.add(fms.mul(emsV.mul(emsL)));
}

// the eyes' and mouth parts' lighting: three's PhysicalLightingModel with its direct light's f90 = specularF90 (the
// trap above); at the defaults (specularIntensity 1, so f90 1) it is three's own direct light exactly
class HumanLightingModel extends THREE.PhysicalLightingModel {
    direct({ lightDirection, lightColor, reflectedLight }, builder) {
        if (this.clearcoat || this.iridescence || this.anisotropy) {
            super.direct({ lightDirection, lightColor, reflectedLight }, builder);
            return;
        }
        const { normalView, diffuseColor, metalness, specularColor, specularF90, roughness, BRDF_Lambert, mix, vec3 } = THREE;
        // (H4b face) the mouth's parts: the light that reaches them through the lips' opening (apertureDirect)
        if (this.mouthDirectFn) lightColor = lightColor.mul(this.mouthDirectFn(lightDirection));
        const irradiance = normalView.dot(lightDirection).clamp().mul(lightColor);
        // (H4b face) a WRAPPED diffuse per channel for the mouth's soft tissue (this.wrapRGB, from the material): light
        // reaches past the terminator by the channel's scattering, red furthest, (N.L + w) / (1 + w), energy kept by the
        // 1 / (1 + w); the specular keeps the plain N.L
        const dIrr = this.wrapRGB ? normalView.dot(lightDirection).add(vec3(...this.wrapRGB))
            .div(vec3(...this.wrapRGB.map((w) => 1.0 + w))).clamp(0.0, 1.0).mul(lightColor) : irradiance;
        reflectedLight.directDiffuse.addAssign(dIrr.mul(BRDF_Lambert({
            diffuseColor: diffuseColor.rgb.mul(metalness.oneMinus()) })));
        reflectedLight.directSpecular.addAssign(irradiance.mul(ggxMultiscatter({ lightDirection,
            f0: mix(specularColor, diffuseColor.rgb, metalness), f90: specularF90, roughness })));
    }

    // (H4b face) the environment's reflection inside the mouth: three's own occlusion, then the material's specVis (the
    // reflected ray through the lips' opening, apertureSpecVis) on the indirect specular alone
    ambientOcclusion(builder) {
        super.ambientOcclusion(builder);
        const sv = builder.material && builder.material.specVis;
        if (sv) builder.context.reflectedLight.indirectSpecular.mulAssign(sv);
    }
}

class HumanPhysicalNodeMaterial extends THREE.MeshPhysicalNodeMaterial {
    static get type() { return 'HumanPhysicalNodeMaterial'; }
    setupLightingModel() {
        // useSheen never passed on (the trap above)
        const lm = new HumanLightingModel(this.useClearcoat, false, this.useIridescence, this.useAnisotropy,
            this.useTransmission, this.useDispersion);
        lm.wrapRGB = this.wrapRGB || null;          // (H4b face) the mouth's tissue: a wrapped diffuse per channel
        lm.mouthDirectFn = this.mouthDirectFn || null;   // (H4b face) the mouth's parts: the direct light through the opening
        return lm;
    }
    setupSpecular() {
        super.setupSpecular();
        honourSpecularNodes(this);
    }
}

// --------------------------------------------------------------------------------------------- the micro relief
function microRelief(pmm, strength) {
    // pores (pits at the cells' centres) and the primary-line network (furrows along the Voronoi edges), mm. The
    // furrows are SOFT and BROKEN: a wide rounded profile (squared smoothstep over 0.35 of a cell), its depth wandering
    // along the line (the first close-up's crisp 0.1-wide lines read as craquelure, white-edged in the specular)
    const { vec3, float, smoothstep, mx_worley_noise_vec2, mx_noise_float } = THREE;
    const wp = mx_worley_noise_vec2(pmm.div(K.PORE_CELL_MM), 0.85);
    const pore = smoothstep(0.30, 0.06, wp.x);
    const wl = mx_worley_noise_vec2(pmm.div(K.LINE_CELL_MM).add(vec3(17.0, 3.0, 11.0)), 0.9);
    const f0 = smoothstep(0.35, 0.0, wl.y.sub(wl.x));
    const brk = mx_noise_float(pmm.div(0.9)).mul(0.5).add(0.5).clamp(0.0, 1.0);
    const furrow = f0.mul(f0).mul(brk.mul(0.7).add(0.3));
    const grain = mx_noise_float(pmm.div(0.18)).mul(0.25);
    return pore.mul(-K.PORE_DEPTH_MM).add(furrow.mul(-K.LINE_DEPTH_MM)).add(grain.mul(0.006)).mul(strength);
}

function bumpFromHeight(hM, nBase = null) {
    // Mikkelsen's surface gradient from the height's own screen derivatives (listing 1), view space; nBase: the normal
    // it perturbs (the textured path's normal-mapped one; the geometry's by default)
    const { positionView, normalView, faceDirection } = THREE;
    const dHdx = hM.dFdx(), dHdy = hM.dFdy();
    const sx = positionView.dFdx(), sy = positionView.dFdy();
    const n = nBase || normalView;
    const r1 = sy.cross(n), r2 = n.cross(sx);
    const det = sx.dot(r1).mul(faceDirection);
    const grad = det.sign().mul(r1.mul(dHdx).add(r2.mul(dHdy)));
    return det.abs().mul(n).sub(grad).normalize();
}

// ---------------------------------------------------------------------------------- (H3b) the skin's runtime variation
// a periodic volume of band-limited noise: four independent channels of white noise blurred by a Gaussian (sigma 1.4
// texels, wrapping), each normalised to unit variance and stored as 0.5 + n / 6. Generated once per page, 1 MB, ~50 ms;
// read trilinear at the layers' scales, each rotated so its lattice's axes never line up with the body's
let _noiseVol = null;
function noiseVolume(size = 64, seed = 90210) {
    if (_noiseVol) return _noiseVol;
    const n = size * size * size;
    const data = new Uint8Array(n * 4);
    let s = seed >>> 0;
    const rnd = () => {        // mulberry32
        s = (s + 0x6D2B79F5) >>> 0;
        let t = Math.imul(s ^ (s >>> 15), 1 | s);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const sig = 1.4, kr = Math.ceil(sig * 3);
    const k = new Float32Array(2 * kr + 1);
    let ks = 0;
    for (let i = -kr; i <= kr; i++) { k[i + kr] = Math.exp(-0.5 * (i / sig) ** 2); ks += k[i + kr]; }
    for (let i = 0; i < k.length; i++) k[i] /= ks;
    const wrap = (i) => (i + size) % size;
    let a = new Float32Array(n), b = new Float32Array(n);
    const steps = [1, size, size * size];
    for (let ch = 0; ch < 4; ch++) {
        for (let i = 0; i < n; i++) a[i] = rnd() - 0.5;
        for (const st of steps) {
            for (let z = 0; z < size; z++) for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
                const c = st === 1 ? x : st === size ? y : z;
                const base = x + y * size + z * size * size - c * st;
                let acc = 0;
                for (let j = -kr; j <= kr; j++) acc += a[base + wrap(c + j) * st] * k[j + kr];
                b[x + y * size + z * size * size] = acc;
            }
            [a, b] = [b, a];
        }
        let m = 0, v = 0;
        for (let i = 0; i < n; i++) m += a[i];
        m /= n;
        for (let i = 0; i < n; i++) v += (a[i] - m) ** 2;
        v = Math.sqrt(v / n);
        for (let i = 0; i < n; i++) {
            data[i * 4 + ch] = Math.max(0, Math.min(255, Math.round(255 * (0.5 + (a[i] - m) / v / 6.0))));
        }
    }
    const t = new THREE.Data3DTexture(data, size, size, size);
    t.format = THREE.RGBAFormat;
    t.type = THREE.UnsignedByteType;
    t.minFilter = THREE.LinearFilter;
    t.magFilter = THREE.LinearFilter;
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.wrapR = THREE.RepeatWrapping;
    t.generateMipmaps = false;
    t.colorSpace = THREE.NoColorSpace;
    t.unpackAlignment = 1;
    t.needsUpdate = true;
    _noiseVol = t;
    return t;
}

// three fixed rotations (axis-angle), one per layer: applied to the bind pose before the lattice
const ROTS = [[0.35, 0.78, 0.52, 0.9], [-0.61, 0.33, 0.72, 1.7], [0.48, -0.55, 0.68, 2.6], [0.71, 0.29, -0.64, 0.55]];
function rotated(p, i) {
    const m = new THREE.Matrix3().setFromMatrix4(new THREE.Matrix4().makeRotationAxis(
        new THREE.Vector3(ROTS[i][0], ROTS[i][1], ROTS[i][2]).normalize(), ROTS[i][3]));
    return THREE.mat3(m).mul(p);
}

// the mottling and the edge noise: unit-variance channels of the volume at a layer's scale (mm per texel)
function volNoise(pmm, seedOffset, layer, mmPerTexel, size = 64) {
    const { texture3D } = THREE;
    const q = rotated(pmm.add(seedOffset), layer).div(mmPerTexel * size);
    return texture3D(noiseVolume(size), q).sub(0.5).mul(6.0);
}

// one spot layer: the bind pose rotated, one cell, one candidate. pmm in mm, cell mm; gateP(hash) -> its existence in
// [0, 1] for this candidate; R [min, max] radii (ball, mm). Returns { mask, s } (s: the spot's hashed strength 0..1)
function spotLayer(pmm, seed, layer, cell, Rr, gate, fw, edge, edgeMM = 0.11) {
    const { vec3, float, smoothstep, mx_cell_noise_float, fract } = THREE;
    const q = rotated(pmm.add(seed), layer).div(cell);
    const c = q.floor(), f = q.sub(c);
    const h0 = mx_cell_noise_float(c);
    const h1 = mx_cell_noise_float(c.add(vec3(37.0, 17.0, 59.0)));
    const h2 = fract(h1.mul(113.37)), h3 = fract(h1.mul(271.91)), h4 = fract(h0.mul(419.73)), h5 = fract(h0.mul(733.17));
    // the radius log-uniform (a ball's section reads ~pi / 4 of its diameter: the photos' median d 0.96 mm, p90 2.5)
    const R = float(Rr[0]).mul(float(Rr[1] / Rr[0]).pow(h4));
    const m = R.div(cell);
    const centre = vec3(h1, h2, h3).mul(m.mul(2.0).oneMinus()).add(m);
    const d = f.sub(centre).length().mul(cell);
    // the rim: rough, at most ~0.12 mm, with a soft edge EDGE_MM wide (the photo at the same scale: a ramp scaled with R read
    // as a halo round a disc; 0.05 mm read as a leaf cut out and stuck on); below ~2 px it blurs, and an under-sampled spot
    // keeps its average: amplitude x (R / footprint)^2 instead of a crawling dot
    const w = fw.max(edgeMM);
    const dd = d.add(edge.mul(R.mul(0.22).min(0.12)));
    const amp = R.div(fw.mul(1.2)).pow2().min(1.0);
    const mask = smoothstep(R.add(w), R.sub(w.mul(1.5)), dd).mul(amp).mul(smoothstep(h0, h0.add(0.012), gate));
    return { mask, s: h5, R, d };
}

// ------------------------------------------------------------------------------------------------- the skin node
// the textured glb's packs (h3/integrate/i02_glb.py: each in a standard slot): every one is DATA (no sRGB decode: the
// loader marks the emissive slot sRGB) and anisotropically filtered
function dataMaps(src) {
    for (const t of [src.normalMap, src.clearcoatNormalMap, src.emissiveMap, src.thicknessMap, src.aoMap]) {
        if (t) { t.colorSpace = THREE.NoColorSpace; t.anisotropy = K.ANISOTROPY; t.needsUpdate = true; }
    }
}

export function skinMaterial(src, U, lut, opts = {}) {
    const { attribute, uv, vec2, vec3, vec4, float, texture, mix, smoothstep, exp2, sqrt, positionGeometry, fwidth,
        normalView, normalMap } = THREE;
    const m = new SkinNodeMaterial();
    // THE TEXTURED PATH (the H3 integrator, 10-30): the glb carries the forge's bakes and the packs per texel, in the
    // standard slots i02_glb.py writes: PIGMENT in the emissive map, SURFACE in the volume's thickness map, AUX in the
    // occlusion map, the composed normal (the macro bake + the T tier on the HEAD) as the normal map and the MACRO
    // normal (the high's shape alone) in the clear coat's normal slot. Texture reads stay inside [0, 1] by themselves.
    // Without them, the stand-in's vertex attributes, each CLAMPED to its stored [0, 1] as it is read: under MSAA an
    // edge pixel shades at its centre even where that lies outside the triangle, so the varyings EXTRAPOLATE, and a
    // slightly negative thickness at a silhouette made exp(-k t) overflow; the harness's half-float post target turned
    // it into Inf, then NaN, and its bloom and SSR spread the NaN over the whole frame (found 10-30 by bisecting the
    // terms: m03_variants.sh)
    const TEX = !!(src && src.emissiveMap && src.thicknessMap && src.aoMap && src.normalMap);
    let pig, surf, aux, nDetail = null, nMacro = null, varMap = float(0.0), aoMS = null;
    if (TEX) {
        dataMaps(src);
        const st = uv();
        // (H3b integrator) the micro-shadow's AO, read coarser: the bake's AO is 24 rays a texel, and the micro-shadow's
        // steep remap turned that ray noise into a stipple round the cleft (the second A / B). A mip BIAS alone does nothing
        // under magnification (the eye macro sits ~4 levels below mip 0, so +2.5 still read mip 0 and the lid margin went
        // blotchy: the eye A / B, 19:3x), so the level is explicit: this pixel's own isotropic level + MICRO_SHADOW_BIAS,
        // and never finer than MICRO_SHADOW_LOD_MIN (a ~6-texel blur of the AO, at every distance)
        if (K.MICRO_SHADOW) {
            const tsz = float(src.aoMap.image?.width ?? 4096);
            const ex = st.dFdx().mul(tsz), ey = st.dFdy().mul(tsz);
            const lod = THREE.log2(ex.dot(ex).max(ey.dot(ey)).max(1.0e-8)).mul(0.5);
            aoMS = texture(src.aoMap, st).level(lod.add(K.MICRO_SHADOW_BIAS).max(K.MICRO_SHADOW_LOD_MIN)).r;
        }
        // the packs are RGB with NO DATA IN ALPHA (the engine's Deno decoder, under three's premultiplyAlpha 'none',
        // un-premultiplies straight-alpha PNGs: RGB x 255 / A; the first textured render read every texel whose alpha
        // held a value as maximum melanin) and two channels FOLDED at pack time (h3/integrate/i01_packs.py): rebuilt
        // here in the stand-in's layout so the code below reads one meaning. The curvature carries its tissue scale
        // already (the tissue below is the neutral TISSUE_REF: factor 1) and the roughness mip 0's sub-texel normal
        // variance (the forge's nlen over the T tier's 4 x 4 sub-normals: (r^4 + var)^(1/4))
        const pT = texture(src.emissiveMap, st), sT = texture(src.thicknessMap, st), aT = texture(src.aoMap, st);
        pig = vec4(pT.rgb, aT.b);
        surf = vec4(sT.rgb, aT.g);
        aux = vec4(aT.r, float(K.TISSUE_REF / K.TISSUE_MAX), 0.0, 0.0);
        const nt = texture(src.normalMap, st);
        nDetail = normalMap(nt);
        if (src.clearcoatNormalMap) nMacro = normalMap(texture(src.clearcoatNormalMap, st));
        // TOKSVIG (the beetle's, beetle_cuticle.js): each mip's filtered normal is SHORTER by the relief it averaged;
        // its length r gives the von Mises-Fisher variance 2 (1 - r^2) / (3 r - r^3), added to alpha^2
        const rl = nt.rgb.mul(2.0).sub(1.0).length().add(K.TOKSVIG_DEAD).min(1.0);
        const r2 = rl.mul(rl);
        varMap = r2.oneMinus().mul(2.0).div(rl.mul(3.0).sub(r2.mul(rl)).max(1.0e-4)).min(0.5);
    } else {
        pig = attribute('_pigment', 'vec4').clamp(0.0, 1.0);
        surf = attribute('_surface', 'vec4').clamp(0.0, 1.0);
        aux = attribute('_aux', 'vec4').clamp(0.0, 1.0);
    }
    const dec = (e) => exp2(e.sub(0.5).mul(K.LOG_RANGE));
    const pmm = positionGeometry.mul(1000.0);
    // the footprint (mm per pixel)
    const fw = fwidth(pmm).length();
    // (H3b) THE IDENTITY'S SKIN VARIATION (K.MOTTLE, K.FRECKLE, K.MOLE): log2 of each pigment, added to the zones'.
    // Dry skin only: the wet tissue (the lips' film, the lid margin, the mouth) keeps its colour
    const dry = surf.a.oneMinus();
    let lMel = float(0.0), lBlood = float(0.0), moleH = null, lMole = null;
    if (K.VARIATION !== false) {
        const SO = U.seedOffset;
        const M = K.MOTTLE;
        // the volume at the three scales; the fine layer fades with the footprint (it would alias), its share of the
        // variance is simply gone at a distance, as it is from any photograph
        const fadeL = (i) => smoothstep(M.VOL_MM[i] * 5.0, M.VOL_MM[i] * 2.5, fw);
        const n0 = volNoise(pmm, SO, 0, M.VOL_MM[0]), n1 = volNoise(pmm, SO, 1, M.VOL_MM[1]);
        const n2 = volNoise(pmm, SO, 2, M.VOL_MM[2]);
        const amp = U.mottle.mul(dry);
        lBlood = n0.x.mul(M.BLOOD[0]).mul(fadeL(0)).add(n1.x.mul(M.BLOOD[1]).mul(fadeL(1))).add(n2.x.mul(M.BLOOD[2]))
            .mul(amp);
        lMel = n0.y.mul(M.MEL[0]).mul(fadeL(0)).add(n1.y.mul(M.MEL[1]).mul(fadeL(1))).add(n2.y.mul(M.MEL[2])).mul(amp);
        // the deep folds' pigment (K.FOLD_MEL)
        lMel = lMel.add(smoothstep(0.80, 0.30, aux.r).mul(K.FOLD_MEL).mul(dry));
        // the spots' fine noise: a fourth, finer read of the volume (features ~0.2 mm), its channels the rim's roughness and
        // the patch's own mottling. THE SHAPES: the lookup is domain-warped by the fine layer (~+-0.3 mm over ~0.8 mm), so a
        // freckle is an irregular patch and neighbours run together into clusters, as the photos' do (round spots with a
        // soft ramp, side by side with the photo at the same 0.027 mm / px, were plainly discs)
        const nf = volNoise(pmm, SO, 3, K.SPOT_FINE_MM);
        const edge = nf.z;
        const F = K.FRECKLE;
        const pW = pmm.add(n0.xyz.mul(F.WARP_MM));
        // a density that wanders across the skin (freckles gather in drifts), from the coarse layer's fourth channel
        const drift = n2.w.mul(0.55).add(1.0).clamp(0.10, 2.0);
        const ballR = (F.R[1] - F.R[0]) / Math.log(F.R[1] / F.R[0]);      // the log-uniform radii's mean
        // g per layer for D_CM2 / cm2 at weight 1: D = g 2 R / cell^3 (mm), the layers adding
        const gF = F.D_CM2 * 0.01 * F.CELL ** 3 / (2.0 * ballR) / F.LAYERS;
        const gateF = U.freckles.mul(pig.b).mul(drift).mul(gF).mul(dry);
        let spot = float(0.0);
        for (let i = 0; i < F.LAYERS; i++) {
            const S = spotLayer(pW, SO, i, F.CELL, F.R, gateF, fw, edge, F.EDGE_MM);
            spot = spot.add(S.mask.mul(S.s.add(0.5)));
        }
        const L = F.LARGE;
        const ballL = (L.R[1] - L.R[0]) / Math.log(L.R[1] / L.R[0]);
        const gL = F.D_CM2 * L.SHARE * 0.01 * L.CELL ** 3 / (2.0 * ballL);
        const SL_ = spotLayer(pW, SO.add(vec3(131.0, 71.0, 37.0)), 0, L.CELL, L.R, U.freckles.mul(pig.b).mul(drift).mul(gL).mul(dry),
            fw, edge, F.EDGE_MM);
        spot = spot.add(SL_.mask.mul(SL_.s.mul(0.7).add(0.5)));
        spot = spot.clamp(0.0, 1.6).mul(nf.y.mul(0.18).add(n0.w.mul(0.16)).add(1.0));
        lMel = lMel.add(spot.mul(F.MEL));
        lBlood = lBlood.add(spot.mul(F.BLOOD));
        // THE MOLES: one layer, cell 14 mm: g so that `moles` is the whole-body count at the mean zone weight
        const Mo = K.MOLE;
        const rBall = (Mo.R[1] - Mo.R[0]) / Math.log(Mo.R[1] / Mo.R[0]);
        const gM = 0.01 * Mo.CELL ** 3 / (2.0 * rBall) / Mo.AREA_CM2;   // per unit count, on 1.7 m2 of skin
        const gateM = U.moles.mul(gM).mul(pig.b.mul(Mo.ZONE_GAIN).add(1.0)).mul(dry);
        const S = spotLayer(pmm.add(n0.xyz.mul(Mo.WARP_MM)), SO, 3, Mo.CELL, Mo.R, gateM, fw, edge.mul(0.3), Mo.EDGE_MM);
        const inner = smoothstep(S.R.mul(1.05), S.R.mul(0.55), S.d);
        const melM = mix(float(Mo.MEL[0]), float(Mo.MEL[1]), S.s);
        // (H3c) the mole's melanin kept apart, so its volume fraction can be capped below (K.MOLE.MEL_CAP)
        lMole = S.mask.mul(inner.mul(0.18).add(0.82)).mul(nf.y.mul(0.08).add(1.0)).mul(melM);
        lBlood = lBlood.add(S.mask.mul(S.s.mul(0.45).add(0.55)).mul(Mo.BLOOD));
        moleH = S.mask.mul(inner).mul(S.R).mul(Mo.H).mul(S.s.mul(0.8).add(0.4));
    }
    let fMel = U.melanin.mul(dec(pig.r)).mul(exp2(lMel));
    // (H3c) the mole: at most MEL_CAP, unless the skin itself is darker (a mole never lightens skin)
    if (lMole) fMel = fMel.mul(exp2(lMole)).min(fMel.max(K.MOLE.MEL_CAP ?? 1.0));
    // (H4b face) THE MOUTH'S WET TISSUE (K.MOUTH): the HEAD's mucosa behind the lips (the mouth sock, the lips' inner roll):
    // the wet zones near the opening's centre, and the lips' own tissue near it (the vermilion's wet 0.15 counts) that lies
    // behind the opening's plane: the inner rolls (the man's lower one stood up into the opening as a lit pale band with the
    // skin's grain, h4b/face/out/diag/d06_a1c.png). The driver's aperture; without one, nothing here changes
    let mouthMask = float(0.0), lipNear = float(0.0), mucosaMask = float(0.0);
    if (K.MOUTH) {
        const dC = THREE.positionWorld.sub(U.mouthC);
        const vAx = U.mouthN.cross(U.mouthU);                     // the opening's vertical (up)
        const dv = dC.dot(vAx);
        const mouthWet = smoothstep(K.MOUTH.WET_MASK[0], K.MOUTH.WET_MASK[1], surf.a)
            .mul(smoothstep(K.MOUTH.NEAR_M[0], K.MOUTH.NEAR_M[1], dC.length()))
            .mul(float(1.0).sub(smoothstep(K.MOUTH.ABOVE_M[0], K.MOUTH.ABOVE_M[1], dv))).mul(U.mouthOn);
        lipNear = smoothstep(0.03, 0.10, surf.a).mul(smoothstep(0.042, 0.036, dC.length())).mul(U.mouthOn);
        // the inner roll: behind the opening's plane, facing into the mouth (not forward: the outer vermilion and the cheek
        // by the corners curve back behind the plane but face out, and a plane-only test blacked them out, d08), and within
        // the opening's width
        const behind = float(1.0).sub(smoothstep(K.MOUTH.SIDE_M[0], K.MOUTH.SIDE_M[1], dC.dot(U.mouthN)));
        const facingIn = float(1.0).sub(smoothstep(0.05, 0.45, THREE.normalWorld.normalize().dot(U.mouthN)));
        const across = dC.dot(U.mouthU).abs().div(U.mouthAB.x.max(1.0e-4));
        const within = float(1.0).sub(smoothstep(0.85, 1.05, across));
        // THE DEEP INTERIOR whatever its zone (the pharynx's wall behind the tongue is not the wet mouth zone and stayed
        // sky-lit beige with the tongue hidden, d12): well behind the opening's plane, within its width, not far above it,
        // and facing toward the opening (the outer cheek faces away from it)
        // facing into the cavity: toward the opening's centre, or toward its central axis (the line through the centre
        // along the normal: the floor beside the tongue faces up to it, the palate down; facing the centre alone left the
        // floor sky-lit, a pale sliver between the side teeth and the tongue, d14)
        const nW = THREE.normalWorld.normalize();
        const toC = dC.negate().normalize();
        const toAx = U.mouthN.mul(dC.dot(U.mouthN)).sub(dC);              // from the point to its foot on the axis
        const faceIn = THREE.max(nW.dot(toC), nW.dot(toAx.div(toAx.length().max(1.0e-4))));
        // (no higher than DEEP_ABOVE_M above the centre: the nose's underside, 18-25 mm up, lies behind the plane too and
        // faces the axis; the palate an opening shows sits within ~12 mm)
        // the depth it must lie behind the plane grows with its height off the opening (beyond the half-height): the floor
        // and the palate lie deep behind the teeth, the chin's fold and the nose's underside a few mm behind a puckered
        // opening's plane (the 'ou' pucker drew a dark crescent on the chin, d16)
        // (and with its distance off the opening's sides: the back of the mouth spreads ~30-35 mm out, past the opening's
        // half-width, and a width limit at the opening's own left it sky-lit, a pale tick beside the molars, p07_pick.py;
        // the outer cheek faces away from the centre and the axis, so the facing test keeps it out)
        // (beyond the corners the interior lies deep behind the teeth: x3 per mm there, so the skin folds just outside the
        // corners, 5-12 mm behind the plane, stay out: at x0.5 they went dark, d23)
        const dU = dC.dot(U.mouthU).abs();
        const req = float(0.005).add(dv.abs().sub(U.mouthAB.y).max(0.0).mul(0.5))
            .add(dU.sub(U.mouthAB.x).max(0.0).mul(3.0));
        const withinDeep = float(1.0).sub(smoothstep(1.25, 1.6, dU.div(U.mouthAB.x.max(0.020))));
        const deep = withinDeep.mul(smoothstep(0.0, 0.25, faceIn))
            .mul(float(1.0).sub(smoothstep(req.negate(), req.negate().add(0.002), dC.dot(U.mouthN))))
            .mul(smoothstep(K.MOUTH.NEAR_M[0], K.MOUTH.NEAR_M[1], dC.length()))
            .mul(float(1.0).sub(smoothstep(K.MOUTH.DEEP_ABOVE_M[0], K.MOUTH.DEEP_ABOVE_M[1], dv)))
            .mul(float(1.0).sub(smoothstep(K.MOUTH.DEEP_BELOW_M[0], K.MOUTH.DEEP_BELOW_M[1], dv.negate()))).mul(U.mouthOn);
        mouthMask = THREE.max(THREE.max(mouthWet, deep), lipNear.mul(behind).mul(facingIn).mul(within));
        // THE MUCOSA'S LOOK (colour, smoothness, the wet film) also on the lips' surfaces that face the opening's centre line
        // within its width and a lip's roll of its height (the lower lip's wet inner part faces up into an open mouth, the
        // upper's down), in front of the plane too: the man's lower band read pale mauve with the dry skin's grain, d09
        const toward = THREE.normalWorld.normalize().dot(vAx).mul(dv.sign().negate());
        const facing = smoothstep(0.25, 0.6, toward);
        const nearV = float(1.0).sub(smoothstep(U.mouthAB.y.add(0.002), U.mouthAB.y.add(0.005), dv.abs()));
        mucosaMask = THREE.max(mouthMask, lipNear.mul(facing).mul(nearV).mul(within));
        fMel = fMel.mul(mix(float(1.0), float(K.MOUTH.INNER_MEL), mucosaMask));  // the mucosa: little melanin
        // (H4b face, session 2) the sock's UV islands (markMouthSock) join the cavity's LIGHTING mask, after the look's
        // mask is made (the look keeps its soft edges; the islands' seam is the inner lip line)
        if (opts.geometry?.attributes?.mouthSock) {
            mouthMask = THREE.max(mouthMask, THREE.attribute('mouthSock', 'float').mul(U.mouthOn));
        }
    }
    const fBlood = U.blood.mul(dec(pig.g)).mul(U.flush.add(1.0)).mul(exp2(lBlood))
        .mul(mix(float(1.0), float(K.MOUTH ? K.MOUTH.MUCOSA_BLOOD : 1.0), mucosaMask));    // (H4b face) the mucosa's red
    const uMel = sqrt(fMel.div(K.MEL_MAX).clamp(0.0, 1.0));
    const vBlood = sqrt(fBlood.div(K.BLOOD_MAX).clamp(0.0, 1.0));
    const alb = texture(lut.albedo, vec2(uMel, vBlood)).rgb;
    m.colorNode = alb.mul(U.tint);
    // the micro relief, faded by the footprint (mm per pixel), its lost slope variance into the roughness
    const fade = smoothstep(K.MICRO_FADE[1], K.MICRO_FADE[0], fw);
    // (textured: the AUX pack's B holds it as the RUNTIME relief's strength, the R tier: the body's pores; on the HEAD
    // set only where the forge's baked T tier fades out above the neck ring, i01_packs.py, so the two never double)
    const strength = pig.a.mul(U.pores);
    let nrm = nDetail || normalView;
    if (nDetail) m.normalNode = nDetail;
    let varN = varMap;
    if (K.MICRO) {
        let hM = microRelief(pmm, strength.mul(fade)).mul(1e-3);
        if (moleH) hM = hM.add(moleH.mul(1e-3));      // (H3b) a mole stands a little proud of the skin
        nrm = bumpFromHeight(hM, nDetail);
        m.normalNode = nrm;
        varN = varN.add(strength.mul(fade.oneMinus()).mul(K.MICRO_VAR));
    }
    // (H4b face) the mouth's wet tissue (mouthMask): smooth and wet: the T tier's pores and lines fade toward the macro
    // normal (a mucosa has no stratum corneum's grain), and its variance with them
    if (K.MOUTH) {
        // toward the surface's own smooth normal (the macro bake carries the vermilion's lines onto the inner roll too)
        nrm = mix(nrm, normalView, mucosaMask.mul(K.MOUTH.INNER_SMOOTH)).normalize();
        m.normalNode = nrm;
        varN = varN.mul(float(1.0).sub(mucosaMask.mul(K.MOUTH.INNER_SMOOTH)));
    }
    const dx = nrm.dFdx(), dy = nrm.dFdy();
    varN = varN.add(dx.dot(dx).add(dy.dot(dy)).mul(2.0 * K.SAA_SIGMA2).min(K.SAA_KAPPA));
    // roughness: the zone's, lowered by wetness (a water film: 0.12), then widened by the variance (alpha^2 + var)
    let rz = mix(surf.b, float(0.12), U.wet.max(surf.a.mul(0.6)));
    if (K.MOUTH) rz = mix(rz, float(K.MOUTH.INNER_ROUGH), mucosaMask);          // (H4b face) the mucosa's wet film
    m.roughnessNode = rz.mul(rz).mul(rz).mul(rz).add(varN).pow(0.25).clamp(0.05, 1.0);
    m.metalnessNode = float(0.0);
    m.aoNode = aux.r.max(surf.a.mul(K.WET_AO_FLOOR));
    // (H4b face) THE CAVITY on the HEAD's wet tissue behind the lips: its ambient x its view of the outside through the opening,
    // its reflection x the reflected ray's way out (m.skin.specVis, read by SkinLightingModel.ambientOcclusion)
    let mouthSpec = null;
    if (K.MOUTH) {
        const mvis = apertureVisibility(U, THREE.positionWorld, THREE.normalWorld.normalize());
        m.aoNode = m.aoNode.mul(mix(float(1.0), mvis, mouthMask));
        mouthSpec = mix(float(1.0), apertureSpecVis(U, THREE.positionWorld, THREE.normalWorld.normalize(), 0.18), mouthMask);
        if (K.MOUTH.DEBUG === 'vis') m.emissiveNode = vec3(mvis.mul(mouthMask), mouthMask.mul(0.25), 0.0);
    }
    m.ior = K.IOR;
    m.specularIntensity = 1.0;
    // what the lighting model reads
    const tissue = aux.g.mul(K.TISSUE_MAX);
    const f0 = ((K.IOR - 1) / (K.IOR + 1)) ** 2;
    m.skin = {
        lut,
        diffuse: m.colorNode,
        f0: vec3(f0, f0, f0),
        uMel, vBlood,
        curv: surf.r.mul(tissue.div(K.TISSUE_REF).clamp(0.4, 1.4)).clamp(0.0, 1.0),
        thickMM: surf.g.mul(K.THICK_MAX),
        thickM: surf.g.mul(K.THICK_MAX * 1e-3),
        ao: aux.r,                 // (H3b) the baked AO: the scattered shadow's cavity guard
        // (H3b integrator) the micro-shadow's AO: the baked AO (on the textured skin a few mips coarser) with the wet
        // tissue's floor
        aoDirect: aoMS ? aoMS.max(surf.a.mul(K.WET_AO_FLOOR)) : m.aoNode,
        nGeo: nMacro,            // the smooth surface's normal for the diffuse blend (null: the geometry's)
        specVis: mouthSpec,      // (H4b face) the mouth's wet tissue: the reflection's way out through the lips (null: none)
        // (H4b face) the mouth's wet tissue for the direct light (the lights through the opening only) and the lips' and
        // mucosa's transmission path near the opening (K.MOUTH.LIP_MIN_MM; the lips' wet 0.15, the mouth zone's 1.0)
        mouthMask: K.MOUTH ? mouthMask : null,
        mouthDirectFn: K.MOUTH ? (L) => apertureDirect(U, L) : null,
        lipMask: K.MOUTH ? lipNear : null,
    };
    m.name = TEX ? `human_skin_${src.userData?.set || 'tex'}` : 'human_skin';
    return m;
}

// ------------------------------------------------------------------------------------------------------ the eye
export function eyeMaterial(src, U, side, eyeK) {
    // eyeK: the globe's constants from the glb (node extras: globe_mm, cornea_r_mm, limbus_d_mm, iris_z_mm)
    const { vec2, vec3, vec4, float, mix, smoothstep, step, sin, cos, atan, length, normalize, refract, abs,
        positionGeometry, cameraPosition, modelWorldMatrixInverse, mx_noise_float, mx_worley_noise_float } = THREE;
    const R = eyeK.globe_mm / 2, RC = eyeK.cornea_r_mm, RL = eyeK.limbus_d_mm / 2, ZI = eyeK.iris_z_mm;
    const ZC = Math.sqrt(R * R - RL * RL) - Math.sqrt(RC * RC - RL * RL);
    const p = positionGeometry.mul(1000.0);
    const cam = modelWorldMatrixInverse.mul(vec4(cameraPosition, 1.0)).xyz.mul(1000.0);
    const vd = p.sub(cam).normalize();
    const nC = p.sub(vec3(0.0, 0.0, ZC)).normalize();
    const rd = refract(vd, nC, 1.0 / 1.376);
    // the refracted ray runs into the eye (rd.z < 0) and meets the iris plane behind the cornea (ZI < p.z)
    const tt = float(ZI).sub(p.z).div(rd.z.min(-1e-3));
    const q = p.add(rd.mul(tt));
    const rho = length(q.xy);
    const ang = atan(q.y, q.x);
    const rp = U.pupil.mul(0.5);
    const RI = float(RL - 0.12);
    const tI = rho.sub(rp).div(RI.sub(rp)).clamp(0.0, 1.0);
    const irisCol = side === 'L' ? U.irisL : U.irisR;
    // the stroma: radial fibres (angle-stretched noise), the collarette at ~0.3 of the way out, crypts, the limbal ring
    const fib = mx_noise_float(vec3(cos(ang).mul(38.0), sin(ang).mul(38.0), tI.mul(4.0)))
        .add(mx_noise_float(vec3(cos(ang).mul(90.0), sin(ang).mul(90.0), tI.mul(9.0))).mul(0.5));
    const colPos = float(0.30).add(mx_noise_float(vec3(cos(ang).mul(5.0), sin(ang).mul(5.0), 3.0)).mul(0.05));
    const collar = smoothstep(0.07, 0.0, abs(tI.sub(colPos)));
    const crypt = smoothstep(0.30, 0.05, mx_worley_noise_float(vec3(cos(ang).mul(7.0), sin(ang).mul(7.0),
        tI.mul(2.2)), 0.9)).mul(smoothstep(0.30, 0.45, tI)).mul(smoothstep(0.85, 0.65, tI));
    const limbal = smoothstep(0.78, 1.0, tI);
    let iris = irisCol.mul(fib.mul(0.35).add(1.0)).mul(collar.mul(0.45).add(1.0)).mul(crypt.mul(-0.55).add(1.0))
        .mul(limbal.mul(-0.75).add(1.0));
    // the inner pupillary band: a darker ruff right at the pupil's edge
    iris = iris.mul(smoothstep(0.0, 0.05, tI).mul(0.6).add(0.4));
    // (H3c) THE EYES SET (h4/close/c09_eyetex.py: the iris from a photograph, the sclera baked) when the glb's eye material
    // carries it (baseColorTexture): the iris read at the refracted point, its radius remapped from this pupil onto the
    // texture's reference pupil (the stroma stretches as the pupil opens), coloured by the identity's iris colour over the
    // photo's own mean (extras iris_ref_lin), so the uniform still sets the colour and the photo the structure; the sclera
    // read at the surface's own UV. The procedural stroma and sclera stay as the fallback
    const EYES = !!(src && src.map);
    if (EYES) {
        const ex = src.userData || {};
        const ref = ex.iris_ref_lin || [0.083, 0.048, 0.0136];
        const pref = float(ex.pupil_ref_mm ?? 1.8);
        src.map.anisotropy = K.ANISOTROPY;
        const rhoT = mix(pref, RI, tI);
        const qT = q.xy.mul(rhoT.div(rho.max(1.0e-4)));
        const uvI = vec2(qT.x.div(2.0 * 12.5).add(0.5), float(0.5).sub(qT.y.div(2.0 * 12.5)));
        if (ex.iris_mode === 'structure') {
            // (H4b face) K.IRIS: the photo's structure x the identity's colour by zone
            const IR = K.IRIS;
            const st = THREE.texture(src.map, uvI).r.div(ex.structure_mid_lin ?? 0.214).max(1.0e-4).pow(IR.CONTRAST);
            const coll = smoothstep(IR.COLLARETTE[0], IR.COLLARETTE[1], tI);
            const inner = side === 'L' ? U.irisInnerL : U.irisInnerR;
            iris = mix(irisCol.mul(inner), irisCol, coll).mul(st)
                .mul(float(1.0).sub(smoothstep(IR.LIMBAL[0], 1.0, tI).mul(IR.LIMBAL[1])))
                .mul(smoothstep(0.0, IR.RUFF[0], tI).mul(1.0 - IR.RUFF[1]).add(IR.RUFF[1]));
        } else {
            iris = THREE.texture(src.map, uvI).rgb.mul(irisCol).div(vec3(...ref));
        }
    }
    // the sisters' spiral (a runtime iris display): arms in log-polar, one colour per eye
    const spiralArm = sin(ang.mul(3.0).add(rho.max(0.2).log().mul(6.0)).add(U.t.mul(0.6))).mul(0.5).add(0.5);
    iris = mix(iris, irisCol.mul(spiralArm.mul(1.6).add(0.3)), U.spiral);
    const pupilM = smoothstep(rp.add(0.08), rp.sub(0.08), rho);
    const irisCore = mix(iris, vec3(0.004, 0.004, 0.005), pupilM);
    // the sclera: off-white, a little warmer and darker toward the corners (the technician's CFEye), faint vessels
    const off = length(p.xy).div(R);
    const vess = smoothstep(0.08, 0.0, abs(mx_noise_float(p.mul(0.55)))).mul(smoothstep(0.55, 0.95, off)).mul(0.5);
    const sclera = EYES ? THREE.texture(src.map, THREE.uv()).rgb : mix(vec3(0.70, 0.64, 0.60), vec3(0.62, 0.50, 0.46),
        smoothstep(0.45, 0.95, off)).mul(vess.mul(-0.35).add(1.0)).add(vec3(0.08, 0.0, 0.0).mul(vess));
    const inIris = smoothstep(RL + 0.15, RL - 0.25, length(p.xy)).mul(step(0.0, p.z));
    // THE LIDS' OCCLUSION on the ball (a stand-in for the plan's occlusion shell): darker within ~2 mm of each lid
    // margin's height in the eye's frame (the identity's own: the glb's node extras lid_up_mm / lid_dn_mm, measured on
    // the clay's margin loops by m02), in eye space, so it is exact at the rest gaze and drifts with large gazes
    // (the head-attached shell, H4 / H7, replaces it). [E: the depth 0.55 and the 2 mm band]
    const up = float(eyeK.lid_up_mm ?? 4.4), dn = float(eyeK.lid_dn_mm ?? -5.4);
    // (H3b) with the eye's parts in the scene the head-attached shell does this (eyeShellMaterial), so the band goes
    const occl = K.EYE_PARTS ? float(1.0) : float(1.0).sub(smoothstep(up.sub(2.2), up, p.y)
        .add(smoothstep(dn.add(2.0), dn, p.y)).clamp(0.0, 1.0).mul(0.55));
    const m = new HumanPhysicalNodeMaterial();
    m.colorNode = mix(sclera, irisCore, inIris).mul(occl);
    m.aoNode = K.EYE_PARTS ? float(eyeK.ao_ref ?? 0.88) : occl;
    m.roughnessNode = mix(float(0.12), float(0.04), inIris);
    m.metalnessNode = float(0.0);
    m.ior = 1.376;
    m.emissiveNode = irisCol.mul(U.eyeGlow).mul(inIris).mul(pupilM.oneMinus()).mul(spiralArm.mul(0.7).add(0.3));
    m.name = 'human_eye_' + side;
    return m;
}

// (H3b) THE EYE'S PARTS, the way games dress a digital human's eye (e01_eyeparts.py's header has the geometry):
// THE SHELL multiplies the ball by a tinted occlusion measured per vertex (attribute _shell: x occlusion relative to the
// opening's centre, y mm to the rim, z the upper lid's share), plus the lashes' shadow band until lashes exist. A true
// multiply (src Zero, dst SrcColor) in the linear target: it dims the ball, its reflections and nothing else, and being
// head-attached it does not drift with the gaze as the stand-in did. Drawn first of the parts.
export function eyeShellMaterial() {
    const { attribute, vec3, float, mix, MeshBasicNodeMaterial } = THREE;
    const a = attribute('_shell', 'vec4');
    const lash = a.z.mul(a.y.div(K.SHELL_LASH_MM).pow2().negate().exp()).mul(K.SHELL_LASH);
    const occ = a.x.clamp(0.0, 1.0).pow(K.SHELL_POW ?? 1.0).mul(K.SHELL_GAIN).add(lash).clamp(0.0, 0.97);   // (H3c) the power
    const m = new MeshBasicNodeMaterial();
    m.colorNode = mix(vec3(1.0), vec3(...K.SHELL_TINT), occ);
    m.transparent = true;
    m.depthWrite = false;
    m.blending = THREE.CustomBlending;
    m.blendEquation = THREE.AddEquation;
    m.blendSrc = THREE.ZeroFactor;
    m.blendDst = THREE.SrcColorFactor;
    m.blendSrcAlpha = THREE.ZeroFactor;
    m.blendDstAlpha = THREE.OneFactor;
    m.side = THREE.DoubleSide;
    m.fog = false;
    m.name = 'human_eye_shell';
    return m;
}

// THE RING and THE CARUNCLE: wet tissue under a clear film (attribute _ring: x the tissue's alpha, y the film's weight,
// z the part's measured AO, w colour, 0 the lid's posterior edge .. 1 the corners' conjunctiva). (src One, dst
// OneMinusSrcAlpha) so the film's specular survives where the tissue has faded to nothing: at x = 0 the strip is a
// clear meniscus over the ball, a thin bright line. The film's weight reaches the specular through
// specularIntensityNode (honoured by HumanPhysicalNodeMaterial: the r184 trap), so its grazing lobe fades with it.
export function eyeRingMaterial(U, lut, kind = 'ring') {
    const { attribute, texture, vec2, float, mix, sqrt, positionGeometry, positionWorld, normalWorld, normalView,
        mx_noise_float } = THREE;
    const a = attribute('_ring', 'vec4');
    const alpha = a.x.clamp(0.0, 1.0);
    const mel = U.melanin.mul(mix(float(K.RING_MEL[0]), float(K.RING_MEL[1]), a.w));
    const bl = U.blood.mul(mix(float(K.RING_BLOOD[0]), float(K.RING_BLOOD[1]), a.w));
    let alb = texture(lut.albedo, vec2(sqrt(mel.div(K.MEL_MAX).clamp(0, 1)), sqrt(bl.div(K.BLOOD_MAX).clamp(0, 1)))).rgb;
    const m = new HumanPhysicalNodeMaterial();
    let nrm = normalView;
    if (kind === 'caruncle') {
        // its glandular surface: fine soft bumps (sebaceous glands, ~0.3 mm), paler crowns over the blood
        const pmm = positionGeometry.mul(1000.0);
        const n = mx_noise_float(pmm.div(0.30));
        alb = alb.mul(n.mul(0.18).add(1.0));
        nrm = bumpFromHeight(n.mul(0.018).mul(1e-3).mul(alpha));
        m.normalNode = nrm;
    }
    m.colorNode = alb.mul(alpha);
    m.opacityNode = alpha;
    // the film's lobe, widened by its own normal's screen variation (Tokuyoshi-Kaplanyan, as the skin's): the strip can be
    // a pixel wide at a portrait distance, and its highlight must stay a line, not crawl
    const dx = nrm.dFdx(), dy = nrm.dFdy();
    const v = dx.dot(dx).add(dy.dot(dy)).mul(2.0 * K.SAA_SIGMA2).min(K.SAA_KAPPA);
    // (the corners' wet tissue is rougher than the free film: a mirror lobe drew thin arcs along the plica's ridge)
    const r = mix(float(K.TEAR_ROUGH), float(K.TISSUE_ROUGH), a.w.clamp(0.0, 1.0));
    m.roughnessNode = r.pow2().pow2().add(v).pow(0.25).clamp(0.05, 1.0);
    m.metalnessNode = float(0.0);
    m.ior = K.TEAR_IOR;
    m.specularIntensity = 1.0;
    m.specularIntensityNode = a.y.clamp(0.0, 1.0);
    m.aoNode = float(K.RING_AO_FLOOR).add(a.z.clamp(0.0, 1.0).mul(1.0 - K.RING_AO_FLOOR));
    m.receivedShadowPositionNode = positionWorld.add(normalWorld.mul(K.RING_SHADOW_LIFT_MM * 1e-3));
    m.transparent = true;
    m.depthWrite = false;
    m.blending = THREE.CustomBlending;
    m.blendEquation = THREE.AddEquation;
    m.blendSrc = THREE.OneFactor;
    m.blendDst = THREE.OneMinusSrcAlphaFactor;
    m.blendSrcAlpha = THREE.OneFactor;
    m.blendDstAlpha = THREE.OneMinusSrcAlphaFactor;
    m.side = THREE.DoubleSide;
    m.name = 'human_eye_' + kind;
    return m;
}

// --------------------------------------------------------------------------------------- teeth, gums and tongue
export function mouthMaterial(src, U, lut, kind, geom = null) {
    const { vec2, float, texture, sqrt } = THREE;
    const m = new HumanPhysicalNodeMaterial();
    // (H3c) THE MOUTH SET (h4/close/c11_mouth.py: the teeth's colour from the crown table; the mucosa's multiplier round
    // sRGB mid-grey, linear 0.214) and the per-vertex bake (_MOUTH: x AO, y part, z the crown coordinate, w the incisal
    // translucency weight) when the glb carries them (the budget mouth); H3b's flat colours without
    const MS = !!(src && src.map);
    const MA = !!(geom && geom.attributes && geom.attributes._mouth);
    if (MS) { src.map.anisotropy = K.ANISOTROPY; }
    const tex = MS ? texture(src.map, THREE.uv()).rgb : null;
    if (kind === 'teeth') {
        m.colorNode = MS ? tex : THREE.vec3(0.62, 0.56, 0.43);   // enamel over dentine [E: a VITA A2-like shade]
        m.roughnessNode = float(0.22);
        m.ior = 1.62;                                     // enamel
    } else {
        // gums and tongue from the skin LUT: mucosa, little melanin, much blood (the skin's mouth zone)
        // (H4b face) as tissue: K.MOUTH's pigments (H4: gums x0.15 / x14, tongue x0.10 / x10, rough 0.22 / 0.45), a wrapped
        // diffuse (the lighting model's wrapRGB)
        const T_ = kind === 'gums' ? K.MOUTH.GUMS : K.MOUTH.TONGUE;
        const mel = U.melanin.mul(T_.mel);
        const bl = U.blood.mul(T_.blood);
        const alb = texture(lut.albedo, vec2(sqrt(mel.div(K.MEL_MAX).clamp(0, 1)),
            sqrt(bl.div(K.BLOOD_MAX).clamp(0, 1)))).rgb;
        m.colorNode = MS ? alb.mul(tex.div(0.2140)) : alb;
        m.roughnessNode = float(T_.rough);
        if (T_.spec !== undefined) m.specularIntensity = T_.spec;
        m.wrapRGB = T_.wrap;
        m.ior = 1.38;
    }
    // (H4b face) THE CAVITY: the parts' own crevices (H3c's vertex AO) x each point's view of the outside through the lips'
    // opening (apertureVisibility; 1 while no driver sets the aperture)
    const crev = MA ? THREE.attribute('_mouth', 'vec4').x.clamp(0.0, 1.0).mul(0.75).add(0.25) : float(1.0);   // (H3c) the parts' crevices
    const vis = apertureVisibility(U, THREE.positionWorld, THREE.normalWorld.normalize());
    m.aoNode = crev.mul(vis);
    const roughK = kind === 'teeth' ? 0.22 : (kind === 'gums' ? K.MOUTH.GUMS.rough : K.MOUTH.TONGUE.rough);
    m.specVis = apertureSpecVis(U, THREE.positionWorld, THREE.normalWorld.normalize(), roughK);   // the reflection's view out
    m.mouthDirectFn = (L) => apertureDirect(U, L);                                              // the lights through the opening
    if (K.MOUTH.DEBUG === 'vis') { m.colorNode = THREE.vec3(0.0); m.emissiveNode = THREE.vec3(vis); }
    m.metalnessNode = float(0.0);
    m.name = 'human_' + kind;
    return m;
}

// dispatch by the material's extras key (the glb's materials say bestiary: human_skin / human_eye / ...)
export function humanMaterial(obj, U, lut) {
    const key = obj.material?.userData?.bestiary || '';
    // (H4b face, session 2) the skin's mesh: its mouth sock marked by its UV islands (markMouthSock), the geometry passed on
    if (key === 'human_skin') {
        if (K.MOUTH && obj.isSkinnedMesh) {
            const k = markMouthSock(obj);
            if (k > 0) console.log(`[human_skin] ${obj.name}: the mouth sock's UV islands, ${k} vertices`);
        }
        return skinMaterial(obj.material, U, lut, { geometry: obj.geometry });
    }
    if (key === 'human_eye') {
        let n = obj, ex = null;
        while (n && !ex) { ex = n.userData?.globe_mm ? n.userData : null; n = n.parent; }
        const side = (ex && ex.eye_side) || (obj.name.endsWith('R') ? 'R' : 'L');
        return eyeMaterial(obj.material, U, side, ex || { globe_mm: 24.156, cornea_r_mm: 7.8, limbus_d_mm: 11.71,
            iris_z_mm: 10.2 });
    }
    if (key === 'human_eye_shell') return eyeShellMaterial();
    if (key === 'human_eye_ring') return eyeRingMaterial(U, lut, obj.name.startsWith('caruncle') ? 'caruncle' : 'ring');
    if (key === 'human_teeth') return mouthMaterial(obj.material, U, lut, 'teeth', obj.geometry);
    if (key === 'human_gums') return mouthMaterial(obj.material, U, lut, 'gums', obj.geometry);
    if (key === 'human_tongue') return mouthMaterial(obj.material, U, lut, 'tongue', obj.geometry);
    return obj.material;
}
