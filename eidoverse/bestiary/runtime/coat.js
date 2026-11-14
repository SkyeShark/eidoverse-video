// coat.js: Claude's Creatures' COAT at runtime, fur and hair as a generator part on ANY base (Skye 10-28: "fur and hair
// should be its own sort of part of the generator like the crystal growths, so we could do things like have a furry
// octopus"), real time first ("make sure to optimize everything for real time when you work with hair and fur"). The
// forge's groom (forge/groom/; HAIR_STUDY §9: one groom, many emitters) emits CARDS in the coat ABI
// (work/bestiary/coat/g_runtime/ABI_RUNTIME.md: WOLF_PLAN §5.4's, one primitive per base skin material) and a COAT
// PACK on the base's texels. This file draws them over a Bestiary creature, riding its skeleton:
//
//   import { loadCoat, attachCoat } from './coat.js';
//   const coat = await attachCoat(oct, await loadCoat(bytes), { display: { masks: displayMasks, clouds: displayClouds } });
//   coat.look({ wind: 0.004, tint: 0xffe8d0 });        // any COAT_LOOK key, live (uniforms: no recompile)
//   coat.lod;                                          // { screen, cut, width } at the last frame
//
// THE CARD MATERIAL (CoatNodeMaterial, ported from SPECIMEN's FurNodeMaterial, creature_specimen.js 1093-1386, which
// four review rounds proved in this engine), with HAIR_STUDY §9.5's lobes:
// - lighting (CoatLightingModel): R, TT and TRT about the strand tangent as Unreal's real-time hair BSDF has them
//   (Karis 2016, the shading model both games of the study ship), plus SPECIMEN's energy-normalised wrap diffuse about
//   the ROOT's base normal (cards shade like the body, never like flat planes) and a scatter term that grows as the
//   colour brightens (blond glows, black does not: study T: scatter min / max); a self-shadow toward the root stands in
//   for the deep-opacity a strand renderer would have; the environment as a dim R share of its radiance with no
//   Fresnel about the skin's normal (that term turned the cards at the body's silhouette silver);
// - colour: the base's albedo at the root UV (one lookup per card at the manifest's explicit level), then the remix's
//   zone remap with the zone masks read at the same UV (opts.remap, supplied by remix.js), the bestiary tint and the
//   skin's display families at the root (opts.display: the fur changes colour with the skin), then the style: root
//   darkening, tip lift, per-card value / hue jitter, per-strand jitter from the attribute page;
// - alpha: opaque numeric alpha test (never alpha-to-coverage: one sample per pixel drops the draw; never alphaHash:
//   it crawls), the coverage page's alpha rescaled per pixel by the forge's per-mip clip so the material's one cut
//   keeps mip 0's coverage at every distance (and the shadow pass sees the same test), SPECIMEN's resolvability
//   retirement, an edge-on fade (the study-T camera-vector edge mask), the LOD rank dissolve;
// - position (coatPosition, in BIND space: three runs a position node before skinning): SPECIMEN's coherent sway + a
//   travelling gust along the wind, weighted by rootToTip^2 x flex and applied to the vertex and its centreline alike
//   (never changes a card's width), then SPECIMEN's projected-width floor and the LOD's coverage compensation;
// - LOD (coatLOD): ONE mesh, a draw range by screen size over the rank-sorted cards (the manifest's prefix table) and
//   a dissolve of the cards whose rank + strandRandom lies near the cut, so ranks fade instead of popping; below the
//   ladder's last entry nothing is drawn and the skin's coat layer carries the read (the far end costs the bare
//   creature plus a few texture reads in the skin).
// THE SKIN'S COAT LAYER (coatSkinLayer): the coat pack on the base's texels (density, length, comb) blended into the
// skin material: the fur's colour, a velvet sheen, a matte lobe, the skin's subsurface held back; and (the integration,
// 10-29) the coat's own relief and strands from the pack's height in place of the skin's papillae and pores.
// THE INTEGRATION'S CHANGES (10-29, judged on the furry octopus in the engine; work/bestiary/coat/g_integrate/
// NOTES.md): long coats' FREE TIPS (look.tipFree: the outer part of a card shades as a fibre, Kajiya-Kay about its
// tangent, past the silhouette where the root normal has turned from the light); the ROOT FADE (look.rootFade: cards
// thin out where the coat pack's density at their root falls toward a bare zone, no pale 'paper' cards on the oral
// web's margin); FINS (look.finOnly: a short coat's cards drawn only at the silhouette, the velvet's close-up pile); the
// coat's own relief in the skin layer (look.layerFlat / layerBump / layerDetail / layerSoften); the fins take the
// layer's grazing sheen (the second pass, 10-29 night). THE HOST'S SCREEN-SPACE AO (round 2, settled in the material:
// the harness default stays): the eidoverse harness's N8AO at its default 0.3 m takes every card layer in front of a
// point as solid, which turned the first pass's mantle crest near black (work/bestiary/coat/g_integrate/look/d4_ao.png);
// the cards opt out of it and take a share in its transparency pass instead (look.aoTake at the root to aoTakeTip at
// the tip), and the furred skin under drawn cards claims a share back (look.layerAOClaim), set by the integration so the
// coat stays within ~2.6 levels of its own far end with a ground in the frame (work/bestiary/coat/g4/g4_integrate/
// NOTES.md, work/bestiary/patches/coat_runtime.md).
// THE TIP COLOUR (W3a, the wolf pelt, 11-09; work/bestiary/wolf/w3a_notes/NOTES.md): a coat's guard hairs end in their own
// colour, darker OR lighter than the root (study T's root / tip pair lifts the tip; a grey wolf's agouti guard hair ends
// black, and its salt and pepper is those black tips over the pale bands and the underfur). The forge's TIP PACK on the
// base's texels (man.tip_pack, per base material, as coat_pack: RGB the tip colour stored sRGB, A the share of the strands
// whose tip it is), read at the root uv as the albedo is; along a card it takes over from look.tipStart to tipEnd, each
// strand's start jittered (look.tipJitter), on the strands whose id (the attribute page's lock id + its per-strand offset,
// shifted by the card's random) falls under the share: whole locks mostly, so the dark tips read as flecks and streaks,
// never one dash per card. The skin layer takes look.layerTip of it past the close-up (the coat seen as maps). Built when
// look.tipMix > 0 at attach and the coat carries a tip pack; no change to any other coat.
// THE CLOAK (setCoatOpacity): the remix's creature-wide opacity on the coat, the coverage test unchanged.
// SHELLS (coatShells, when the forge's manifest carries a 'shells' spec): a short coat's optional close-up layer, one
// instanced draw per skin set over the furred triangles. Measured 10-29 on the velvet octopus at 1080p: +1.0 ms (x8)
// to +1.4 ms (x16) per frame at 0.6 m, against +0.03 ms or less for the skin layer alone: built only on request
// (attachCoat's opts.shells).
//
// Engine facts this file is built around (WOLF_PLAN §5.3; reference_webgpu_silent_draw_drops): the scene pass is
// single-sample, alpha-to-coverage silently drops the draw, more than 8 vertex buffers silently drops it too (the
// coat binds 6: position, normal, tangent, skinIndex, skinWeight and the interleaved _furdata / _rootdata /
// _furcenter), opacity multiplies alpha BEFORE the alpha test, a transparent DoubleSide material draws twice unless
// forceSinglePass. The file is species-agnostic and imports nothing from bestiary.js / remix.js (they pass their
// builders in), so it lifts out with the rest of Claude's Creatures.

const THREE = globalThis.THREE;

// ============================================================================================ the look (defaults)
// Every key is a uniform (live, no recompile) unless marked. The forge's manifest.look overrides these per style,
// attachCoat's opts.look over that, coat.look({...}) at runtime.
export const COAT_LOOK = {
    // colour: 0 = the base's albedo at the root, 1 = the style's own colour; tint multiplies after
    colorMix: 0.0, color: [0.30, 0.22, 0.16], tint: [1.0, 1.0, 1.0],
    rootDark: 0.62, rootDarkEnd: 0.40,          // albedo x rootDark at the root, back to 1 by rootToTip rootDarkEnd
    tipLift: 0.25,                              // tips lighter (study T: every root / tip pair has the lighter tip)
    valueJitter: 0.07, hueJitter: 0.025,        // per card (the study-T random value / hue variation, softer)
    strandJitter: 0.25,                         // per strand (the attribute page's id); (g5) 0.10 -> 0.25: with the id now
                                                // arriving intact, the strands' own variation is what reads as fibre
    strandHue: 0.06,                            // (g5) per strand, the hue's share (MetaHuman's melanin variation)
    band: 0.0, bandCenter: 0.58, bandWidth: 0.12, bandDark: 0.55,   // one agouti band (the wolf's preset; 0 = off)
    // (W3a) THE TIP COLOUR from the coat's tip pack (built when tipMix > 0 at attach and man.tip_pack names the base
    // material; 0 = off, the root colour lifted by tipLift as before): its weight, where along the strand it takes over
    // (rootToTip tipStart .. tipEnd), each strand's start jittered by +- tipJitter, and a multiplier on the pack's share
    tipMix: 0.0, tipStart: 0.62, tipEnd: 0.86, tipJitter: 0.12, tipShare: 1.0,
    tipInner: 1.0,                              // (W3a) the share on the volume's inner, dense cards (atlas row 0) relative
                                                // to its outer ones (the last row), linear between: a groom clumped by
                                                // layer puts the underfur in the dense rows and the guards in the sparse
                                                // ones, and the pepper is the guards' (1 = every row alike)
    bandSel: 0.0,                               // (W3a) the agouti band on the tip-coloured strands only (1) or on all (0)
    layerTip: 0.3,                              // (W3a) the skin layer's share of the tip colour past the close-up (x the
                                                // pack's share x tipShare x tipMix x (1 - closeW)): the coat seen as maps
    // (B3, H8) the pigment model: 0 = off (the colour above), 1 = the melanins' colour (built when > 0 at attach)
    pigment: 0.0, eumelanin: 0.30, pheomelanin: 0.12, pigmentPath: 4.0, dye: [0.5, 0.5, 0.5], dyeAmount: 0.0, grey: 0.0,
    // shading (Unreal's hair BSDF: roughness widens the lobes, shift tilts them, specular scales R)
    // (roughness 0.62 vs 0.42 barely differs on the groom's shaggy at 1.5 m and close: the coat's read is its coverage
    // and the diffuse terms; 0.5 is a middle, 10-29)
    // ((g5) 0.5 -> 0.4, with the per-strand tilt and roughness below: the highlight breaks into streaks along the flow)
    roughness: 0.4, specular: 0.5, shift: 0.05, backlit: 0.55, scatter: 0.22,
    trt: 1.0,                                   // (the second restart) the TRT lobe's gain (1 = Unreal's; the tone per
                                                // lighting term isolates it with 0, g4_runtime/TONE.md)
    rTint: 0.0,                                 // (B5 hair) the R lobe's colour: white (0) .. the albedo's hue at full value
                                                // (1). A card is a bundle: light leaving its outer strands' surfaces has
                                                // also crossed strands in front, so the bundle's primary reads in the
                                                // hair's colour, not a white veil over it (the chalk, b5_NOTES)
    // (B6 hair) DARK HAIR's R (where rTint fades out, the albedo's luminance under ~0.07): black hair's highlight is a
    // narrow, dim, cool-white sheen, not the full-width white band light hair's R would be (the B5 check: a silver
    // crescent on the ponytail, a grey sheet on long, a white band on the crop). Each default = no change for any coat
    darkR: 1.0,                                 // the R lobe's gain on dark albedo
    darkRWidth: 1.0,                            // the R lobe's width (roughness) on dark albedo
    darkRCool: 0.0,                             // 0 white .. 1 a cool white (0.82, 0.90, 1.0) on dark albedo
    darkEnv: 1.0,                               // the environment's R on dark albedo
    matteFace: 0.0,                             // (B6) the brows' and lashes' R / TRT / env R taken away (0 .. 1): cards
                                                // flagged in _rootdata.w (+512, b6_build.py) lie flat on the skin, where a
                                                // fibre's lobe drew white blotches at the brows' medial ends
    ttBundle: 2.5,                              // (g5) the TT lobe's absorption path in strands: a card is a bundle (1 = one
                                                // strand's, Unreal's: back light reads near neutral on a dark coat). At Skye's
                                                // sand frame the rim light's streaks 0.31 -> 0.37 saturation, warm; 4 no further
                                                // (the rest there is that light's R lobe); the back-lit station unchanged to the eye
    wrap: 0.40, wrapMix: 0.18,                  // SPECIMEN's energy-normalised wrap about the root normal
    tipFree: 0.6, kkGain: 0.55,                 // the free tips: toward the tip the fibre's own Kajiya-Kay diffuse (x kkGain)
                                                // replaces the root normal's, and the root's terminator lets go (0 = off)
    selfShadow: 0.55,                           // direct light at the root relative to the tip (deep coats darker)
    shadowLift: 0.0,                            // (B3b; built when > 0 at attach) metres the cards' RECEIVED shadow lookup is
                                                // lifted out along their shell normal: a hair volume's card layers lie 1-13 mm
                                                // apart, and the 4096 shadow map cast each outer card's hard outline onto the
                                                // ones under it (B3's bob: card-shaped light / dark patches over the whole
                                                // skull, b3b_e03..e08); lifted past the volume, only what lies outside it (the
                                                // head, the other side of the hair) shadows a card
    layerOcc: 0.0,                              // (B3b) THE VOLUME'S DEPTH: a card's light x (1 - layerOcc x (1 - row / 3)), row
                                                // its atlas density row (0 = the volume's inner, densest cards .. 3 the outer
                                                // wisps: cards.py classify ranks them by height in the volume), on the direct
                                                // and the indirect light. With the hard self-shadow lifted (shadowLift) every
                                                // layer shaded alike, so the partings between clumps filled with the same
                                                // tone and the hair read as paint (b3b_e10); deeper hair is darker
    shadowSoft: 0.0,                            // (B3b) the received shadow eased toward 1 by this (a hair volume transmits:
                                                // study T / MetaHuman shadow hair through a deep-opacity term, never a hard map)
    depthShadow: 0.5,                           // (round 2) direct light through the clump: x (1 - depth x this), the
                                                // attribute page's depth (strands nearer the skin lie under the others);
                                                // (g5) 0.35 -> 0.5: it never acted before (the page's depth arrived
                                                // divided by its alpha, ~0 everywhere)
    depthRef: 1.5,                              // (g5) the depth that counts as full: mm toward the skin from the card's
                                                // plane (a strand 1.5 mm under its clump's crest is fully in its shade;
                                                // 0 = the page's own full scale, atlas.depth_mm: 6 mm on shaggy, where
                                                // its strands lie within ~1 mm of their card's plane)
    depthMean: -1,                              // (g5) the depth the clump's shade and its AO centre on, as (0.5 - R) x 2 of
                                                // the page (negative: the forge's atlas.depth_mean, else 0): they are a
                                                // MODULATION about the page's coverage-weighted mean (crests lighter, flanks
                                                // darker), which the mips take to no change at all with distance, not a
                                                // one-sided darkening (v3's mean 0.233 at depthRef 1.5 took 3.7 levels at
                                                // 1.75 m and 1.6 at 15 m off the coat, look/tone_b9s0.json)
    scraggle: 0.3, curl: 0.6,                   // per-strand tangent tilt (study T: tangent A / B: +-0.3; (g5) 0.15 -> 0.3), the
                                                // page's sideways bend
    roughJitter: 0.35,                          // (g5) per-strand roughness variation (MetaHuman's RoughnessVariation 0.35)
    envRoughness: 0.78,                         // the environment's lobe: the radiance's blur
    envSpec: 1.0,                               // the environment's R share (at the fibre's F0, no grazing boost)
    aoRoot: 0.35, aoDepth: 0.25,                // indirect occlusion toward the root, and by the page's depth
    envFibre: 1.0,                              // (g5; built when > 0 at attach, never on fins) the environment's normal turned
                                                // from the root's toward the side of the fibre the eye sees (0 = the root's): a
                                                // fibre seen side-on shows its flank, not the sky its root faces. Coat - maps with
                                                // a ground max 1.46 -> 1.18 levels, floating at 1.75 m -7.3 -> -5.5, the coat's L*
                                                // 3 -> 15 m +1.04 -> +0.42, the fur's saturation 0.44 -> 0.48 (tone_n.json, tone_w2.json)
    aoTipGap: 0.0,                              // (B3c) what the GAPS of a card's tip half claim in N8AO's transparency pass
                                                // (0 = as before: a gap discards, so the skin seen through it keeps the AO
                                                // the card itself causes, counted as solid). The bob's fringe tips 4-8 mm
                                                // off the forehead and the nape's 12-40 mm off the neck drew a ragged pink
                                                // 'stubble' band there (gone with N8AO off: b3c_d_noao); a sparse tip
                                                // occludes little. Over rootToTip 0.55 -> 0.9 a gap pixel writes this much
                                                // lift (the skin behind takes 1 - it of the AO)
    aoTake: 0.5,                                // (round 2) how much of the HOST's screen-space AO the cards take at the
                                                // root, running to aoTakeTip by rootToTip 0.75 (0 = none: the coat's own
                                                // occlusion only). 0.8 was judged on the shaggy crest at N8AO's default
                                                // 0.3 m (g4_runtime/look/t5_take.png); up close it drew a dark line at
                                                // every card row's root, the shingle read (look/r11_aotake_mantle_px.png:
                                                // 0.90 % of the mantle close's pixels in dark strokes at 0.8, 0.33 % at
                                                // 0.5, 0.18 % at 0.3); 0.5 keeps the crest's depth and the tone within
                                                // the groom's layer_tone fit (+1.6..-1.5 levels against the maps alone)
    aoTakeTip: 0.6,                             // (round 2's integration) the take at the tip: the take runs from aoTake
                                                // at the root to this by rootToTip 0.75 (0 = the cards claim all of the
                                                // host's AO toward their tips: round 2's first default). With a GROUND in
                                                // the frame (the ladder film, any terrain) the harness AO's contact
                                                // darkens the skin and so the maps alone (the ladder's far end); tips
                                                // that claimed it all back left the shaggy coat 15-16 levels LIGHTER than
                                                // its far end at 1.75-3 m. 0.6 (with layerAOClaim 0.5) keeps it within
                                                // 2.6 levels at every step, TAA and clip (work/bestiary/coat/g4/
                                                // g4_integrate/NOTES.md, tone_r2_s5.json); floating with nothing near,
                                                // the coat then reads 3.5-7.3 darker than its maps (0 kept that within
                                                // 2.5). A fin coat's tips stay at 0
    aoTakeFar: 0.88,                            // (g5) THE TAKE PAST THE CLOSE-UP, root and tip alike: the partial take is
    aoFarLo: 0.4, aoFarHi: 0.8,                 // for the crest, where the 0.3 m AO counts card layers as solid; from afar
                                                // cards lie within a pixel of the skin, and a take of 0.5-0.6 left the coat
                                                // +5.1 levels over its maps at 15 m with a ground in the frame (-0.35 floating),
                                                // since the pass claims a card's whole footprint, the skin showing through
                                                // its dither too; a take of 1 goes -3.0 (the cards' own depth still counts).
                                                // 0.88: coat - maps with a ground -0.1 .. +0.9 from 8 to 45 m, floating -4.1 at
                                                // 8 m, -2.5 at 15 m, -0.8 at 45 m, the coat's L* 3 -> 15 m +3.0 -> +1.1 (the
                                                // maps' +0.3; tone_f1.json, tone_h1.json, tone_h3.json). Blended in over the
                                                // share of ranks drawn, aoFarHi .. aoFarLo (~5 to ~20 m at 1080p), none
                                                // for a fin coat
    aoHostLo: 0.5, aoHostHi: 7.5,               // (g5, 10-31) THE TAKES FOLLOW THE HOST'S AO SCALE: aoTake, aoTakeTip and
                                                // aoTakeFar above were all tuned under the harness's N8AO at 0.3 m, which
                                                // darkens a whole 0.4 m creature (people-scale): the skin and the maps take
                                                // that whole, the cards a share, and the coat matched its maps. At a radius
                                                // from the arm's own width (0.02 m, the lead's 18:3x A/B) the maps and the
                                                // bare octopus come out ~7 L* lighter while N8AO still counts card layers
                                                // as occluders, so the same takes left the coat 14.8 levels under its maps
                                                // at 1.75 m (-0.2 at 45 m), and every take of 0 balanced it (-1.8 .. -3.1;
                                                // look/tone_a2.json, tone_k1-k3.json). So the three takes scale by CU.hostTake,
                                                // a smoothstep in log(radius / the coat's length, manifest length_m) from
                                                // aoHostLo (none) to aoHostHi (all): 0.02 / 0.040 = 0.5 and 0.3 / 0.040 = 7.5
                                                // on shaggy, the two radii measured; between them a guess. coatLOD reads the
                                                // radius each frame (globalThis._n8ao); no host AO, no change
    strandRamp: 0.0,                            // (round 2) root darkening / tip lift from each strand's own root-to-tip
                                                // (the attribute page's B) instead of the card's (1 = the strand's)
    // alpha
    cut: 0.34,                                  // (build-time) the alpha test; the clip table is relative to it
    mipBias: 0.0,                               // the coverage page sampled this many levels sharper (study T: -1)
    dither: 1.0,                                // (round 2) the COVERAGE MODE: 1 = dithered (the coverage fraction against
                                                // a per-pixel threshold, which TAA resolves into partial coverage), 0 = the
                                                // clip (one hard threshold on the page). (g5) dithered with or without TAA:
                                                // attachCoat stills the pattern for a host with no TAA (ditherWalk 0, taaBias
                                                // 0), a stipple that the host's FXAA softens: the clip drew one hard stroke per
                                                // strand edge, bark or chipped paint even at the hero, and boiled twice as
                                                // much (% of the creature > 24 levels per frame, six stations 2.0-4.7 -> 0.9-2.3,
                                                // the swim arm 17.7 -> 13.7: look/m1_plain.png, m1_motion.png). A host with no
                                                // post filter at all may prefer dither 0
    clipBias: 0.0,                              // the clip reads the coverage this many levels coarser (fine strands merge
                                                // into stable locks before the threshold); 1 on atlas v3: no gain (rk)
    ditherWalk: 1.0,                            // (g5) the dither's golden-ratio walk per frame (1 = TAA's; 0 = a pattern that
                                                // holds still, for a host with no history to average it)
    ditherDecor: 1.0,                           // (g5) each card's dither threshold offset by its own random (x this): the
                                                // card layers over a pixel test independently (0 = round 2's shared
                                                // threshold, which resolved overlapping layers to their max: a veil)
    taaBias: -1.0,                              // (g5) the DITHER reads the coverage and the attribute page this many
                                                // levels sharper (the study-T mip bias -1, which its temporal dither resolves):
                                                // each frame shades the strands themselves, TAA averages them (the
                                                // resolve's correlation with a 16-sample reference 0.48 -> 0.58 at the
                                                // mantle close, cov_measure_b3)
    lockShade: 0.0,                             // (g5) a lock's edges dimmer than its core: the coverage read lockLevels
    lockLevels: 2.0,                            // coarser (the sub-lock's density) less the same three levels coarser
                                                // still (the tile's), the card x (1 + 2 lockShade x that): a modulation
                                                // about the card's mean, which the mips take to 0 with distance (built
                                                // when > 0; off by default: the round lock and the layer's depth carry it)
    lockBend: 0.9,                              // (g5; built when > 0 at attach, never on fins) a card shades as a ROUND
                                                // lock: its diffuse normal tilted across its width (side -1..1 x this,
                                                // toward the strand's sideways axis), its middle facing the light, its
                                                // edges turning away; the tilt's mean loss of light (asinh(k) / k for a
                                                // light along the normal) is given back, so the card's mean holds
    edgeFade: 0.6, edgeLo: 0.05, edgeHi: 0.28,  // edge-on cards fade (|card normal . view| below edgeHi)
    minPx: 1.1, maxWidth: 1.7,                  // SPECIMEN's width floor in delivered pixels, and its cap
    rankFade: 0.8,                              // how many ranks the LOD dissolve spans
    rootFade: 1.0, rootFadeLo: 0.12, rootFadeHi: 0.45,   // cards fade where the coat pack's density at the root thins
                                                // (rootFadeLo .. rootFadeHi of its R) toward a bare zone (0 = off)
    finOnly: 0.0, finLo: 0.22, finHi: 0.50,     // a short coat's cards as FINS: drawn only where the root normal turns
                                                // edge-on to the view (|N.V| under finLo .. finHi), the maps face-on
    finRim: 0.25,                               // (g5) the fins' share of the layer's grazing brightening (1 = round 2's:
                                                // fins sat ON the layer's bright rim then; pushed, they show only past
                                                // the outline, against what lies behind, where the full lift drew them
                                                // as pale flecks and thorns: look/b4_velvet_finrim*.png; the layer's rim
                                                // and its velvet lobe carry the grazing read)
    finSheen: 0.3,                              // (g5) the fins' share of the velvet lobe (x look.sheen): a fin's root normal
                                                // sits at N.V ~0, the lobe's peak, over its WHOLE face, where on the layer
                                                // that peak is a hairline at the outline: at 1 the fins stood ~4 x the
                                                // body's linear light, pale paper chips (look/b8_fins_sand.png); the
                                                // layer's rim and its lobe carry velvet's grazing read
    finZoneBlur: 3.0,                           // (coat G6; fins only) how many mip levels coarser than its root's footprint a
                                                // fin reads the zone masks and the display (a remix's zones, bestiary's
                                                // display families), so a thin zone never lines the outline (0 = off)
    finAffixFade: 1.0,                          // (coat G6; fins only) how far a remix's creature-wide glow (rim_pulse,
                                                // glint) fades along a fin from its root to its tip (0 = whole fin)
    finEdge: 0.3,                               // (coat G6; fin coats) while the fins are drawn the skin layer's grazing
                                                // terms (its rim, its velvet lobe) read |N.V| as at least this, so they
                                                // plateau over the outline's last pixels, where the fins carry the light,
                                                // instead of peaking in a 1 px line on the skin's silhouette (0 = off)
    finPush: 0.015,                             // (g5; fins only) metres each fin is pushed away from the camera along
                                                // its own view ray (its screen position kept): over the body the skin
                                                // then hides it, past the outline nothing does, so a fin shows only where
                                                // it stands out against what lies behind (0 = off)
    finTake: 0.6,                               // (g5, 10-31; fin coats) the fins' share of the host's screen-space AO, root
                                                // and tip alike (-1: round 2's, aoTake at the root running to none at the
                                                // tip). At an INNER silhouette (an arm crossing the head at Skye's sand
                                                // frame) the fins stood as a pale ribbon 25-30 px wide, 1.66 x the skin
                                                // around them in linear light: the skin there takes N8AO whole, the fins
                                                // hardly any. Whole is too much: N8AO reads a fin at its pushed depth,
                                                // 15 mm behind the edge, a trench (ao ~0.18 in that crevice, ~0.83 on
                                                // an open outline): 1 drew the ribbon black and a dark stroke round the
                                                // outline. 0.6: the band 139 -> 112 levels (bare 117), the outer
                                                // fringe / skin rim 0.965 -> 0.923 (look/v14b_takes.png, fin_line.py)
    // motion (metres; wind along windDir in the WORLD, turned into the creature's space each frame)
    sway: 0.0007, wind: 0.0, windSpeed: 0.78, windFreq: 0.9, windK: 6.0, windDir: [1.0, 0.0, 0.35],
    // LOD
    lodBias: 1.0,                               // multiplies the screen size (> 1 keeps detail longer)
    // the skin's coat layer (coatSkinLayer)
    layerNear: 0.80, layerFar: 1.0,             // how much fur colour the skin takes with cards drawn / without
    layerRoughness: 0.80, layerSheen: 0.9, layerSpec: 0.30, layerSSS: 0.25,   // layerSheen: the grazing rim's gain
    sheen: 1.0, sheenRough: 0.3, sheenTint: 0.25,   // (round 2) THE VELVET LOBE (Charlie, Estevez & Kulla 2017) on the
                                                // skin's coat layer and on fin cards, brighter at grazing: its gain (0 =
                                                // off), its roughness, its colour from the fur's toward white. 0.3, not
                                                // 0.5: at 0.5 the lobe lifted the face as much as the outline (a paler
                                                // velvet, not a velvet cue); at 0.3 the outline keeps its 5-12 levels and
                                                // the face's lift falls to 2-7 (work/bestiary/coat/g4/g4_runtime/SHEEN.md)
    sheenModel: 0.0,                            // 0 Charlie, 1 Ashikhmin's velvet (the comparison in SHEEN.md)
    layerFlat: 1.0,                             // how far the skin's own relief (its normal map) gives way under the coat
    layerBump: 0.35,                            // the coat's strand relief from its height (G) as a bump (0 = smooth)
    layerDetail: 0.35,                          // the strands in the coat's colour: deep gaps darker, tall tips lighter
    layerSoften: 2.5,                           // the skin's fine colour (pores, papillae dots) blurred under the coat
                                                // by this many mip levels (0 = off), and (g5) never past layerSoftenMm
    layerSoftenMm: 3.0,                         // on the skin: a blur relative to the pixel's own footprint grows with
                                                // distance, and by 15 m it pulled the bare zones' pale colour (eye rings,
                                                // the sucker side, the oral web) into the fur: THE MAPS' DISTANCE DRIFT
                                                // (batch 3, tone_drift.py: maps - bare +2.5 / +4.3 / +6.3 / +9.9 levels at
                                                // 3 / 5 / 8 / 15 m, layerSoften 0 +1.8 / +1.8 / +1.6 / +1.5)
    layerAOClaim: 0.5,                          // (round 2's integration; built when > 0 at attach) how much of the
                                                // host's screen-space AO the FURRED SKIN claims back while cards are
                                                // drawn over it (x the pack's density x the close-up's weight CU.closeW:
                                                // none from ~10 m out, none for a fin coat): the skin seen between card
                                                // rows otherwise takes the AO of the cards in the depth buffer whole (a
                                                // black crevice under the mantle at 0.3 m; at 0.5 about the bare
                                                // creature's own crevice: g4_integrate/look/a10_ao_settings_taa.png)
    layerDeep: 0.7,                             // (g5) the furred skin seen BETWEEN drawn cards is the coat's interior:
                                                // its colour x (1 - layerDeep x the pack's density x CU.closeW), the
                                                // close-up's weight below (none past ~8 m, where no gap resolves: at the
                                                // share of ranks drawn alone it still took 3.5 levels off the coat at 15 m)
    cardLift: 0.35,                             // (g5) layerDeep's pair: the cards' colour x (1 + cardLift x CU.closeW), so
                                                // up close the coat trades contrast about the same mean (lighter strands
                                                // over darker gaps), with no tone left to hand over at distance (on atlas
                                                // v3, coat - maps own -8.1 / -5.7 / -1.6 at 1.75 / 3 / 5 m at 0, -1.5 /
                                                // -0.9 / +0.3 at 0.35, nothing past 8 m: look/tone_c1.json, tone_c3.json)
    layerInterior: 1.0,                         // (coat G6, 11-01) layerDeep's other half: between drawn cards the furred skin
                                                // is the coat's interior, so it loses its TOP's grazing terms, the rim
                                                // (layerSheen), the velvet lobe and the wet skin's gloss, by this x the
                                                // pack's density x CU.closeW (the cards carry the coat's grazing light up
                                                // close; far off, closeW 0, the layer is the whole coat and keeps them).
                                                // Seen against the grain at grazing (the mantle's back from low behind,
                                                // the cards edge-on), the layer between them read as a pale smooth sheen
                                                // with hair strokes painted on it (g6/look/la1_layer.png)
    closeLo: 0.6, closeHi: 1.0,                 // (g5) the close-up's weight CU.closeW: smoothstep over the share of ranks
                                                // drawn (1 from all ranks, ~2.2 m at 1080p, to 0 at 60 %, ~10 m)
    cardTone: [1.0, 1.0, 1.0],                  // (g5) a LINEAR RGB multiplier on the CARDS' colour at every distance (the
                                                // runtime's trim of the hand-over; layerTone, below, is the groom's match
                                                // of the maps)
    layerTone: [1.0, 1.0, 1.0],                 // (round 2) a LINEAR RGB multiplier on the layer's fur colour at every
                                                // distance: the groom's match of the maps to the cards' screen average
                                                // (the forge's layer_tone; work/bestiary/coat/g4/g4_runtime/TONE.md). One
                                                // [r, g, b], or { <base material>: [r, g, b] } per skin set
};

const VEC3_KEYS = ['color', 'tint', 'windDir', 'layerTone', 'cardTone', 'dye'];
const BUILD_KEYS = ['cut'];

function toColor(v) {
    if (v == null) return null;
    if (Array.isArray(v)) return new THREE.Color().setRGB(v[0], v[1], v[2]);
    return new THREE.Color(v);                    // hex / css: sRGB -> the linear working space
}

// the forge's manifest names its look in snake case (forge/groom styles/*.json "look"); root_dark is an AMOUNT there
// (0.25 = roots 25 % darker), rootDark here the multiplier at the root
const FORGE_LOOK = {
    tip_lift: ['tipLift', (v) => v], root_dark: ['rootDark', (v) => 1 - v], value_jitter: ['valueJitter', (v) => v],
    hue_jitter: ['hueJitter', (v) => v], rank_fade: ['rankFade', (v) => v], strand_jitter: ['strandJitter', (v) => v],
    fin_only: ['finOnly', (v) => v],
    // (round 2) an atlas v2 style's runtime keys
    strand_ramp: ['strandRamp', (v) => v], clip_bias: ['clipBias', (v) => v], sheen: ['sheen', (v) => v],
    sheen_rough: ['sheenRough', (v) => v], sheen_tint: ['sheenTint', (v) => v], ao_take: ['aoTake', (v) => v],
    layer_tone: ['layerTone', (v) => v],
    // (round 2's integration)
    ao_take_tip: ['aoTakeTip', (v) => v], layer_ao_claim: ['layerAOClaim', (v) => v],
    // (g5) the close-up's strand shading and the coat's interior
    strand_hue: ['strandHue', (v) => v], rough_jitter: ['roughJitter', (v) => v], taa_bias: ['taaBias', (v) => v],
    lock_shade: ['lockShade', (v) => v], layer_deep: ['layerDeep', (v) => v], lock_bend: ['lockBend', (v) => v],
    card_tone: ['cardTone', (v) => v], card_lift: ['cardLift', (v) => v], ao_take_far: ['aoTakeFar', (v) => v],
    fin_take: ['finTake', (v) => v],
    // (W3a) the tip colour
    tip_mix: ['tipMix', (v) => v], tip_start: ['tipStart', (v) => v], tip_end: ['tipEnd', (v) => v],
    tip_jitter: ['tipJitter', (v) => v], tip_share: ['tipShare', (v) => v], layer_tip: ['layerTip', (v) => v],
    band_sel: ['bandSel', (v) => v], tip_inner: ['tipInner', (v) => v],
};

function lookFromForge(l) {
    if (!l) return null;
    const out = {};
    for (const [k, v] of Object.entries(l)) {
        if (FORGE_LOOK[k]) out[FORGE_LOOK[k][0]] = FORGE_LOOK[k][1](v);
        else if (k in COAT_LOOK) out[k] = v;
    }
    return out;
}

export function coatUniforms(manifestLook, ...looks) {
    // the coat's uniforms from the defaults, the forge's look (the manifest's, snake case) and any looks over them
    // (opts.look); CU.look holds the resolved values, CU.set(look) changes them live
    const look = Object.assign({}, COAT_LOOK, lookFromForge(manifestLook), ...looks.filter(Boolean));
    const CU = { look };
    for (const [k, v] of Object.entries(look)) {
        if (BUILD_KEYS.includes(k)) continue;
        if (k === 'layerTone' && v && typeof v === 'object' && !Array.isArray(v)) {
            // (round 2) the layer's tone per skin set ({ octopus_head: [r, g, b], ... }); a set it does not name keeps
            // the shared CU.layerTone, [1, 1, 1]
            CU.layerToneBy = Object.fromEntries(Object.entries(v).map(([n, c]) => [n, THREE.uniform(toColor(c))]));
            CU[k] = THREE.uniform(new THREE.Color(1, 1, 1));
            continue;
        }
        if (VEC3_KEYS.includes(k)) {
            CU[k] = k === 'windDir' ? THREE.uniform(new THREE.Vector3().fromArray(v).normalize())
                : THREE.uniform(toColor(v));
        } else if (typeof v === 'number') {
            CU[k] = THREE.uniform(v);
        }
    }
    // driven per frame: the LOD's cut (ranks drawn, continuous), the survivors' width, the skin layer's weight, the
    // wind's direction in the creature's space
    CU.rankCut = THREE.uniform(1e6);
    CU.widthScale = THREE.uniform(1.0);
    CU.layerW = THREE.uniform(look.layerNear);
    // (g5) the close-up's weight, 0 .. 1 (look.closeLo .. closeHi over the share of ranks drawn; 0 for a fin coat; coatLOD
    // sets it each frame, 0 until then): all the furred skin does because cards lie over it follows it, so past it the skin
    // is exactly the maps' skin and the cards alone tell the two apart: the interior's darkness and the cards' lift
    // (layerDeep, cardLift), the skin's own colour under the fur (layerNear), its AO claim (layerAOClaim)
    CU.closeW = THREE.uniform(0.0);
    // (g5) the far take's weight, 0 .. 1 (look.aoFarHi .. aoFarLo over the same share; 0 for a fin coat; coatLOD sets it)
    CU.farW = THREE.uniform(0.0);
    // (coat G6) a fin coat's fins' presence, 0 .. 1 (the share of ranks drawn; 0 for a card coat; coatLOD sets it): the
    // layer's outline plateau (look.finEdge) follows it, so with no fins drawn the layer keeps its whole grazing peak
    CU.finW = THREE.uniform(0.0);
    // (g5, 10-31) the takes' scale by the host's AO radius over the coat's length (look.aoHostLo .. aoHostHi; coatLOD sets it,
    // 1 until then and with no host AO)
    CU.hostTake = THREE.uniform(1.0);
    CU.windLocal = THREE.uniform(new THREE.Vector3(1, 0, 0));
    // (round 2) the dither's frame counter (coatLOD advances it once per rendered frame)
    CU.frame = THREE.uniform(0.0);
    CU.set = (l = {}) => {
        for (const [k, v] of Object.entries(l)) {
            if (!(k in CU) || v == null || BUILD_KEYS.includes(k)) continue;
            look[k] = v;
            if (k === 'layerTone' && typeof v === 'object' && !Array.isArray(v)) {
                // per skin set: the sets named at attach time take their new values (a shader holds only those)
                for (const [n, c] of Object.entries(v)) CU.layerToneBy?.[n]?.value.copy(toColor(c));
                continue;
            }
            if (k === 'windDir') CU[k].value.fromArray(v).normalize();
            else if (VEC3_KEYS.includes(k)) CU[k].value.copy(toColor(v));
            else CU[k].value = v;
        }
    };
    return CU;
}

// ============================================================================================ hashes (per card)
function hashes(rnd) {
    const { fract, sin } = THREE;
    return [
        fract(sin(rnd.mul(91.7).add(17.3)).mul(43758.5453)),
        fract(sin(rnd.mul(173.3).add(41.1)).mul(24634.6345)),
        fract(sin(rnd.mul(269.5).add(11.7)).mul(56445.2341)),
    ];
}

// ============================================================================================ the lighting model
// Unreal's hair BSDF (ShadingModels.ush HairShading / KajiyaKayDiffuseAttenuation, Karis 2016), its tangent pointing
// to the ROOT (our TANGENT points to the tip: negated), the azimuth from the projections onto the strand's normal
// plane, the longitudinal lobes as Gaussians in sin(theta_i) + sin(theta_r). Added to it: SPECIMEN's wrap diffuse about
// the root's base normal, and a body visibility on R / TRT / scatter (the coat's own self-shadowing is absent on cards,
// so the body's terminator bounds them; TT keeps a wider one: back light passes the silhouette's tips).
const F0_HAIR = ((1 - 1.55) / (1 + 1.55)) ** 2;
const INV_SQRT_2PI = 1 / Math.sqrt(2 * Math.PI);

function hairF(c) {
    return THREE.float(F0_HAIR).add(THREE.float(1 - F0_HAIR).mul(THREE.float(1).sub(c).clamp(0, 1).pow(5)));
}

function hairG(B, x) {
    return x.mul(x).mul(-0.5).div(B.mul(B)).exp().mul(INV_SQRT_2PI).div(B);
}

// ============================================================================================ the velvet lobe
// (round 2) THE CUE THAT SAYS VELVET: a pile's fibres seen side-on at grazing, so the outline BRIGHTENS. Charlie
// (Estevez & Kulla 2017, "Production Friendly Microfacet Sheen BRDF": D = (2 + 1/a) sin(theta_h)^(1/a) / 2 pi, a =
// roughness^2), the sheen of glTF (KHR_materials_sheen), Filament's cloth and three's own, chosen over Ashikhmin's velvet
// (an inverted Gaussian with a sin^-4 peak at exact grazing). Measured on the velvet octopus the two read alike (the
// outline's profile within 1 level, the silhouette's crawl 3.6 vs 3.3 % of its band, the fins' flips dominating both);
// Charlie for what is around it: the standard sheen, a published albedo fit for the environment's share, a finite
// maximum at every roughness (work/bestiary/coat/g4/g4_runtime/SHEEN.md). With
// Neubelt's visibility 1 / (4 (NL + NV - NL NV)) held off zero: three's sheen divides by it unguarded, and where N.L and
// N.V both clamp to 0 (the webs' folds, a coat layer's grazing pixels) that is 0 x inf = NaN, the black cracks of the
// 10-29 maps-only stills. velvetDirect returns the lobe x N.L (radiance per unit of light colour); velvetAlbedo the
// lobe's directional albedo under uniform light (three's IBLSheenBRDF fit), for the environment's share
function velvetDirect(N, V, L, rough, model = null) {
    // (g5) both of three r184's traps closed here as M2c's check closed its own (work/bestiary/patches/
    // scratch_crossbreed_m2/m2c_check/NOTES.md): N.V held at 1e-3 or more (a bumped normal turned from the eye), and the
    // half vector's length held off zero (L = -V); with the visibility's floor below no term can reach 0 x inf
    const { float } = THREE;
    const nl = N.dot(L).clamp(0, 1), nv = N.dot(V).clamp(1e-3, 1);
    const lv = L.add(V);
    const nh = N.dot(lv.div(lv.length().max(1e-4))).clamp(0, 1);
    const a = rough.mul(rough).max(0.01);
    const inv = float(1).div(a);
    const sin2 = float(1).sub(nh.mul(nh)).max(0.0078125);
    let D = float(2).add(inv).mul(sin2.pow(inv.mul(0.5))).mul(1 / (2 * Math.PI));
    if (model) {
        // look.sheenModel 1: Ashikhmin's velvet (Ashikhmin & Premoze 2007; The Order: 1886's cloth), kept for the
        // comparison SHEEN.md reports: 1 / (pi (1 + 4 a^2)) x (1 + 4 exp(-cot^2 / a^2) / sin^4)
        const cot2 = nh.mul(nh).div(sin2);
        const Da = float(1).add(cot2.div(a.mul(a)).negate().exp().mul(4.0).div(sin2.mul(sin2)))
            .div(float(1).add(a.mul(a).mul(4.0)).mul(Math.PI));
        D = THREE.mix(D, Da, model.clamp(0, 1));
    }
    const vis = float(1).div(nl.add(nv).sub(nl.mul(nv)).max(1e-3).mul(4.0));
    return D.mul(vis).mul(nl);
}

function velvetAlbedo(N, V, rough) {
    const { float } = THREE;
    const nv = N.dot(V).clamp(1e-3, 1);
    const r2 = rough.mul(rough), rInv = rough.add(0.1).reciprocal();
    const a = float(-1.9362).add(rough.mul(1.0678)).add(r2.mul(0.4573)).sub(rInv.mul(0.8469));
    const b = float(-0.6014).add(rough.mul(0.5538)).sub(r2.mul(0.4670)).sub(rInv.mul(0.1255));
    return a.mul(nv).add(b).exp().clamp(0, 1);
}

// (coat G6) N lifted toward the eye so N.V is at least `floor` (its azimuth about V kept; N itself where N.V is already
// there): a lobe read with it plateaus over the last pixels of an outline instead of peaking on the outline's last one
function liftNormal(N, V, floor) {
    const { float } = THREE;
    const nv = N.dot(V);
    const side = N.sub(V.mul(nv)).add(N.mul(1e-4)).normalize();
    const lifted = side.mul(float(1).sub(floor.mul(floor)).max(0.0).sqrt()).add(V.mul(floor));
    return THREE.select(nv.lessThan(floor), lifted, N);
}

// (the stage-3 landing, 10-30) THE TWO CLASSES ARE BUILT ON FIRST USE (coatClasses, below). Their bases, three's
// PhysicalLightingModel and MeshStandardNodeMaterial, exist only in its WebGPU build: declared at load, they threw
// 'Class extends value undefined' as this module loaded under core three ('npm:three@0.184.0': the cable harness
// tests/c05d_runtime.mjs that c05c and c03d run, M2's motion tools), and bestiary.js imports this file. So each class is
// returned by a factory that coatClasses calls the first time a coat material is made: a creature without a coat and
// every core-three harness never build them
const coatLightingModelClass = () => class CoatLightingModel extends THREE.PhysicalLightingModel {
    constructor(material) {
        super(false, false, false, false, false, false);
        this.coat = material.coatNodes;
    }

    direct({ lightDirection: L, lightColor, reflectedLight }) {
        const { float, vec3, max, mix, smoothstep, sqrt, exp, pow, dot } = THREE;
        const c = this.coat;
        const albedo = THREE.diffuseColor.rgb;
        const N = THREE.normalViewGeometry.normalize();              // the ROOT's base normal (never the card's)
        const V = THREE.positionViewDirection.normalize();
        const T = c.T.negate();                                      // Unreal's convention: toward the root
        const nl = N.dot(L).clamp(-1, 1);

        // ---- diffuse: SPECIMEN's energy-normalised wrap about N (integrates to Lambert), scaled by the self-shadow
        // (g5: about the card's ROUND-LOCK normal when look.lockBend builds one, c.Nd; the body's terminator below stays
        // the root's)
        const nld = c.Nd ? c.Nd.dot(L).clamp(-1, 1) : nl;
        const w = c.wrap, k = c.wrapMix;
        const D = nld.clamp(0, 1);
        const W = nld.add(w).div(float(1).add(w)).clamp(0, 1);
        const Dwrap = mix(D, W, k).div(float(1).add(k.mul(w)));
        const sinL = dot(T, L).clamp(-1, 1), sinV = dot(T, V).clamp(-1, 1);
        // the FREE TIPS (the integration, 10-29): a long coat's outer part stands off the body, past its silhouette,
        // where the root's terminator no longer says what light reaches a fibre (the cards rooted at the mantle's far
        // edge turn their root normals from the sun while their tips stand in it). Toward the tip (c.free = look.tipFree
        // x a ramp over rootToTip) the diffuse becomes the fibre's own Kajiya-Kay term about its tangent (sin(T, L) x
        // kkGain) and the terminator lets go; the body's shadow map, which the cards receive, still darkens what the
        // body hides from the light
        const free = c.free ?? float(0.0);
        const kk = sqrt(float(1).sub(sinL.mul(sinL)).max(0)).mul(c.kkGain ?? 0.55);
        const Dfur = mix(Dwrap, kk, free);
        const vis = mix(smoothstep(-0.25, 0.30, nl), float(1), free);          // the body's terminator, soft
        const visTT = mix(smoothstep(-0.65, 0.05, nl), float(1), free);
        const body = albedo.mul(Dfur).mul(1 / Math.PI).mul(c.shadowH).mul(c.ndComp ?? float(1.0));
        // Unreal's scatter: a soft Kajiya-Kay term about a normal facing the viewer, sqrt(base colour) tinted
        const kd = float(1).sub(sinL.abs());
        const Nf = V.sub(T.mul(sinV)).normalize();
        const NoLf = Nf.dot(L).add(1).div(4).clamp(0, 1);
        const scat = sqrt(albedo.max(0)).mul(mix(NoLf, kd, 0.33)).mul(1 / Math.PI).mul(c.scatterW).mul(vis);
        reflectedLight.directDiffuse.addAssign(lightColor.mul(body.mul(float(1).sub(c.scatterW)).add(scat)));

        // ---- the three lobes
        const cosL = sqrt(float(1).sub(sinL.mul(sinL)).max(0));
        const cosV = sqrt(float(1).sub(sinV.mul(sinV)).max(0));
        const cosThetaD = sqrt(cosV.mul(cosL).add(sinV.mul(sinL)).mul(0.5).add(0.5).clamp(1e-3, 1));
        const Lp = L.sub(T.mul(sinL)), Vp = V.sub(T.mul(sinV));
        const cosPhi = dot(Lp, Vp).div(sqrt(dot(Lp, Lp).mul(dot(Vp, Vp)).add(1e-4)));
        const cosHalfPhi = sqrt(cosPhi.mul(0.5).add(0.5).clamp(0, 1));
        const VoL = dot(V, L);
        const r2 = c.rough.mul(c.rough).max(0.0025);
        const sumSin = sinL.add(sinV);
        // R: the white primary, shifted toward the root (alpha = -2 shift), Unreal's view-dependent shift
        const aR = c.shift.mul(-2.0);
        const sa = aR.sin(), ca = aR.cos();
        const shiftR = sa.mul(2.0).mul(ca.mul(cosHalfPhi).mul(cosV).add(sa.mul(sinV)));
        // (B6) dark albedo's weight (1 - rTint's light weight, below): the R narrowed and dimmed there (look.darkRWidth,
        // darkR), and the brows' / lashes' flag (c.matte x look.matteFace) takes their lobes away
        const lumD = dot(albedo, vec3(0.2126, 0.7152, 0.0722));
        const darkW = c.dark ? float(1).sub(smoothstep(0.012, 0.07, lumD)) : float(0.0);
        const r2R = c.dark ? r2.mul(mix(float(1), c.dark.width.mul(c.dark.width), darkW)).max(0.0016) : r2;
        const matteK = c.matte ? float(1).sub(c.matte.mul(c.matteFace).clamp(0, 1)) : float(1.0);
        const Mr = hairG(r2R.mul(Math.SQRT2).mul(cosHalfPhi).max(0.02), sumSin.sub(shiftR));
        const Rl = Mr.mul(cosHalfPhi.mul(0.25)).mul(hairF(sqrt(VoL.mul(0.5).add(0.5).clamp(0, 1))))
            .mul(c.specular.mul(2.0)).mul(mix(float(1), c.backlit, VoL.negate().clamp(0, 1)))
            .mul(c.dark ? mix(float(1), c.dark.gain, darkW) : float(1.0)).mul(matteK);
        // TT: through the strand, forward (back light through the tips), absorption from the colour
        const nPrime = float(1.19).div(cosThetaD).add(cosThetaD.mul(0.36));
        const a = float(1).div(nPrime);
        const hh = cosHalfPhi.mul(float(1).add(a.mul(float(0.6).sub(cosPhi.mul(0.8)))));
        const fTT = hairF(cosThetaD.mul(sqrt(float(1).sub(hh.mul(hh)).max(0))));
        const Mtt = hairG(r2.mul(0.5).max(0.02), sumSin.sub(c.shift));
        // (g5) A CARD IS A BUNDLE, NOT A FIBRE (look.ttBundle): Unreal's exponent is one strand's path, so Tt = albedo^~0.45, nearly
        // neutral on a dark coat, where light crossing a lock passes through several strands and comes out in the fur's own colour
        // (back-lit brown fur glows warm). At one strand's path a back light through the cards read pale grey-lilac over dark albedo:
        // Skye's sand frame, a host's cool rim light with no shadow, the web's top seen from beside it: rgb 115 90 82 over the fur's
        // 111 74 62, saturation 0.29 / 0.44 (not R, TRT, the environment, the sheen, the AO take or the scatter; backlit 0 took it)
        const Ttt = pow(albedo.max(1e-4), vec3(sqrt(float(1).sub(hh.mul(a).pow(2)).max(0)).mul(0.5).div(cosThetaD).mul(c.ttBundle ?? float(1.0))));
        const TT = Ttt.mul(Mtt.mul(exp(cosPhi.mul(-3.65).sub(3.98))).mul(float(1).sub(fTT).pow(2)))
            .mul(c.backlit).mul(c.ttMask);
        // TRT: the tinted secondary, shifted the other way, wider
        const fTRT = hairF(cosThetaD.mul(0.5));
        const Mtrt = hairG(r2.mul(2.0), sumSin.sub(c.shift.mul(4.0)));
        const Ttrt = pow(albedo.max(1e-4), vec3(float(0.8).div(cosThetaD)));
        const TRT = Ttrt.mul(Mtrt.mul(exp(cosPhi.mul(17.0).sub(16.78))).mul(float(1).sub(fTRT).pow(2).mul(fTRT)))
            .mul(c.trt ?? float(1.0));
        // (B5) the R lobe's colour (look.rTint): white .. the albedo's hue at full value
        // fading out on dark hair (b5 z1: black's albedo normalised to full value is pure red; on dark hair the
        // white R is what the eye sees, the TRT absorbed), full by a luminance of 0.08 (the brown preset's ~0.07)
        const hue = albedo.div(max(albedo.x, max(albedo.y, albedo.z)).max(1e-4));
        const lum = dot(albedo, vec3(0.2126, 0.7152, 0.0722));
        const lightW = smoothstep(0.012, 0.07, lum);
        const Rcol0 = c.rTint ? mix(vec3(1.0), hue, c.rTint.clamp(0, 1).mul(lightW)) : vec3(1.0);
        // (B6) on dark albedo a cool white (look.darkRCool)
        const Rcol = c.dark ? mix(Rcol0, vec3(0.82, 0.90, 1.0), c.dark.cool.mul(darkW)) : Rcol0;
        // (B5 face, black) TRT's gain above 1 likewise on light hair only: x4 on black's dark-red albedo drew red patches
        // on the brows and the fringe (b5_face_red.png: gone at trt 1, not at rTint 0)
        const trtW = c.rTint ? mix(float(1.0), c.trt ?? float(1.0), lightW).div((c.trt ?? float(1.0)).max(1e-3)) : float(1.0);
        const spec = Rcol.mul(Rl).add(TRT.mul(trtW).mul(matteK)).mul(vis).mul(c.shadowH.sqrt()).add(TT.mul(visTT));
        reflectedLight.directSpecular.addAssign(lightColor.mul(max(spec, vec3(0.0))));
        // (round 2) a FIN's velvet lobe about the root normal, as the skin layer's (coatSkinLayer)
        if (c.velvet) {
            const sc = mix(albedo, vec3(1.0), c.velvet.tint).mul(c.velvet.gain);
            reflectedLight.directSpecular.addAssign(lightColor.mul(sc).mul(velvetDirect(N, V, L, c.velvet.rough, c.velvet.model)));
        }
    }

    indirectSpecular(builder) {
        // the coat's environment light. three's own indirect specular is a Fresnel (DFG) term about the shading normal,
        // here the ROOT's base normal: where the body turns away (N.V -> 0) it reflected the sky at near-mirror strength
        // and turned the cards at the body's silhouette silver-grey (the 10-29 shaggy stills, the mantle's edge). A
        // coat's fibres face every way, so the skin's grazing angle says nothing about theirs (Unreal's hair has no
        // Fresnel about a surface normal either): the coat keeps a dim white R share of the pre-filtered radiance at the
        // fibre's F0 with no grazing boost, and the IBL's diffuse share three adds here (its irradiance over pi, the
        // energy the specular did not take) as it was
        const { radiance, iblIrradiance, reflectedLight } = builder.context;
        const c = this.coat;
        let envR = radiance.mul(c.specular.mul(2.0 * F0_HAIR)).mul(c.envSpec ?? THREE.float(1.0));
        // (B6) on dark albedo look.darkEnv; the brows / lashes (matteFace) none
        if (c.dark) {
            const lumD = THREE.dot(THREE.diffuseColor.rgb, THREE.vec3(0.2126, 0.7152, 0.0722));
            envR = envR.mul(THREE.mix(THREE.float(1), c.dark.env, THREE.float(1).sub(THREE.smoothstep(0.012, 0.07, lumD))));
        }
        if (c.matte) envR = envR.mul(THREE.float(1).sub(c.matte.mul(c.matteFace).clamp(0, 1)));
        reflectedLight.indirectSpecular.addAssign(envR);
        reflectedLight.indirectDiffuse.addAssign(THREE.diffuseColor.rgb.mul(iblIrradiance.mul((1 - F0_HAIR) / Math.PI)));
        // (round 2) a FIN's velvet lobe under the environment (its albedo x the irradiance's radiance), as the layer's
        if (c.velvet) {
            const N = THREE.normalViewGeometry.normalize(), V = THREE.positionViewDirection.normalize();
            const sc = THREE.mix(THREE.diffuseColor.rgb, THREE.vec3(1.0), c.velvet.tint).mul(c.velvet.gain);
            reflectedLight.indirectSpecular.addAssign(iblIrradiance.mul(1 / Math.PI).mul(sc).mul(velvetAlbedo(N, V, c.velvet.rough)));
        }
    }
};

const coatNodeMaterialClass = (CoatLightingModel) => class CoatNodeMaterial extends THREE.MeshStandardNodeMaterial {
    static get type() { return 'CoatNodeMaterial'; }
    setupLightingModel() { return new CoatLightingModel(this); }
};

let COAT_CLASSES = null;
export function coatClasses() {
    // { CoatLightingModel, CoatNodeMaterial }, built once, the first time they are used (coatMaterial, shellMaterial)
    if (!COAT_CLASSES) {
        const CoatLightingModel = coatLightingModelClass();
        COAT_CLASSES = { CoatLightingModel, CoatNodeMaterial: coatNodeMaterialClass(CoatLightingModel) };
    }
    return COAT_CLASSES;
}

// ============================================================================================ attribute names
export function coatAttributeNames(geometry) {
    // GLTFLoader lowercases custom names (_FURDATA -> _furdata); SPECIMEN's bundles name them furData ...
    const pick = (...n) => n.find((x) => geometry?.getAttribute?.(x)) || n[0];
    return {
        furData: pick('_furdata', 'furData', '_FURDATA'),
        rootData: pick('_rootdata', 'rootData', '_ROOTDATA'),
        furCenter: pick('_furcenter', 'furCenter', '_FURCENTER'),
    };
}

export function vertexBufferCount(geometry) {
    // what r184 binds: one buffer per plain attribute, one per InterleavedBuffer
    const seen = new Set();
    for (const a of Object.values(geometry.attributes)) seen.add(a.isInterleavedBufferAttribute ? a.data : a);
    return seen.size;
}

// ============================================================================================ the coverage page as R8
// (the g4 check, 10-30) ONE R8 page per SOURCE texture: every coat primitive (one material each: the octopus has two)
// samples the same coverage page, and the per-material cache below built and uploaded an identical R8 page for each
// (measured: two R8 textures from one source, +5.33 MB of GPU memory per style)
const _coverageR8 = new WeakMap();
function coverageR8(tex) {
    // (round 2) the coverage page as ONE channel: the eidoverse harness migrates every glTF image to an RGBA DataTexture
    // (with CPU box mips), four bytes per texel for a page whose meaning is one; this keeps its R in an R8 texture with
    // its own box mips (rounded, where the harness's truncate: a coverage chain should not drift dark level by level),
    // a quarter of the memory. Any other texture (a browser's ImageBitmap) is returned as it is
    const img = tex?.image;
    if (!tex?.isDataTexture || !img?.data || img.data.length !== img.width * img.height * 4) return tex;
    const built = _coverageR8.get(tex);
    if (built) return built;
    const w = img.width, h = img.height;
    const r = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) r[i] = img.data[4 * i];
    const levels = [{ data: r, width: w, height: h }];
    let sw = w, sh = h, src = r;
    while (sw > 1 || sh > 1) {
        const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
        const dst = new Uint8Array(dw * dh);
        for (let y = 0; y < dh; y++) {
            const y0 = Math.min(sh - 1, 2 * y) * sw, y1 = Math.min(sh - 1, 2 * y + 1) * sw;
            for (let x = 0; x < dw; x++) {
                const x0 = Math.min(sw - 1, 2 * x), x1 = Math.min(sw - 1, 2 * x + 1);
                dst[y * dw + x] = (src[y0 + x0] + src[y0 + x1] + src[y1 + x0] + src[y1 + x1] + 2) >> 2;
            }
        }
        levels.push({ data: dst, width: dw, height: dh });
        sw = dw; sh = dh; src = dst;
    }
    const t = new THREE.DataTexture(r, w, h, THREE.RedFormat, THREE.UnsignedByteType);
    t.mipmaps = levels;
    t.generateMipmaps = false;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.magFilter = THREE.LinearFilter;
    t.anisotropy = Math.max(8, tex.anisotropy || 1);
    t.wrapS = tex.wrapS; t.wrapT = tex.wrapT;
    t.flipY = false;
    t.colorSpace = THREE.NoColorSpace;
    t.name = `${tex.name || 'coverage'}_r8`;
    t.needsUpdate = true;
    _coverageR8.set(tex, t);
    return t;
}

// ============================================================================================ the root colour
function rootColour(base, U, rootUV, rootLod, opts, zoneLod = rootLod) {
    // the base material's albedo at the root (explicit level: one root UV per card, implicit mips would crawl), the
    // remix's zone remap over the packs read at the same UV, the bestiary tint, the skin's display families at the root
    // ((coat G6) the packs, the zones' masks and the display, at zoneLod: a fin's are read coarser, coatMaterial's
    // look.finZoneBlur, so a thin zone never lines the outline)
    const { texture, vec4 } = THREE;
    let col = texture(base.map, rootUV).level(rootLod).rgb;
    const masks = base.thicknessMap ? texture(base.thicknessMap, rootUV).level(zoneLod) : vec4(0.0, 0.0, 0.0, 0.5);
    const disp = base.emissiveMap ? texture(base.emissiveMap, rootUV).level(zoneLod) : vec4(0.0, 0.0, 0.0, 0.5);
    if (opts.remap) col = opts.remap(col, { masks, display: disp });
    if (U?.tint) col = col.mul(U.tint);
    if (opts.display && U) {
        // (the card's own bind position for the clouds' arc: their fronts are ~20 cm, the coat a few cm)
        const pg = THREE.positionGeometry || THREE.positionLocal;
        if (opts.display.masks) col = opts.display.masks(col, U, disp);
        if (opts.display.clouds && U.clouds) col = opts.display.clouds(col, U, disp, masks, pg).col;
    }
    return col;
}

function tipColour(base, U, tipTex, rootUV, zoneLod, opts) {
    // (W3a) the tip pack at the root (the root colour's level): RGB the tip colour, stored sRGB (8 bits keep the black
    // tips' steps; decoded as gamma 2.2), through the same remap, tint and display as the root colour, so a recoloured
    // coat's tips follow it; A the share of the strands whose tip it is
    const { texture, vec3, vec4 } = THREE;
    tipTex.colorSpace = THREE.NoColorSpace;
    const tp = texture(tipTex, rootUV).level(zoneLod);
    let col = tp.rgb.max(0.0).pow(vec3(2.2));
    if (opts.remap || (opts.display && U)) {
        const masks = base.thicknessMap ? texture(base.thicknessMap, rootUV).level(zoneLod) : vec4(0.0, 0.0, 0.0, 0.5);
        const disp = base.emissiveMap ? texture(base.emissiveMap, rootUV).level(zoneLod) : vec4(0.0, 0.0, 0.0, 0.5);
        if (opts.remap) col = opts.remap(col, { masks, display: disp });
        if (U?.tint) col = col.mul(U.tint);
        if (opts.display && U) {
            const pg = THREE.positionGeometry || THREE.positionLocal;
            if (opts.display.masks) col = opts.display.masks(col, U, disp);
            if (opts.display.clouds && U.clouds) col = opts.display.clouds(col, U, disp, masks, pg).col;
        }
    } else if (U?.tint) col = col.mul(U.tint);
    return { col, share: tp.a };
}

// ============================================================================================ the card material
export function coatMaterial(base, coatSrc, geometry, U, CU, man = {}, opts = {}) {
    // base: the BASE skin material's glTF source (its map, thicknessMap = masks, emissiveMap = display); coatSrc: the
    // coat primitive's glTF material (map = the coverage page, emissiveMap = the attribute page); geometry: the coat
    // primitive's (attribute names); U: bestiary's uniforms (tint, display) or null; CU: coatUniforms(); man: the
    // manifest (bestiary.coat); opts: { remap(col, packs), display: { masks, clouds } }, and (g5) attributes (the attribute
    // page as stored, attachCoat's attributePage) and groundOcclusion(U, ventral) (the host's ground term: bestiary.js's)
    const { attribute, texture, uniformArray, float, int, vec2, vec3, vec4, mix, smoothstep, max, dFdx, dFdy } = THREE;
    const names = coatAttributeNames(geometry);
    const fd = attribute(names.furData, 'vec4');
    const rd = attribute(names.rootData, 'vec4');
    const rnd = fd.x.clamp(0, 1);
    const h = fd.y.clamp(0, 1);
    const signedSide = fd.z.clamp(-1, 1);
    const side = signedSide.abs();
    const flex = fd.w.clamp(0, 1);
    // (B6) _rootdata.w = rank * 32 + tile (< 256), + 512 on a card the forge flags matte (the brows, the lashes)
    const matteFlag = THREE.step(511.5, rd.w);
    const rdw = rd.w.sub(matteFlag.mul(512.0));
    const rank = rdw.div(32.0).floor();
    const tile = rdw.sub(rank.mul(32.0));
    const [r1, r2, r3] = hashes(rnd);
    const cut = CU.look.cut ?? 0.34;

    // ---- coverage: the atlas tile (u across, v root -> tip) or SPECIMEN's untextured taper. Two alphas from one fetch
    // (round 2): `alpha`, the CLIP fallback (the coverage rescaled by the forge's per-mip clip so the material's one cut
    // keeps mip 0's coverage), and `frac`, the coverage FRACTION (the filtered page as it is: box mips are the true
    // coverage at every level), which the DITHER compares with a per-pixel, per-frame threshold below; the fades
    // further down multiply both (in dither mode they become true fades that TAA resolves)
    const atlas = man.atlas && coatSrc?.map ? man.atlas : null;
    let alpha, frac, strandId = r2, depth = float(0.0), depthC = float(0.0), sideways = float(0.0), hStrand = null, lockDensity = null;
    // (g5) the attribute page AS STORED (attachCoat decodes it itself: the harness's glTF image path divided its colour
    // by its alpha), else the material's own
    const attrTex = opts.attributes || coatSrc?.emissiveMap || null;
    if (atlas) {
        for (const t of [coatSrc.map, attrTex]) if (t) t.colorSpace = THREE.NoColorSpace;
        // the coverage page as R8 (one per source page, shared by the primitives that sample it: coverageR8's cache; a
        // remix's rebuild reuses it; the RGBA original is then never drawn, so never uploaded)
        const covTex = coatSrc.userData.coatCoverageR8 || (coatSrc.userData.coatCoverageR8 = coverageR8(coatSrc.map));
        const tiles = atlas.tiles.map((r) => new THREE.Vector4(r[0], r[1], r[2], r[3]));
        while (tiles.length < 32) tiles.push(tiles[tiles.length - 1] || new THREE.Vector4(0, 0, 1, 1));
        const rect = uniformArray(tiles, 'vec4').element(int(tile.clamp(0, 31)));
        const auv = rect.xy.add(vec2(signedSide.mul(0.5).add(0.5), h).mul(rect.zw));
        // a negative mip bias keeps thin strands above the cut further out (the study-T mip bias -1), at the price of
        // more aliasing; the clip below is read at the biased level. The clip fallback also reads clipBias levels
        // coarser (round 2: fine strands merge into stable locks before its threshold); the dither reads mipBias alone
        // (g5) and taaBias sharper: TAA averages each frame's strands as an SSAA would, where the mip's box (twice the
        // pixel's footprint, aligned to the texel grid) blurred them into locks before any shading saw them
        const dz = CU.dither.clamp(0, 1);
        const bias = CU.mipBias.add(CU.clipBias.mul(float(1).sub(dz))).add(CU.taaBias.mul(dz));
        const cov = texture(covTex, auv).bias(bias).r;
        frac = cov;
        // (g5) the sub-lock's density against the tile's own (look.lockShade): the same page lockLevels coarser, less
        // the page three levels coarser still, so the term is a modulation about 0 that the mips take to 0 with
        // distance (a lock's core lighter, its thin edges darker, the card's mean kept)
        if (CU.look.lockShade > 0) {
            lockDensity = texture(covTex, auv).bias(bias.add(CU.lockLevels)).r
                .sub(texture(covTex, auv).bias(bias.add(CU.lockLevels).add(3.0)).r);
        }
        // the per-mip clip: the threshold the forge found for the level the sampler reads (isotropic trilinear: the
        // longer of the two screen-space footprints), the coverage rescaled so the material's one cut applies. Per
        // density row when the forge gives one (clip_by_row[mip][row]: a dense row's threshold rises at mip 1 while a
        // wisp row's falls toward 0.05; the global table is their mixture), the tile's row from row_of_tile
        // (floor(tile / (2 x width classes))), else the global table
        // and per BAND along the strand when given (clip_by_band[mip][row][band], band = min(floor(rootToTip x 4), 3)):
        // a sparse tip need not take its dense root's threshold
        const byRow = Array.isArray(atlas.clip_by_row) && atlas.clip_by_row.length && Array.isArray(atlas.rows);
        const byBand = byRow && Array.isArray(atlas.clip_by_band) && atlas.clip_by_band.length
            && Array.isArray(atlas.clip_by_band[0]?.[0]);
        const nRows = byRow ? atlas.rows.length : 1;
        const nBands = byBand ? atlas.clip_by_band[0][0].length : 1;
        const table = byBand ? atlas.clip_by_band.map((m) => m.flat())
            : byRow ? atlas.clip_by_row : ((atlas.clip && atlas.clip.length) ? atlas.clip.map((c) => [c]) : [[cut]]);
        const nMips = table.length;
        const perRow = byRow ? Math.max(1, Math.round(atlas.tiles.length / nRows)) : 1;
        const row = byRow ? tile.div(perRow).floor().clamp(0, nRows - 1) : float(0);
        const band = byBand ? h.mul(nBands).floor().min(nBands - 1) : float(0);
        const cell = row.mul(nBands).add(band);              // the (row, band) slot inside one mip's entry
        const sz = atlas.size || [1024, 1024];
        const px = auv.mul(vec2(sz[0], sz[1]));
        // the level the sampler reads: anisotropic filtering (the engine's GLB pages carry anisotropy 8) picks it from
        // the major footprint over min(major / minor, N) (the anisotropic-filtering reference), isotropic is the major
        const rx = vec2(dFdx(px.x), dFdx(px.y)).length(), ry = vec2(dFdy(px.x), dFdy(px.y)).length();
        const rMax = max(rx, ry).max(1e-6), rMin = THREE.min(rx, ry).max(1e-6);
        const aniso = Math.max(1, covTex.anisotropy || 1);
        const lod = rMax.div(rMax.div(rMin).clamp(1.0, aniso)).log2().add(bias).clamp(0, nMips - 1);
        const clipArr = uniformArray(table.flat().map(Number), 'float');
        const per = nRows * nBands;
        const l0 = lod.floor();
        const l1 = l0.add(1).min(nMips - 1);
        const c0 = clipArr.element(int(l0.mul(per).add(cell)));
        const c1 = clipArr.element(int(l1.mul(per).add(cell)));
        const thr = mix(c0, c1, lod.sub(l0)).max(0.02);
        alpha = cov.mul(float(cut).div(thr));
        if (atlas.attributes && attrTex) {
            // (g5) at the coverage's level, so a strand's id, depth and slope stay its own as far as its coverage does
            const at = texture(attrTex, auv).bias(bias);
            // depth behind the card plane: 0.5 on the plane, smaller toward the skin (forge/groom tiles.py), full scale
            // atlas.depth_mm; (g5) counted against look.depthRef mm when set
            const dmm = Number(atlas.depth_mm) || 0;
            const dGain = dmm > 0 ? THREE.select(CU.depthRef.greaterThan(0.0), float(dmm).div(CU.depthRef.max(1e-3)), float(1.0))
                : float(1.0);
            depth = float(0.5).sub(at.r).mul(2.0).mul(dGain).clamp(0, 1);
            // (g5) the clump's shade centres on the page's mean depth (look.depthMean), in the same units
            depthC = (CU.look.depthMean >= 0 ? CU.depthMean : float(Number(atlas.depth_mean) || 0.0)).mul(dGain).clamp(0, 1);
            strandId = at.g;
            if ((Number(atlas.version) || 0) >= 3) {
                // (g5) atlas v3: an RGB page with no alpha at all (no decoder can divide it): B the sideways slope, the
                // strand's own root-to-tip gone (look.strandRamp then uses the card's), G a per-lock random with a
                // small per-strand offset (the groom builder's v3, g5_groom/NOTES.md)
                sideways = at.b.sub(0.5).mul(2.0);
            } else {
                sideways = at.a.sub(0.5).mul(2.0);
                hStrand = at.b;                   // (round 2) the strand's own root-to-tip (look.strandRamp)
            }
        }
    } else {
        const rootAlpha = smoothstep(0.04, 0.14, h);
        const widthAlpha = float(1).sub(smoothstep(0.68, 0.98, side));
        const tipAlpha = float(1).sub(smoothstep(0.90, 1.00, h));
        alpha = rootAlpha.mul(widthAlpha).mul(tipAlpha);
        frac = alpha;
    }
    const fade = (f) => { alpha = alpha.mul(f); frac = frac.mul(f); };

    // ---- edge-on cards fade (the card's true plane, normalFlat, only for this; lighting keeps the base normal)
    // (g5, the groom builder's find, three r184 Position.js) A MATERIAL WITH A vertexNode, as a fin's is (finPush), READS A
    // positionView RECONSTRUCTED FROM THE CLIP POSITION in its fragment stage, so normalFlat, its derivatives, goes wrong there: the
    // facing fell to ~0 and every fin faded to 0.4 of its coverage (a translucent band under TAA, no fringe at all from the clip).
    // A varying keeps the vertex stage's real positionView; one vec3 more, so only where the trap is
    const pvFin = CU.look.finOnly > 0 ? THREE.positionView.toVarying('v_coatPv') : null;
    const cardFacing = (pvFin ? pvFin.dFdx().cross(pvFin.dFdy()).normalize() : THREE.normalFlat)
        .dot(THREE.positionViewDirection).abs().clamp(0, 1);
    fade(mix(float(1), smoothstep(CU.edgeLo, CU.edgeHi, cardFacing), CU.edgeFade));
    // ---- the coat's own density at the root (the integration, 10-29): the coat pack's R at the root uv over the card's
    // footprint (its explicit level, less the pack's size step below the base map). Cards rooted where the pack thins
    // toward a bare zone fade with it, so the coat thins out at the oral web's margin, the eye rings and the siphon as
    // a hairline does, instead of standing there as pale cards (their roots take the bare skin's pale albedo: the
    // 'paper edge' the low views showed). One fetch per fragment, constant over a card (no crawl)
    if (opts.pack) {
        // (two levels finer than the card's footprint: the octopus's arm islands are narrow, and a full footprint read
        // near their edges averages the empty margin in and thinned flank cards that are not at a bare boundary)
        const pw = opts.pack.image?.width || 0, bw = base.map?.image?.width || 0;
        const step = (pw > 0 && bw > 0 ? Math.max(0, Math.log2(bw / pw)) : 0) + 2;
        const pr = texture(opts.pack, rd.xy.clamp(0, 1)).level(rd.z.sub(step).clamp(0, 12)).r;
        const keep = smoothstep(CU.rootFadeLo, CU.rootFadeHi.max(CU.rootFadeLo.add(1e-3)), pr);
        fade(mix(float(1), keep, CU.rootFade));
    }
    // ---- FINS (look.finOnly, the integration 10-29: velvet's close-up silhouette): a short coat whose face-on read is
    // the coat maps alone draws its cards only where the body turns edge-on to the view (the root normal's |N.V|), so
    // the silhouette gets its pile while the face-on cards, which read as scales, never show: Lengyel's fins, from the
    // groom's own card set
    // (the integration's second pass, 10-29 night: a fin is the skin layer's pile seen side-on, so it takes the layer's
    // grazing brightening, (1 - N.V)^2.5 x layerSheen about the same root normal; without it the fins stood as a dark
    // fringe on the layer's bright rim, the velvet's close silhouettes reading burnt)
    let finRim = null;
    if (CU.look.finOnly > 0) {
        const ndvR = THREE.normalViewGeometry.normalize().dot(THREE.positionViewDirection).abs();
        const fin = float(1).sub(smoothstep(CU.finLo, CU.finHi.max(CU.finLo.add(1e-3)), ndvR));
        fade(mix(float(1), fin, CU.finOnly));
        finRim = float(1).sub(ndvR.clamp(0, 1)).pow(2.5).mul(CU.layerSheen).mul(CU.finOnly).mul(CU.finRim);
    }
    // ---- the LOD dissolve: a card's key rank + strandRandom against the cut (coatLOD stretches it so the top LOD
    // draws every card whole), faded over rankFade ranks
    fade(CU.rankCut.sub(rank.add(rnd)).div(CU.rankFade.max(1e-3)).clamp(0, 1));
    // ---- SPECIMEN's resolvability retirement: cards under ~1 delivered pixel erode instead of popping (the clip
    // alpha erodes; the fraction fades)
    const ssaa = CU.ssaa || (CU.ssaa = THREE.uniform(globalThis.SSAA_FACTOR ?? 1.0));
    const sideGrad = vec2(dFdx(signedSide), dFdy(signedSide)).length().max(1e-4);
    const cardPx = float(2.0).div(sideGrad).div(ssaa);
    const resolved = smoothstep(0.55, 1.10, cardPx);
    alpha = alpha.sub(float(1).sub(resolved).mul(1.0 - cut)).clamp(0, 1);
    frac = frac.mul(resolved).clamp(0, 1);
    // ---- THE DITHER (round 2): with TAA the coverage fraction itself is the alpha, one bit per pixel per frame: the
    // fraction against interleaved gradient noise (Jimenez 2014: every 3x3 block holds an even spread of thresholds, so
    // the neighbourhood TAA clips against carries the true mean and its history is kept) shifted each frame by the
    // golden ratio (each pixel walks a low-discrepancy sequence, so the history converges in a few frames, not as noise
    // does). Each frame stays an exact alpha test (depth, shadows); TAA averages it into partial coverage. (g5) Without TAA
    // the walk stops (look.ditherWalk 0, attachCoat's): a still stipple over the true fraction; look.dither 0, the clip
    // alpha above, stays as an option
    // (g5) PLUS THE CARD'S OWN OFFSET (its strandRandom). The threshold was the pixel's and the frame's alone, so every
    // card layer over a pixel tested its coverage against the SAME number: two layers of coverage 0.5 drew together or
    // not at all, and the pixel resolved to max(c1, c2) where the layers' real union is 1 - (1 - c1)(1 - c2). Measured
    // (batch 2, cov_measure.py: the cards white on a black body, TAA's resolve against a 16-sample box-filtered
    // reference): the shaggy coat resolved to 0.62 / 0.61 / 0.54 coverage at the mantle close / eye ring / arm close
    // where the reference has 0.80 / 0.78 / 0.70 and the no-TAA clip 0.78 / 0.73 / 0.67 (overdrawz: 1.0-1.3 card layers
    // per pixel, 36 % of the pixels with two or more), a ~60 % veil over the body everywhere: round 2's brushed felt.
    // A uniform random offset per card makes the layers' tests independent in expectation (hashed alpha keys its hash
    // to the surface for the same reason), each card's own pattern still IGN's even spread
    const pix = THREE.screenCoordinate.xy.floor();
    const ign = THREE.fract(float(52.9829189).mul(THREE.fract(pix.x.mul(0.06711056).add(pix.y.mul(0.00583715)))));
    const thrD = THREE.fract(ign.add(CU.frame.mul(0.6180339887).mul(CU.ditherWalk)).add(rnd.mul(CU.ditherDecor)));
    const alphaD = THREE.select(frac.greaterThan(thrD), float(1.0), float(0.0));
    // (the restart, 10-30 04:30) what the card claims in N8AO's transparency pass (the AO take, below): with the clip
    // coverage its own test, as judged (look/t5_take.png); with the DITHER its whole footprint (the coverage fraction
    // over 0.05), not this frame's bits: each dithered hole shows the body behind as a one-pixel pit in the depth
    // buffer, which the 0.3 m AO darkens hard, and a hole the card did not claim kept that whole darkening (measured:
    // under TAA the coat read 2.8 levels darker than with the clip at 1.75 m, the maps and the bare creature within 1)
    const alphaAO = mix(alpha, THREE.select(frac.greaterThan(0.05), float(1.0), float(0.0)), CU.dither.clamp(0, 1));
    alpha = mix(alpha, alphaD, CU.dither.clamp(0, 1));

    // ---- colour
    // (coat G6) A FIN'S ZONES SMOOTHED (look.finZoneBlur levels coarser than its root's footprint, fin coats only): a fin
    // stands at the outline, so the zone its root sits in becomes the outline's colour, and a recoloured thin zone (an eye
    // ring, a margin) would draw a line along every outline that crosses it; read coarser, a fin takes its
    // neighbourhood's zone mix, as the layer behind it shows it from a step back. (Ringed's salmon lines round the eye,
    // g5_integrate/look/c_remix_velvet_x4.png, were read as this; they were rim_pulse's glow: look.finAffixFade, rebuild)
    const zoneLod = CU.look.finOnly > 0 && CU.look.finZoneBlur > 0 ? rd.z.add(CU.finZoneBlur).clamp(0, 12) : rd.z.clamp(0, 12);
    // (B3) a base without an albedo map (the human: its skin's colour is a pigment pack) has no root colour to read: the
    // style's colour (or the pigment model below) is the coat's
    let col = base.map ? rootColour(base, U, rd.xy.clamp(0, 1), rd.z.clamp(0, 12), opts, zoneLod) : vec3(CU.color);
    col = mix(col, CU.color, CU.colorMix);
    // (B3, HAIR_FUR H8) THE PIGMENT MODEL (look.pigment > 0 at attach): the hair's colour from its melanins, not the base's
    // albedo: the absorption of eumelanin and pheomelanin (d'Eon et al. 2011's fit, per unit concentration: eu
    // [0.419, 0.697, 1.37], pheo [0.187, 0.4, 1.05]) through look.pigmentPath (a card is a bundle of fibres: 4 fibre
    // diameters of path puts eumelanin 0.3 / pheo 0.12 at study T's golden blonde root 0.565 in R and 3.0 / 0.15 at its black
    // 0.0052, HS §3.6), a dye tinting it (look.dye, dyeAmount), and grey hairs per strand (look.grey: the share of the
    // attribute page's strand ids that lose their pigment: salt and pepper). The TT and TRT lobes and the scatter read this
    // colour, so blonde glows and black does not, as before
    if (CU.look.pigment > 0) {
        const sigma = vec3(0.419, 0.697, 1.37).mul(CU.eumelanin).add(vec3(0.187, 0.4, 1.05).mul(CU.pheomelanin));
        let pig = THREE.exp(sigma.mul(CU.pigmentPath).negate());
        pig = mix(pig, pig.mul(CU.dye).mul(2.0).clamp(0, 1), CU.dyeAmount);
        const greyHair = THREE.step(THREE.fract(strandId.mul(7.31).add(r1.mul(3.17))), CU.grey);
        pig = mix(pig, vec3(0.62, 0.60, 0.57), greyHair);
        col = mix(col, pig, CU.pigment);
    }
    col = col.mul(CU.tint);
    // (round 2) the ramps along the strand: the card's rootToTip, or each strand's own from the attribute page's B
    // (look.strandRamp: every fine strand gets its own light tip instead of the card's band)
    const hc = hStrand ? mix(h, hStrand, CU.strandRamp.clamp(0, 1)) : h;
    const rootDark = mix(CU.rootDark, float(1), smoothstep(0.0, CU.rootDarkEnd.max(1e-3), hc));
    const tipLift = float(1).add(CU.tipLift.mul(smoothstep(0.35, 1.0, hc)));
    const vj = float(1).add(r3.sub(0.5).mul(2.0).mul(CU.valueJitter))
        .mul(float(1).add(strandId.sub(0.5).mul(2.0).mul(CU.strandJitter)));
    // (g5) per strand the hue too (look.strandHue), linear in the id as the value is (a lighter strand warmer), so the
    // mips' average of a page of strands is the card's own colour at every distance (a hash of a filtered id is not)
    const hj = r2.sub(0.5).mul(2.0).mul(CU.hueJitter).add(strandId.sub(0.5).mul(2.0).mul(CU.strandHue));
    const temp = vec3(float(1).add(hj), float(1), float(1).sub(hj));
    // (W3a) THE TIP COLOUR (look.tipMix > 0 at attach and a tip pack for this base material: opts.tip): which strands
    // carry it, the id (a lock's id + its small per-strand offset, so whole locks mostly) shifted by the card's random,
    // under the pack's share x look.tipShare (a 0.04 soft edge: no hard line where a mip blends ids); where along the
    // strand, tipStart .. tipEnd with each strand's start jittered by +- tipJitter (no row of dashes at one height)
    let tipW = null, tipCol = null;
    if (opts.tip && CU.look.tipMix > 0) {
        // (the pack is coarser than the albedo by log2 of their sizes: read it that many levels finer, the same footprint)
        const bw = base.map?.image?.width || 0, tw = opts.tip.image?.width || 0;
        const tipStep = bw > 0 && tw > 0 ? Math.max(0, Math.log2(bw / tw)) : 0;
        const tc = tipColour(base, U, opts.tip, rd.xy.clamp(0, 1), zoneLod.sub(tipStep).max(0.0), opts);
        tipCol = mix(tc.col, CU.color, CU.colorMix).mul(CU.tint);
        // the share by the card's layer (look.tipInner): its atlas row, 0 the inner dense cards .. the last the outer ones
        const nRowsT = atlas && Array.isArray(atlas.rows) ? atlas.rows.length : 4;
        const perRowT = atlas ? Math.max(1, Math.round(atlas.tiles.length / nRowsT)) : 8;
        const rowT = tile.div(perRowT).floor().clamp(0, nRowsT - 1);
        const layerW = mix(CU.tipInner, float(1), rowT.div(Math.max(1, nRowsT - 1)));
        const share = tc.share.mul(CU.tipShare).mul(layerW).clamp(0, 1);
        const pick = THREE.fract(strandId.add(r1));
        const sel = float(1).sub(smoothstep(share.sub(0.02), share.add(0.02), pick)).mul(smoothstep(0.0, 0.04, share));
        const jit = THREE.fract(strandId.mul(7.31).add(r3.mul(3.17))).sub(0.5).mul(2.0).mul(CU.tipJitter);
        const t0 = CU.tipStart.add(jit);
        const w = smoothstep(t0, t0.add(CU.tipEnd.sub(CU.tipStart).max(0.02)), hc).mul(sel).mul(CU.tipMix.clamp(0, 1));
        tipW = { w, sel };
    }
    // one agouti band per strand (the wolf's; band 0 = off), SPECIMEN's broad resolvable band
    const bandC = CU.bandCenter.add(r1.sub(0.5).mul(0.16));
    let band = float(1).sub(smoothstep(CU.bandWidth, CU.bandWidth.add(0.03), hc.sub(bandC).abs())).mul(CU.band);
    if (tipW && CU.look.bandSel > 0) band = band.mul(mix(float(1), tipW.sel, CU.bandSel.clamp(0, 1)));
    const bandTint = mix(float(1), CU.bandDark, band);
    // the strand's colour along its length: the root colour, lifted toward a light tip (tipLift), or (W3a) taken over by
    // the tip colour on the strands that carry it (without a tip pack the expression is the one before, term for term)
    const colRamp = tipW ? mix(col.mul(tipLift), tipCol, tipW.w).mul(rootDark) : col.mul(rootDark).mul(tipLift);
    let rgb = colRamp.mul(vj).mul(temp).mul(bandTint).mul(CU.cardTone)
        .mul(float(1).add(CU.cardLift.mul(CU.closeW)));
    if (finRim) rgb = rgb.mul(float(1).add(finRim));
    if (lockDensity) rgb = rgb.mul(float(1).add(lockDensity.mul(CU.lockShade).mul(2.0)).clamp(0.5, 1.5));
    rgb = rgb.clamp(0, 0.98);

    // (B3b) the volume's depth by the card's atlas row (look.layerOcc; the rows are 8 tiles each: 4 width classes x 2)
    const nRowsA = atlas && Array.isArray(atlas.rows) ? atlas.rows.length : 4;
    const perRowA = atlas ? Math.max(1, Math.round(atlas.tiles.length / nRowsA)) : 8;
    const rowA = tile.div(perRowA).floor().clamp(0, nRowsA - 1);
    const layerOcc = float(1).sub(CU.layerOcc.mul(float(1).sub(rowA.div(nRowsA - 1))));
    // ---- the strand tangent (view space): TANGENT bent by the page's sideways component, tilted per strand
    const N = THREE.normalViewGeometry.normalize();
    let T = THREE.tangentView.normalize();
    const S = N.cross(T).normalize();
    T = T.add(S.mul(sideways.mul(CU.curl))).add(N.mul(strandId.sub(0.5).mul(2.0).mul(CU.scraggle))).normalize();
    // (g5) THE ROUND LOCK (look.lockBend): the card's diffuse normal tilted across its width, so a card reads as a lock
    // with a lit middle and edges turning from the light (the cards had shaded as one flat plane about their root's
    // normal, every card at a point alike: half of round 2's felt). Built only when asked for at attach
    // (not on fins: a fin is the pile seen side-on, no lock to round). The tilt costs a light along N the mean of
    // cos(atan(k side)) over the width, asinh(k) / k; the diffuse takes k / asinh(k) back (ndComp), so the card's mean holds
    const lockOn = CU.look.lockBend > 0 && !(CU.look.finOnly > 0);
    const Nd = lockOn ? N.add(S.mul(signedSide.mul(CU.lockBend))).normalize() : null;
    const kB = CU.lockBend.max(1e-3);
    const ndComp = lockOn ? kB.div(kB.add(kB.mul(kB).add(1.0).sqrt()).log()) : null;

    // (round 2) the coverage test is the material's own discard (below) and the built-in alpha test only a token 0.001
    // (above the harness's 0.0001, so it never treats the coat as an untested transparent), because the fragment's
    // ALPHA OUTPUT now carries something else: what the card takes from the host's screen-space AO. Blending is a plain
    // overwrite (One / Zero) declared as custom, so three does not force an opaque material's alpha to 1 and the coat
    // stays in the opaque list (N8AO counts only transparent: true as transparent)
    const { CoatNodeMaterial } = coatClasses();
    const m = new CoatNodeMaterial({
        metalness: 0, roughness: CU.look.envRoughness, side: THREE.DoubleSide, shadowSide: THREE.DoubleSide,
        transparent: false, depthWrite: true, alphaTest: 0.001, alphaToCoverage: false,
        blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor,
        blendDst: THREE.ZeroFactor, blendEquationAlpha: THREE.AddEquation, blendSrcAlpha: THREE.OneFactor,
        blendDstAlpha: THREE.ZeroFactor,
    });
    m.coatNodes = {
        // (g5) the lobes' width per strand (look.roughJitter, linear in the id: the mips' mean is the look's roughness)
        T, h, rough: CU.roughness.mul(float(1).add(strandId.sub(0.5).mul(2.0).mul(CU.roughJitter))).max(0.05),
        specular: CU.specular, shift: CU.shift, backlit: CU.backlit, envSpec: CU.envSpec, trt: CU.trt, ttBundle: CU.ttBundle, Nd, ndComp,
        // (B5; gated at landing L3) built only when a look asks: CU.rTint is a uniform node (always truthy), so the
        // ungated key ran the TRT weight on every coat, and a fur look with trt != 1 lost its TRT gain on dark fur
        rTint: CU.look.rTint ? CU.rTint : null,
        // (B6) dark hair's R and the brows' / lashes' matte flag (built only when a look asks: no change otherwise)
        dark: (CU.look.darkR !== 1 || CU.look.darkRWidth !== 1 || CU.look.darkRCool !== 0 || CU.look.darkEnv !== 1)
            ? { gain: CU.darkR, width: CU.darkRWidth, cool: CU.darkRCool, env: CU.darkEnv } : null,
        matte: CU.look.matteFace > 0 ? matteFlag : null, matteFace: CU.matteFace,
        scatterW: CU.scatter.mul(smoothstep(0.02, 0.35, THREE.dot(rgb, vec3(0.2126, 0.7152, 0.0722))).mul(0.7).add(0.3)),
        wrap: CU.wrap, wrapMix: CU.wrapMix,
        // the self-shadow toward the root, and (round 2) through the clump: the attribute page's depth (strands nearer
        // the skin lie under the clump's others), the deep-opacity a strand renderer would have, from the atlas
        // ((g5) about the page's mean depth, so the mips take the term to no change with distance)
        shadowH: mix(CU.selfShadow, float(1), smoothstep(0.0, 0.9, h))
            .mul(float(1).sub(depth.sub(depthC).mul(CU.depthShadow)).clamp(0.2, 1.3)).mul(layerOcc),
        ttMask: smoothstep(0.15, 0.90, h),
        // the free tips (CoatLightingModel.direct): from a third of the way up to the tip
        free: CU.tipFree.mul(smoothstep(0.30, 0.95, h)), kkGain: CU.kkGain,
        // (round 2) a FIN is the skin layer's pile seen side-on: it takes the layer's velvet lobe about the same root
        // normal (CoatLightingModel), so the outline brightens with the layer instead of standing dark on it
        // (the Ashikhmin comparison branch is built only when a look asks for it at attach: sheenModel > 0)
        velvet: CU.look.finOnly > 0 ? { gain: CU.sheen.mul(CU.finOnly).mul(CU.finSheen), rough: CU.sheenRough, tint: CU.sheenTint,
            model: CU.look.sheenModel > 0 ? CU.sheenModel : null } : null,
    };
    // THE COVERAGE TEST and THE AO TAKE (round 2). The card discards where its alpha (the clip or the dither above) is
    // at the cut; its alpha OUTPUT is 1 everywhere except in N8AO's transparency pass (coatLOD flags that draw: CU.aoPass),
    // where the vendored N8AO lifts its AO by the alpha it finds (mix(ao, 1, alpha)): there the card writes
    // 1 - mix(aoTake, aoTakeTip, smoothstep(0, 0.75, rootToTip)), so a card takes look.aoTake of the screen-space AO at
    // its root (where it sits against the body) and look.aoTakeTip toward its tip, the coat's own occlusion carrying the
    // rest. (Round 2 first took none toward the tip, against the crest the 0.3 m AO turned black when the cards took it
    // whole; with a ground in the frame that left the coat far lighter than its own maps: the integration's tip take.)
    // (The shadow pass, when cards cast, masks by maskShadowNode below)
    CU.aoPass ??= THREE.uniform(0.0);
    // (round 2's integration) from aoTake at the root to aoTakeTip by rootToTip 0.75 (aoTakeTip 0: as before); a fin
    // coat's cards keep the tip at 0 (they are the silhouette's bright rim, velvet's cue, not a coat over the skin)
    const tipTake = CU.aoTakeTip.mul(float(1).sub(CU.finOnly.clamp(0, 1)));
    // (g5) past the close-up the take goes to look.aoTakeFar, root and tip alike (CU.farW, 0 for a fin coat)
    let take = mix(mix(CU.aoTake, tipTake, smoothstep(0.0, 0.75, h)), CU.aoTakeFar, CU.farW).clamp(0, 1)
        .mul(CU.hostTake);                                         // (g5, 10-31) the host AO's scale (look.aoHostLo / aoHostHi)
    // (g5, 10-31) look.finTake (>= 0, built at attach; 0.6 by default): a fin coat's own take, root and tip alike, in place of
    // the line above's none at the tip: the bright rim belongs to an OPEN outline, where N8AO's ao is mild and the take
    // moves little, while in a crevice (an arm across the head) the fins must darken with the skin around them
    if (CU.look.finOnly > 0 && CU.look.finTake >= 0) take = mix(take, CU.finTake.clamp(0, 1), CU.finOnly.clamp(0, 1));
    // (g5) THE CARD'S VISIBLE FACE, the world y of the card plane's normal turned to the camera (from the position's own
    // derivatives, never normalised through zero: a degenerate or edge-on fragment gives 0, not NaN): what the ground terms
    // below read, since the root normal says nothing of the side of a card the eye sees
    let faceY = null, nearSand = null;
    if (typeof opts.groundOcclusion === 'function' && U?.groundAO && U?.groundY) {
        const nwr = THREE.positionWorld.dFdx().cross(THREE.positionWorld.dFdy());
        const toCam = THREE.cameraPosition.sub(THREE.positionWorld);
        const fs = THREE.select(nwr.dot(toCam).greaterThanEqual(0.0), float(1.0), float(-1.0));
        faceY = nwr.y.mul(fs).div(nwr.length().max(1e-20));
        const hg = THREE.positionWorld.y.sub(U.groundY);
        nearSand = float(0.01).div(hg.mul(hg).add(0.01));   // stage 2b's R^2 / (R^2 + h^2), R 0.10 m (see below)
    }
    // (g5) A FACE NOT LOOKING AT THE SKY, NEAR THE SAND, TAKES THE HOST'S SCREEN-SPACE AO WHOLE. The partial take exists for
    // the crest, where the 0.3 m AO counted card layers as solid; down at the sand, on a face that sees no sky, the AO is
    // the crevice's own darkness (the arches, the V where the arms meet the sand), which the skin there takes whole. So
    // there the take rises to the host's ground weight, groundAO x R^2 / (R^2 + h^2), wherever that is the larger, for
    // faces turned from the sky (y 0.35 and up keep the plain take). The facing is what keeps it there: with height alone
    // (b7) every arm top lies within ~5 cm of the sand, so the whole coat took the AO whole: 6.6 levels darker at Skye's
    // frame, the hand-over at 1.75 m -4.6 -> -9.2. A host without a ground term (no opts.groundOcclusion, or groundAO 0)
    // and every fin coat keep round 2's take
    if (faceY) {
        const nearG = nearSand.mul(U.groundAO).mul(float(1).sub(smoothstep(0.0, 0.35, faceY)))
            .mul(float(1).sub(CU.finOnly.clamp(0, 1)));
        take = THREE.max(take, nearG.clamp(0, 1));
    }
    // (B3c) look.aoTipGap (built when > 0): in the AO pass a GAP of the tip half (alphaAO at the cut) no longer discards
    // but writes gapW as its claim, so the skin seen through a sparse tip is lifted out of the AO the tip causes
    // (gap3: easing the lift out over the card's last 15 % brought the specks back there, the gaps taking the AO again
    // beside the lifted strands; the lift runs to the card's end, whose faint edge on the nape is the lesser read)
    const gapW = CU.look.aoTipGap > 0 ? smoothstep(0.5, 0.75, h).mul(CU.aoTipGap.clamp(0, 1)) : null;
    const inGapAO = alphaAO.lessThanEqual(float(cut));
    const claimAO = gapW ? THREE.select(inGapAO, gapW, float(1).sub(take)) : float(1).sub(take);
    const outA = mix(float(1), claimAO, CU.aoPass);
    const colourOut = vec4(rgb, outA);
    m.colorNode = THREE.Fn(() => {
        const c = colourOut.toVar();
        if (gapW) {
            THREE.select(CU.aoPass.greaterThan(0.5), inGapAO.and(gapW.lessThanEqual(0.001)), alpha.lessThanEqual(float(cut)))
                .discard();
        } else {
            THREE.select(CU.aoPass.greaterThan(0.5), alphaAO, alpha).lessThanEqual(float(cut)).discard();
        }
        return c;
    })();
    m.normalNode = Nd || THREE.normalViewGeometry;                 // no DoubleSide flip: the root's base normal
                                                                   // ((g5) or its round-lock tilt: the sky's light follows)
    // (g5) THE SKY ON THE SIDE OF THE FIBRE THE EYE SEES (look.envFibre). m.normalNode is what three's environment reads, and a card
    // keeps its root's normal, so a coat seen from beside took the sky its roots face, where a fibre seen side-on shows its
    // flank. So the normal turns toward the strand's view-facing normal, V less its share along T (as the scatter's Nf; the
    // small N keeps it off zero where V runs along T). No change face-on (V ~ N); no fetch
    if (CU.look.envFibre > 0 && !(CU.look.finOnly > 0)) {
        const Vf = THREE.positionViewDirection.normalize();
        const Nf = Vf.sub(T.mul(T.dot(Vf))).add(N.mul(1e-3)).normalize();
        m.normalNode = mix(m.normalNode, Nf, CU.envFibre).normalize();
    }
    m.roughnessNode = CU.envRoughness;
    m.metalnessNode = float(0.0);
    const rootMask = float(1).sub(smoothstep(0.08, 0.42, h));
    m.aoNode = float(1).sub(rootMask.mul(CU.aoRoot).mul(flex.mul(0.4).add(0.6)))
        .mul(float(1).sub(depth.sub(depthC).mul(CU.aoDepth))).clamp(0.45, 1.15).mul(layerOcc);
    // (g5) THE GROUND OCCLUSION on top of the coat's own: the host's term for a surface near its sand (stage 2b's
    // groundOcclusion(U, ventral), exported by bestiary.js and passed in as opts.groundOcclusion, since coat.js imports
    // nothing from its host), with the root's ventral weight (the masks pack's G at the root uv, read as the colour is)
    // and the card's own world height; its facing is the root's skin normal (a card's NORMAL), so the cards at the
    // body's contact with the sand darken with the skin under them (Skye's sand-level frame: they stood pale across the
    // dark band). On the indirect light only, as the skin's
    if (typeof opts.groundOcclusion === 'function' && U) {
        const ventral = base?.thicknessMap ? texture(base.thicknessMap, rd.xy.clamp(0, 1)).level(rd.z.clamp(0, 12)).g : float(0.0);
        let go = opts.groundOcclusion(U, ventral);
        // AND THE CARD'S VISIBLE FACE. The host's term faces the root's skin normal, and the coat lies on the creature's
        // upper side, so it barely reached the cards (Skye's sand-level frame: 48 of 2 M pixels moved, b4): what shows
        // at the V is the cards' UNDERSIDE (an arm's lower flank, the cards lying out over the oral web, seen from near
        // the sand), which faces the creature's shadowed sand, not the sky its root normal faces. So the same term is
        // also read with the card plane's own normal turned to the camera (the face the eye sees), and the card takes
        // the darker of the two. That needs the term's own shape: it mirrors landing2b_bestiary.md's GO_R 0.10 m,
        // GO_UP 0.35 and GO_SIDE 0.5 on the host's U.groundAO / U.groundY (work/bestiary/coat/patches/
        // coat_ground_occlusion_hook.md proposes a normal argument for the host's builder, which would retire this copy)
        if (faceY) {
            const down = smoothstep(-0.35, 1.0, faceY.negate());
            go = THREE.min(go, float(1.0).sub(down.mul(nearSand).mul(mix(float(0.5), float(1.0), ventral)).mul(U.groundAO)));
        }
        m.aoNode = m.aoNode.mul(go);
    }
    m.maskShadowNode = alpha.greaterThan(float(cut));
    // (B3b) THE HAIR VOLUME'S OWN SHADOW (look.shadowLift / shadowSoft): the received lookup lifted out of the volume along
    // the shell normal (each card's NORMAL is its row's SDF gradient: outward from the head), then eased toward 1
    if (CU.look.shadowLift > 0) {
        m.receivedShadowPositionNode = THREE.positionWorld.add(THREE.normalWorldGeometry.mul(CU.shadowLift));
    }
    if (CU.look.shadowSoft > 0) m.receivedShadowNode = THREE.Fn(([s]) => mix(s, float(1.0), CU.shadowSoft.clamp(0, 1)));
    m.userData.noAutoAlphaToCoverage = true;      // the harness's auto-enhance must not turn A2C on (drops the draw)
    m.userData.coat = true;
    m.coatCut = cut;
    m.coatAlpha = alpha;
    m.name = `coat_${man.style || 'coat'}_${coatSrc?.userData?.base_material || base?.name || 'base'}`;
    // (the second restart, 10-30) THE AO PASS'S OWN MATERIAL. N8AO's transparency pass reads only the alpha a card
    // writes there (what it claims of the AO: 1 - take) and which pixels it covers (the discard on alphaAO); drawn with
    // the material above, it also ran the whole hair BSDF, the shadow lookups and the wrap for a colour nobody reads
    // (the engine bench: that pass cost as much as the coat's own scene pass, ~+0.15 ms at 1.5 m). coatLOD draws this
    // one there instead (scene.overrideMaterial for that one draw: r184's renderObject reads it after onBeforeRender;
    // put back in onAfterRender). The same vertex stage (coatPosition hands it the same positionNode; the skinning is
    // the mesh's), side, depth and blending; the material above keeps its own AO-pass branch (CU.aoPass) for a pass
    // where the swap cannot happen (another override already set)
    const aoM = new THREE.MeshBasicNodeMaterial({
        side: THREE.DoubleSide, transparent: false, depthWrite: true, alphaTest: 0.001, alphaToCoverage: false,
        blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor,
        blendDst: THREE.ZeroFactor, blendEquationAlpha: THREE.AddEquation, blendSrcAlpha: THREE.OneFactor,
        blendDstAlpha: THREE.ZeroFactor, forceSinglePass: true, fog: false, toneMapped: false,
    });
    if (gapW) {
        // (B3c) a gap's claim must never LOWER a claim already there: with the overwrite (One / Zero, depth written) a front
        // card's gap writing a small lift replaced the strand of a card behind it and that hair went dark (gap2). So with
        // aoTipGap the AO pass keeps the larger claim (alpha Max) and writes no depth; the target's depth is the scene's
        // copy, so fragments behind what the eye sees still fail the test
        aoM.depthWrite = false;
        aoM.blendEquationAlpha = THREE.MaxEquation;
    }
    aoM.colorNode = THREE.Fn(() => {
        if (gapW) inGapAO.and(gapW.lessThanEqual(0.001)).discard();   // (B3c) the tip's gaps claim gapW
        else alphaAO.lessThanEqual(float(cut)).discard();
        return vec4(0.0, 0.0, 0.0, claimAO);
    })();
    aoM.userData.noAutoAlphaToCoverage = true;
    aoM.userData.coat = true;
    aoM.name = `${m.name}_ao`;
    m.coatAOMaterial = aoM;
    m.addEventListener('dispose', () => aoM.dispose());
    return m;
}

// ============================================================================================ the card position
export function coatPosition(m, mesh, CU, opts = {}) {
    // after mesh.bind(): the sway and the wind, then the width floor and the LOD's width. SPECIMEN's addStableFurPosition,
    // with a world wind and the LOD term. (round 2) and the coat's own MOTION VECTORS (opts.motionVectors, on unless false)
    // (g5) THE ORDER THE SHADER REALLY RUNS IN. This node runs BEFORE skinning: the compiled WGSL (three r184; the groom
    // builder's dump, work/bestiary/coat/g5/g5_groom/scratch/shader/all_1.wgsl) reads positionLocal = the BIND attribute, then
    // this expression, then the bones' blend, though NodeMaterial.setupPosition's source lists skinning first and this
    // comment had said post-skin since SPECIMEN. So positionLocal, normalLocal and tangentLocal are the BIND pose here, what
    // this node RETURNS is what the bones then carry, and what it MEASURES on the screen must be read posed. Written the
    // old way (posed centre + (bind point - posed centre) x scale) it was right only at scale 1: the width floor and the
    // LOD's widening moved a card by (scale - 1) x (bind - pose) before skinning (round 2's specks off the curled tips, the
    // far ranks near them), the face-on test read a bind normal against a posed view, a fin's collapse landed on a point
    // skinned twice (long strips over the sand), and the floor measured a bind point against a posed one. Now every
    // offset is in the bind frame, so the bones carry it with the skin, and the screen's questions are put to skinning(mesh)
    const { attribute, float, vec4, sin, max } = THREE;
    const names = coatAttributeNames(mesh.geometry);
    const fd = attribute(names.furData, 'vec4');
    const h = fd.y.clamp(0, 1);
    const rnd = fd.x.clamp(0, 1);
    const flex = fd.w.clamp(0, 1);
    const N = THREE.normalLocal.normalize();                     // the strand's frame, BIND
    const T0 = THREE.tangentLocal;
    const T = T0.sub(N.mul(N.dot(T0))).normalize();
    const B = N.cross(T).normalize();
    const P0 = THREE.positionLocal;                              // BIND
    const centre = attribute(names.furCenter, 'vec3');           // BIND
    const sk = THREE.skinning(mesh);
    const C0 = sk.getSkinnedPosition(undefined, centre);         // POSED, for the screen and the wind's phase
    const Ps = sk.getSkinnedPosition(undefined, P0);             // POSED
    const skinNT = sk.getSkinnedNormalAndTangent();
    const Ns = skinNT.skinNormal.normalize();                    // the strand's frame, POSED
    const Ts = skinNT.skinTangent.sub(Ns.mul(Ns.dot(skinNT.skinTangent))).normalize();
    const Bs = Ns.cross(Ts).normalize();
    const t = THREE.time;
    // the offset at time tt for a card whose skinned centreline point is Cc, in the BIND frame
    const dispAt = (tt, Cc) => {
        // SPECIMEN's coherent sub-pixel sway: one spatial field, +-0.175 rad of per-card phase
        const phase = tt.mul(CU.windSpeed).add(rnd.sub(0.5).mul(0.35)).add(Cc.z.mul(1.70)).add(Cc.x.mul(0.43));
        const gust0 = sin(tt.mul(0.23).add(Cc.x.mul(1.13)).sub(Cc.z.mul(0.71)));
        const sway = T.mul(sin(phase).mul(0.35).add(gust0.mul(0.65))).add(B.mul(sin(phase.mul(1.37).add(2.10)).mul(0.18)))
            .mul(CU.sway);
        // the wind: gusts travelling along the wind's direction (in the creature's space, the posed one), pushing the
        // strand along the posed skin's tangent plane; then read in the posed strand's frame and written in the bind one,
        // so the bones turn it back onto the wind's own direction (the frame is a rotation of the bind frame, so its dot
        // products stand in for the skin matrix's inverse)
        const Wl = CU.windLocal;
        const Wt = Wl.sub(Ns.mul(Ns.dot(Wl)));
        const gust = sin(tt.mul(CU.windFreq).sub(Cc.dot(Wl).mul(CU.windK))).mul(0.5).add(0.5);
        const flutter = sin(tt.mul(CU.windFreq.mul(3.1)).add(rnd.mul(6.2832)).sub(Cc.dot(Wl).mul(CU.windK.mul(2.3))));
        const windS = Wt.mul(gust.mul(0.75).add(0.25)).add(Bs.mul(flutter.mul(0.12))).mul(CU.wind);
        const wind = T.mul(windS.dot(Ts)).add(B.mul(windS.dot(Bs)));
        return sway.add(wind).mul(h.mul(h)).mul(flex);
    };
    const disp = dispAt(t, C0);
    const P = P0.add(disp);
    // the width floor: the card's projected half-width in pixels (vertex to its centreline, both posed: the screen's
    // measure) brought up to minPx / 2 delivered pixels, capped at maxWidth; the LOD's coverage compensation when it asks
    // for more
    const ndc = (q) => {
        const clip = THREE.cameraProjectionMatrix.mul(THREE.modelViewMatrix.mul(vec4(q, 1.0)));
        return clip.xy.div(clip.w.abs().max(1e-5));
    };
    const ssaa = CU.ssaa || (CU.ssaa = THREE.uniform(globalThis.SSAA_FACTOR ?? 1.0));
    const halfPx = ndc(Ps).sub(ndc(C0)).mul(THREE.screenSize.mul(0.5)).length().max(0.05);
    const floorScale = CU.minPx.mul(ssaa).mul(0.5).div(halfPx).clamp(1.0, CU.maxWidth);
    let scale = max(floorScale, CU.widthScale);
    if (CU.look.finOnly > 0) {
        // FINS (finOnly >= 0.5; the second pass, 10-29 night): a card whose root normal faces the view past finHi + 0.12
        // collapses onto its centreline here, so the face-on cards that the fragment's fin test discards (alpha 0 from
        // finHi up) are never rasterised. Measured before this, velvet's fins cost nearly the whole card set's fill:
        // +0.11 ms at 0.6 m against +0.14 for every card drawn whole (1080p)
        // ((g5) both posed, the facing the fragment's own window reads)
        const nV = THREE.modelViewMatrix.mul(vec4(Ns, 0.0)).xyz.normalize();
        const vV = THREE.modelViewMatrix.mul(vec4(C0, 1.0)).xyz.normalize().negate();
        const faceOn = THREE.step(CU.finHi.add(0.12), nV.dot(vV).abs()).mul(THREE.step(0.5, CU.finOnly));
        scale = scale.mul(float(1).sub(faceOn));
    }
    // (g5) the card's offset and width in the bind frame: the bones carry the result
    const pos = centre.add(P0.sub(centre).mul(scale)).add(disp);
    // THE COAT'S OWN MOTION VECTORS (round 2). three's velocity (what TAA reprojects with) is the current position less
    // positionPrevious, which skinning sets to the PREVIOUS SKINNED position alone: the coat's offsets (the sway, the
    // wind, the width floor, the LOD's widening) were in the current position and missing from the previous one, so TAA
    // fetched every card's history displaced by its whole offset (up to ~1 px at a tip at 1.5 m) instead of by its
    // frame-to-frame motion. Wherever this pass writes velocity (builder.needsPreviousData: an MRT with 'velocity'; the
    // shadow pass and plain forward passes pay nothing), the previous position gets the same offsets: the sway and wind
    // of the previous frame (time - deltaTime), widened by this frame's scale (it moves with the camera's distance, a
    // negligible change per frame). (g5) In the bind frame like the rest: positionPrevious here is the INPUT of the previous
    // bones' skin (SkinningNode runs after this node), the wind's phase reads the previous skinned centreline
    if (opts.motionVectors === false) {
        m.positionNode = pos;
    } else {
        const nBones = mesh.skeleton?.bones?.length || 0;
        m.positionNode = THREE.Fn((builder) => {
            if (nBones > 0 && builder.needsPreviousData()) {
                const prevBones = THREE.referenceBuffer('skeleton.previousBoneMatrices', 'mat4', nBones);
                const Cp0 = sk.getSkinnedPosition(prevBones, centre);
                const dp = dispAt(t.sub(THREE.deltaTime), Cp0);
                THREE.positionPrevious.assign(centre.add(THREE.positionPrevious.sub(centre).mul(scale)).add(dp));
            }
            return pos;
        })();
    }
    // (g5) THE FIN'S DEPTH PUSH (look.finPush, fin coats): a fin's depth moves back by finPush along its view ray and
    // nothing else does. Over the body a fin lies a pile's height above the skin, which the ray reaches within height /
    // |N.V| (12 mm at N.V 0.3 for velvet's 3.6 mm pile), so the skin hides it there; past the outline nothing lies behind
    // it and it shows. The fin band then needs no angle to find the outline: at the eye-ring close the arms seen at grazing
    // had every fin drawn over their tops (|N.V| under finHi across the whole arm) as pale rectangular fleece chips.
    // It is written into the CLIP position's z (the depth a point r + t along this ray would have: z + P32 (1 / k - 1), k = 1
    // + t / r), so x, y and w stay the fin's own and it cannot leave its pixels, and the motion vectors need no term.
    // (A first form moved the position along the ray: in this node's bind frame, so the bones turned it sideways and the
    // fins left a curled arm: g5_groom/renders/s05_push_nodepth.png.) Perspective cameras only: P33 is 1 for an
    // orthographic camera and the term goes to 0
    if (CU.look.finOnly > 0 && CU.finPush) {
        m.vertexNode = THREE.Fn(() => {
            const Pm = THREE.cameraProjectionMatrix;
            const clip = Pm.mul(vec4(THREE.positionView, 1.0)).toVar();
            const t = CU.finPush.mul(CU.finOnly.clamp(0, 1));
            const back = t.div(THREE.positionView.length().add(t));          // 1 - 1 / k
            const dz = Pm.element(3).element(2).mul(back).mul(float(1).sub(Pm.element(3).element(3)));
            return vec4(clip.x, clip.y, clip.z.sub(dz), clip.w);
        })();
    }
    // never a camera-pixel width in the light's frame
    m.castShadowPositionNode = P;
    // (the second restart) the AO pass's own material (coatMaterial) rides the same vertex stage
    if (m.coatAOMaterial) {
        m.coatAOMaterial.positionNode = m.positionNode;
        if (m.vertexNode) m.coatAOMaterial.vertexNode = m.vertexNode;
    }
    return m;
}

// ============================================================================================ the cloak
export function coatNdv() {
    // the coat's facing for creature-wide effects (the cloak's held edges, a rim): the ROOT's base normal, so the coat's
    // rim is the body's
    return THREE.normalViewGeometry.dot(THREE.positionViewDirection).abs().clamp(0.0, 1.0);
}

export function setCoatOpacity(m, opacity) {
    // the remix's creature-wide opacity (the cloak) on the coat: the cards keep their coverage (round 2: the coverage is
    // the material's own discard, which the opacity never touches) and turn see-through as the body does, blended normally
    // (the coat's plain overwrite would hide the cloak). r184 multiplies alpha by the opacity before its alpha test, so
    // the token test moves with it. One pass (a transparent DoubleSide material would draw twice)
    m.transparent = true;
    m.blending = THREE.NormalBlending;
    m.forceSinglePass = true;
    m.depthWrite = true;
    m.opacityNode = opacity;
    m.alphaTestNode = THREE.float(0.001).mul(opacity);
    m.needsUpdate = true;
    // (the second restart) the AO pass's own material (coatMaterial) follows, so a see-through card claims the AO there
    // as the lit material did: its alpha times the opacity, blended normally
    const a = m.coatAOMaterial;
    if (a) {
        a.transparent = true;
        a.blending = THREE.NormalBlending;
        a.forceSinglePass = true;
        a.depthWrite = true;
        a.opacityNode = opacity;
        a.alphaTestNode = THREE.float(0.001).mul(opacity);
        a.needsUpdate = true;
    }
    return m;
}

// ============================================================================================ the skin's coat layer
export function coatSkinLayer(m, pack, CU, baseMap = null, tip = null) {
    // the coat maps on the skin (the COAT PACK on the base's texels: R density, G length, BA comb): between the cards
    // and, past the ladder's last entry, instead of them. Wraps the skin material's own nodes (bestiary's skinMaterial or
    // remix's), so its display, remix and growth terms stay underneath: the fur's colour (the skin's own through the
    // coat's colour pipeline at a representative height), a matte lobe, a velvet sheen, the subsurface held back
    const { texture, uv, float, mix, smoothstep, vec3 } = THREE;
    if (!pack) return m;
    pack.colorSpace = THREE.NoColorSpace;
    const pk = texture(pack, uv());
    const dens = pk.r.mul(CU.layerW).clamp(0, 1);
    // THE COAT'S OWN RELIEF (the integration, 10-29: the velvet octopus, the coat maps alone, read as the bare skin with
    // its gloss off: the skin's papillae and pores still showed under a 3.6 mm pile). The skin's normal gives way under
    // the coat (layerFlat x density) to the smooth surface, carrying the coat's strands as a bump from the pack's height
    // G (per strand at the pack's texels; its mips smooth it away with distance, so it never crawls): study T's painted fur,
    // drawn from the groom's own bake
    if (CU.look.layerFlat > 0 || CU.look.layerBump > 0) {
        const skinN = m.normalNode || THREE.normalView;
        const furN = CU.look.layerBump > 0 ? THREE.bumpMap(texture(pack, uv()).g, CU.layerBump) : THREE.normalView;
        m.normalNode = mix(skinN, furN, dens.mul(CU.layerFlat).clamp(0, 1)).normalize();
    }
    const skinCol = m.colorNode ? vec3(m.colorNode.xyz ?? m.colorNode) : vec3(0.2);
    // the visible part of a coat from above: mid to tip (h ~0.72). The tip-lift weight is a constant, computed here:
    // an all-literal smoothstep(0.35, 1.0, 0.72) reaches WGSL as an abstract-typed call naga rejects at runtime
    // ("Abstract types may only appear in constant expressions": the skin and its shadow material failed to compile)
    const hRep = 0.72;
    const tipW = ((x) => x * x * (3 - 2 * x))(Math.min(1, Math.max(0, (hRep - 0.35) / 0.65)));
    const avg = mix(CU.rootDark, float(1), smoothstep(0.0, CU.rootDarkEnd.max(1e-3), float(hRep)))
        .mul(float(1).add(CU.tipLift.mul(tipW)));
    // the strands in the colour: the pack's height G (mean ~0.45 over the octopus's coats) darkens the deep gaps and
    // lifts the tall tips, the mean colour kept
    const detail = float(1).add(pk.g.sub(0.45).mul(2.0).mul(CU.layerDetail)).clamp(0.4, 1.6);
    // the skin's fine colour softens under the coat (fur covers the pores and the papillae's dark dots): the skin's colour
    // times its albedo's ratio of a blurred level to its own (baseMap: the base material's albedo, when given), so the
    // display families, which multiply, stay
    let under = skinCol;
    if (baseMap && CU.look.layerSoften > 0) {
        // (g5) THE BLUR'S REACH IN MILLIMETRES, not mip levels. It read the albedo layerSoften levels coarser than the
        // pixel's own, so its reach on the skin grew with the distance: ~2-5 mm at 0.5-2 m (the pores and papillae it is
        // for), several cm by 15 m (6-7 levels into a 4096 page), where it averaged the bare zones' pale skin into the
        // fur's colour and the coated octopus lightened against the bare one as it receded (+7.4 levels from 3 to 15 m;
        // flat with the blur off: batch 3's tone_drift). Now the level is clamped between the pixel's own and the one
        // whose texels span layerSoftenMm on the skin (metres per texel from the surface's own screen derivatives), and
        // the blur gives way to the plain colour as the pixel's own footprint reaches that scale
        const { dFdx, dFdy, max, vec2: v2 } = THREE;
        const W = baseMap.image?.width || 1024, H = baseMap.image?.height || W;
        const tuv = uv().mul(v2(W, H));
        const tpp = max(v2(dFdx(tuv.x), dFdx(tuv.y)).length(), v2(dFdy(tuv.x), dFdy(tuv.y)).length()).max(1e-6);
        const lod0 = tpp.log2();
        const mpp = max(dFdx(THREE.positionWorld).length(), dFdy(THREE.positionWorld).length()).max(1e-9);
        const lodSoft = CU.layerSoftenMm.mul(1e-3).mul(tpp).div(mpp).max(1e-6).log2();
        const lod1 = lodSoft.clamp(lod0, lod0.add(CU.layerSoften));
        const wS = smoothstep(0.0, 1.0, lod1.sub(lod0));
        const a0 = texture(baseMap, uv()).rgb.max(0.02);
        const a1 = texture(baseMap, uv()).level(lod1.max(0.0)).rgb;
        under = mix(skinCol, skinCol.mul(a1.div(a0).clamp(0.5, 2.0)), wS);
    }
    // (round 2) the groom's tone match (look.layerTone, per skin set when the forge names one)
    const setName = String(m.name || '').replace(/_(bestiary|remix)$/, '');
    const tone = CU.layerToneBy?.[setName] ?? CU.layerTone ?? vec3(1.0);
    let furCol = mix(under, CU.color, CU.colorMix).mul(CU.tint).mul(tone).mul(avg).mul(detail).clamp(0, 0.98);
    // (W3a) THE TIP COLOUR in the maps (look.tipMix > 0 and the coat's tip pack for this skin set): past the close-up the
    // layer is the whole coat, so it takes look.layerTip of the tips' colour by their share (the coat seen as maps: the
    // cards' own mix of tip and root); up close it is the coat's interior between the cards, which shows no tips
    if (tip && CU.look.tipMix > 0) {
        tip.colorSpace = THREE.NoColorSpace;
        const tp = texture(tip, uv());
        const tipCol = mix(tp.rgb.max(0.0).pow(vec3(2.2)), CU.color, CU.colorMix).mul(CU.tint).mul(tone).mul(detail);
        const wT = tp.a.mul(CU.tipShare).mul(CU.tipMix).mul(CU.layerTip).mul(float(1).sub(CU.closeW)).clamp(0, 1);
        furCol = mix(furCol, tipCol, wT).clamp(0, 0.98);
    }
    // the velvet's grazing brightening as an albedo rim (bestiary's displayFuzz: + 0.10 (1 - N.V)^2.5 on soft skin),
    // not three's sheen lobe: its Neubelt visibility 1 / (4 (NL + NV - NL NV)) is infinite where both clamp to 0, and
    // on the webs' folds that drew black cracks (the 10-29 maps-only stills)
    const ndv0 = THREE.normalView.dot(THREE.positionViewDirection).clamp(0.0, 1.0);
    // (coat G6) A FIN COAT'S LAYER PLATEAUS AT THE OUTLINE while its fins are drawn (look.finEdge x CU.finW): its grazing
    // terms, the rim here and the velvet lobe below (which made the line: g6/look/v4a_x4.png, sheen 0 alone takes it
    // away), are read as if |N.V| were at least finEdge, so they stop climbing over the last pixels where the fins,
    // standing just past the outline, carry the pile's grazing light. Without it the lobe's peak was a 1 px bright line
    // along the skin's own silhouette under the fin band (g5_integrate/look/c_velvet_arm_line_x4.png)
    const finCoat = CU.look.finOnly > 0;
    const edgeFloor = finCoat ? CU.finEdge.mul(CU.finW).clamp(0, 0.95) : null;
    const ndv = finCoat ? ndv0.max(edgeFloor) : ndv0;
    // (coat G6) the interior's weight (look.layerInterior x density x CU.closeW): the grazing terms of the coat's TOP (the
    // rim here, the velvet lobe and the skin's gloss below) give way where the cards are the coat
    const inW = CU.layerInterior.mul(pk.r).mul(CU.closeW).clamp(0, 1);
    const topW = float(1).sub(inW);
    const rim = float(1).sub(ndv).pow(2.5).mul(CU.layerSheen).mul(topW);
    // (g5) THE COAT'S INTERIOR between drawn cards (look.layerDeep): up close the cards are the coat and what shows of
    // the layer between their strands is the coat's depth, in its own shade (the gaps' darkness that separates strands
    // and locks: round 2's close-up read as brushed felt, the cards and the layer behind them one brown); scaled by the
    // pack's density and the close-up's weight (CU.closeW: 0 for a fin coat and from ~10 m on, where no gap resolves and
    // the layer is the coat's own body)
    const deep = float(1).sub(CU.layerDeep.mul(pk.r).mul(CU.closeW).clamp(0, 1));
    m.colorNode = mix(skinCol, furCol.add(furCol.mul(rim)).mul(deep).clamp(0, 0.98), dens);
    // (round 2) THE VELVET LOBE on the layer (velvetDirect / velvetAlbedo: Charlie, brighter at grazing in the light
    // and under the sky), weighted by the coat's density, in the fur's colour toward white. Added to the skin material's
    // own lighting model (whatever bestiary or remix built: its direct and environment terms run first), so the skin's
    // display, subsurface and growth terms stay as they are; a material without the coat (dens 0) gains nothing visible
    // and the far LOD pays a few ALU per pixel for it
    // (g5) and THE SKIN'S OWN LOBE UNDER THE COAT, look.layerSpec, which never applied before: three r184's setupSpecular
    // reads the plain material.specularIntensity, never the specularIntensityNode this layer set, and its direct light
    // adds every lobe at Schlick f90 = 1 whatever the intensity (the axolotl's finding, work/bestiary/engine_test/
    // axolotl_scene.js scaleDirectSpecular). So the skin's own specular increments, direct and environment, are scaled
    // here by mix(1, layerSpec, density) (the wet skin's gloss gives way under the fur), before the velvet lobe is added
    if (typeof m.setupLightingModel === 'function') {
        // (coat G6) both x the top's weight: between drawn cards the interior has no gloss and no sheen of its own
        const specK = mix(float(1.0), CU.layerSpec.mul(topW), dens);
        const sheenCol = CU.look.sheen > 0 ? mix(furCol, vec3(1.0), CU.sheenTint).mul(CU.sheen).mul(dens).mul(topW) : null;
        // (coat G6) the lobe's normal, lifted toward the eye at a fin coat's outline (liftNormal: |N.V| >= the floor above)
        const lobeN = finCoat ? liftNormal(THREE.normalView, THREE.positionViewDirection, edgeFloor) : THREE.normalView;
        const orig = m.setupLightingModel;
        m.setupLightingModel = function (builder) {
            const lm = orig.call(this, builder);
            const direct = lm.direct.bind(lm);
            lm.direct = (input, b) => {
                const s0 = input.reflectedLight.directSpecular.toVar();
                direct(input, b);
                input.reflectedLight.directSpecular.assign(s0.add(input.reflectedLight.directSpecular.sub(s0).mul(specK)));
                if (!sheenCol) return;
                const N = lobeN, V = THREE.positionViewDirection;
                input.reflectedLight.directSpecular.addAssign(input.lightColor.mul(sheenCol)
                    .mul(velvetDirect(N, V, input.lightDirection, CU.sheenRough, CU.look.sheenModel > 0 ? CU.sheenModel : null)));
            };
            if (typeof lm.indirectSpecular !== 'function') return lm;
            const ind = lm.indirectSpecular.bind(lm);
            lm.indirectSpecular = (b) => {
                const { iblIrradiance, reflectedLight } = b.context;
                const s0 = reflectedLight.indirectSpecular.toVar();
                ind(b);
                reflectedLight.indirectSpecular.assign(s0.add(reflectedLight.indirectSpecular.sub(s0).mul(specK)));
                if (!sheenCol) return;
                reflectedLight.indirectSpecular.addAssign(iblIrradiance.mul(1 / Math.PI).mul(sheenCol)
                    .mul(velvetAlbedo(lobeN, THREE.positionViewDirection, CU.sheenRough)));
            };
            return lm;
        };
    }
    if (m.roughnessNode) m.roughnessNode = mix(m.roughnessNode, CU.layerRoughness, dens);
    else m.roughnessNode = mix(float(m.roughness ?? 0.5), CU.layerRoughness, dens);
    // (the specularIntensityNode line that stood here is gone: three r184 never reads it; the lobe's scale is above)
    if (m.thicknessColorNode) m.thicknessColorNode = m.thicknessColorNode.mul(float(1).sub(dens.mul(float(1).sub(CU.layerSSS))));
    // (round 2's integration) THE FURRED SKIN'S AO CLAIM: in N8AO's transparency pass this skin draws an AO-only
    // material (attachCoat swaps it in for that one draw, as the cards' own) writing the share of the host's AO it claims
    // back: look.layerAOClaim x the pack's density x the cards' presence. Between card rows the skin otherwise takes the
    // screen-space AO of the cards in front of it whole (a black crevice under the mantle at 0.3 m); bare zones
    // (density 0) and the ladder's far end (no cards: the maps alone take the AO as the bare skin does) claim nothing
    if (CU.look.layerAOClaim > 0) {
        const aoS = new THREE.MeshBasicNodeMaterial({
            side: m.side, transparent: false, depthWrite: true, alphaToCoverage: false,
            blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor,
            blendDst: THREE.ZeroFactor, blendEquationAlpha: THREE.AddEquation, blendSrcAlpha: THREE.OneFactor,
            blendDstAlpha: THREE.ZeroFactor, forceSinglePass: true, fog: false, toneMapped: false,
        });
        aoS.colorNode = THREE.vec4(0.0, 0.0, 0.0, CU.layerAOClaim.mul(pk.r).mul(CU.closeW).clamp(0, 1));
        aoS.userData.noAutoAlphaToCoverage = true;
        aoS.userData.coat = true;
        aoS.name = `${m.name || 'skin'}_coat_ao`;
        m.coatAOMaterial = aoS;
        m.addEventListener('dispose', () => aoS.dispose());
    }
    m.userData.coatLayer = true;
    m.needsUpdate = true;
    return m;
}

// ============================================================================================ LOD
function lodAt(table, screen) {
    // the manifest's ladder (screen size descending): cut and width interpolated in log(screen); past the last entry 0
    if (!table || !table.length) return { cut: 1e6, width: 1.0 };
    const s = Math.max(screen, 1e-6);
    if (s >= table[0].screen) return { cut: table[0].cut, width: table[0].width ?? 1.0 };
    for (let i = 0; i < table.length - 1; i++) {
        const a = table[i], b = table[i + 1];
        if (s <= a.screen && s >= b.screen) {
            const f = Math.log(s / b.screen) / Math.log(a.screen / b.screen);
            return { cut: b.cut + (a.cut - b.cut) * f, width: (b.width ?? 1) + ((a.width ?? 1) - (b.width ?? 1)) * f };
        }
    }
    const z = table[table.length - 1];
    return { cut: 0.0, width: z.width ?? 1.0 };
}

export function coatLOD(meshes, man, CU, opts = {}) {
    // the draw range per primitive from the camera, once per frame per camera (onBeforeRender of each coat mesh). screen
    // = the coat's bounding-sphere diameter over the viewport height (UE's screen size); a forced LOD (opts.force /
    // ctl.force: a cut, or {cut, width}) for timing and review
    const ranks = man.ranks || 1;
    const prims = new Map((man.primitives || []).map((p) => [p.base_material, p]));
    const sphere = new THREE.Sphere();
    const tmp = new THREE.Vector3(), camP = new THREE.Vector3();
    const ctl = { screen: 0, cut: 1e6, width: 1, force: opts.force ?? null, frame: -1, camId: -1, drawn: 0,
        aoMaterial: opts.aoMaterial !== false };   // (the second restart) N8AO's transparency pass draws the AO-only material
    let r0 = 0;
    for (const o of meshes) {
        o.geometry.computeBoundingSphere();
        r0 = Math.max(r0, o.geometry.boundingSphere.radius);
    }
    sphere.copy(meshes[0].geometry.boundingSphere);
    function update(renderer, camera, mesh) {
        const frame = renderer?.info?.frame ?? 0;
        if (ctl.frame === frame && ctl.camId === camera.id) return;
        // only a scene camera picks the LOD (a shadow pass keeps the main view's)
        if (!(camera.isPerspectiveCamera || camera.userData?.coatLOD)) return;
        ctl.frame = frame;
        ctl.camId = camera.id;
        // (round 2) the dither's frame counter: the golden-ratio walk advances once per rendered frame
        if (CU.frame) CU.frame.value = frame % 4096;
        mesh.updateWorldMatrix(true, false);
        const s = mesh.matrixWorld.getMaxScaleOnAxis();
        tmp.copy(sphere.center).applyMatrix4(mesh.matrixWorld);
        const d = Math.max(1e-4, tmp.distanceTo(camera.getWorldPosition(camP)));
        const halfH = d * Math.tan(THREE.MathUtils.degToRad(camera.fov) * 0.5) / (camera.zoom || 1);
        ctl.screen = (r0 * s) / halfH * (CU.lodBias?.value ?? 1.0);
        let L = lodAt(man.lod, ctl.screen);
        if (ctl.force != null) L = typeof ctl.force === 'number' ? { cut: ctl.force, width: lodAt(man.lod, 1e6).width } : ctl.force;
        ctl.cut = Math.min(ranks, Math.max(0, L.cut));
        ctl.width = L.width ?? 1.0;
        // the dissolve band sits just under the cut, stretched so cut = ranks draws every card whole and cut = 0 none:
        // a card's key rank + strandRandom fades over [cutEff - rankFade, cutEff], cutEff = cut x (1 + rankFade / ranks)
        const fadeW = CU.rankFade?.value ?? 0.8;
        const cutEff = ctl.cut * (1 + fadeW / ranks);
        CU.rankCut.value = cutEff;
        CU.widthScale.value = ctl.width;
        // (g5) THE CLOSE-UP'S WEIGHT, smoothstep over the share of ranks drawn (look.closeLo .. closeHi), none for a fin
        // coat (its cards never cover the face-on skin): what the furred skin does because cards lie over it follows
        // it, and nothing else. Past it the skin is exactly the maps' skin, so the ladder's hand-over is the cards alone.
        // (The skin's own colour under the fur followed the cut, the AO claim the share of ranks.)
        const finCoat = (CU.finOnly?.value ?? CU.look.finOnly ?? 0) > 0;
        const lo = CU.closeLo?.value ?? 0.6, hi = Math.max(lo + 1e-3, CU.closeHi?.value ?? 1.0);
        const x = finCoat ? 0 : Math.min(1, Math.max(0, (ctl.cut / ranks - lo) / (hi - lo)));
        CU.closeW.value = x * x * (3 - 2 * x);
        // (g5) the far take's weight (look.aoTakeFar), over its own range of the same share
        const loF = CU.aoFarLo?.value ?? 0.4, hiF = Math.max(loF + 1e-3, CU.aoFarHi?.value ?? 0.8);
        const xF = finCoat ? 0 : Math.min(1, Math.max(0, (hiF - ctl.cut / ranks) / (hiF - loF)));
        CU.farW.value = xF * xF * (3 - 2 * xF);
        // (coat G6) the fins' presence for the layer's outline plateau (look.finEdge): the share of ranks drawn
        CU.finW.value = finCoat ? Math.min(1, Math.max(0, ctl.cut / ranks)) : 0;
        // (g5, 10-31) the takes' scale by the host's AO radius over the coat's length (look.aoHostLo .. aoHostHi, log space)
        const aoR = Number(globalThis._n8ao?.configuration?.aoRadius);
        const coatLen = Number(man.look?.length_m) || 0.04;
        if (Number.isFinite(aoR) && aoR > 0) {
            const hLo = Math.max(1e-3, CU.aoHostLo?.value ?? 0.5), hHi = Math.max(hLo * 1.01, CU.aoHostHi?.value ?? 7.5);
            const xH = Math.min(1, Math.max(0, Math.log(aoR / coatLen / hLo) / Math.log(hHi / hLo)));
            CU.hostTake.value = xH * xH * (3 - 2 * xH);
            if (ctl.hostTakeLogged !== CU.hostTake.value) {
                ctl.hostTakeLogged = CU.hostTake.value;
                console.log(`[coat] the host's AO radius ${aoR} m over the coat's length ${coatLen} m: the cards' AO takes x ${CU.hostTake.value.toFixed(3)}`);
            }
        }
        // the skin layer's weight: layerFar, to layerNear with the close-up's weight, so it never switches in one frame (it
        // once did at cut 0: on the ladder's forced sweep a third of the creature changed by more than 2 levels in that
        // frame: work/bestiary/coat/g_check/look/c04_pop_sheet.png). A FIN coat's layer keeps layerFar at every cut (its
        // close-ups read as the maps-alone velvet does, without the bare skin's gloss: g_check/look/c05_velvet_layer_ab.png)
        CU.layerW.value = CU.look.layerFar + (CU.look.layerNear - CU.look.layerFar) * CU.closeW.value;
        // draw ranks 0 .. ceil(cutEff) - 1 (the fading rank stays in the range)
        const k = Math.min(ranks, Math.ceil(cutEff - 1e-6));
        let drawn = 0;
        for (const o of meshes) {
            const p = prims.get(o.userData.coatBase);
            const idx = o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count;
            const n = k <= 0 ? 0 : (p?.rank_index_end ? p.rank_index_end[k - 1] : idx);
            o.geometry.setDrawRange(0, n);
            drawn += n / 3;
        }
        ctl.drawn = drawn;
    }
    for (const o of meshes) {
        const prev = o.onBeforeRender, prevAfter = o.onAfterRender;
        let swapped = null;                          // (the second restart) the scene whose override this draw set
        o.onBeforeRender = function (renderer, scene, camera, geometry, material, group) {
            update(renderer, camera, o);
            // (round 2) the AO take: is this draw N8AO's transparency pass? (a per-object uniform, so the value holds
            // for this draw only; the scene pass draws with 0)
            const aoNow = renderer?.getRenderTarget?.()?.texture?.name === 'N8AO.TransparencyDepthWriteFalse';
            if (CU.aoPass) CU.aoPass.value = aoNow ? 1 : 0;
            if (prev) prev.call(this, renderer, scene, camera, geometry, material, group);
            // (the second restart) and there the card draws its AO-only material (coatMaterial: the discard and the
            // alpha, no lighting) in place of the lit one, for this one draw
            if (aoNow && ctl.aoMaterial && material?.coatAOMaterial && scene && scene.overrideMaterial == null) {
                scene.overrideMaterial = material.coatAOMaterial;
                swapped = scene;
                if (!ctl.aoLogged) {
                    ctl.aoLogged = true;
                    console.log('[coat] N8AO transparency pass: the cards draw their AO-only material there');
                }
            }
        };
        o.onAfterRender = function (renderer, scene, camera, geometry, material, group) {
            if (swapped) { swapped.overrideMaterial = null; swapped = null; }
            if (prevAfter) prevAfter.call(this, renderer, scene, camera, geometry, material, group);
        };
    }
    ctl.update = update;
    return ctl;
}

// ============================================================================================ loading and attaching
export async function loadCoat(bytes) {
    // a coat glb (bytes: Uint8Array / ArrayBuffer) -> the parsed gltf
    const buf = bytes instanceof ArrayBuffer ? bytes : bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    return await new globalThis.GLTFLoader().parseAsync(buf, '');
}

async function packTexture(gltf, index, wrap = THREE.ClampToEdgeWrapping) {
    // a coat pack by texture index. In the eidoverse harness an image the GLTFLoader did not bind to a material slot
    // is never migrated to a DataTexture, and Deno's ImageBitmap upload writes no pixels (render_scene.mjs, the GLB
    // migrate header): decode its bytes through the harness's own loader (glTF rows, no flip, CPU mips). Elsewhere
    // (a browser) the parser's texture is fine
    const parser = gltf.parser;
    const img = parser.json.images?.[parser.json.textures?.[index]?.source];
    if (typeof globalThis.loadImageTexture === 'function' && img && img.bufferView !== undefined) {
        const bv = await parser.getDependency('bufferView', img.bufferView);
        const t = await globalThis.loadImageTexture(new Uint8Array(bv), { flipY: false, wrap });
        t.colorSpace = THREE.NoColorSpace;
        return t;
    }
    const t = await parser.getDependency('texture', index);
    t.wrapS = t.wrapT = wrap;
    return t;
}

// ============================================================================================ shells
function tileClip(tex, cut, levels = 8) {
    // the shell tile's per-mip clip (A, the dot mask): the threshold keeping mip 0's coverage fraction at the cut, from
    // the texture's own CPU mips (the harness's box chain) when it has them; else the plain cut
    const mips = tex.mipmaps?.length ? tex.mipmaps : (tex.image?.data ? [tex.image] : null);
    if (!mips) return [cut];
    const alphaOf = (m) => { const a = new Float32Array(m.width * m.height); for (let i = 0; i < a.length; i++) a[i] = m.data[4 * i + 3] / 255; return a; };
    const a0 = alphaOf(mips[0]);
    let n0 = 0;
    for (let i = 0; i < a0.length; i++) if (a0[i] > cut) n0++;
    const f0 = n0 / a0.length;
    const out = [cut];
    for (let k = 1; k < Math.min(levels, mips.length); k++) {
        const a = alphaOf(mips[k]).sort();
        out.push(Math.min(cut, Math.max(0.02, a[Math.min(a.length - 1, Math.floor((1 - f0) * a.length))])));
    }
    return out;
}

function furredIndex(geometry, pack, threshold = 0.02) {
    // the base primitive's triangles where the coat pack says fur (R) at any corner (the pack's CPU pixels: the
    // harness's DataTexture); every triangle when the pixels are not readable
    const idx = geometry.index;
    const img = pack?.image;
    if (!idx || !img?.data || !geometry.attributes.uv) return idx;
    const uv = geometry.attributes.uv, W = img.width, H = img.height, D = img.data;
    const R = (i) => {
        const x = Math.min(W - 1, Math.max(0, Math.floor(uv.getX(i) * W)));
        const y = Math.min(H - 1, Math.max(0, Math.floor(uv.getY(i) * H)));
        return D[4 * (y * W + x)] / 255;
    };
    const s = idx.array, keep = [];
    const start = geometry.groups?.length ? 0 : 0;
    for (let t = start; t + 2 < s.length; t += 3) {
        if (R(s[t]) > threshold || R(s[t + 1]) > threshold || R(s[t + 2]) > threshold) keep.push(s[t], s[t + 1], s[t + 2]);
    }
    return new THREE.BufferAttribute(new Uint32Array(keep), 1);
}

export function shellMaterial(base, shell, pack, U, CU, spec, uvPerTile, opts = {}) {
    // one material for every layer of one skin set: the layer from instanceIndex (h = (k + 1) / layers), raised along the
    // skin normal by h x the coat pack's height (G x look.height_m, the forge's spec), the strand tile in the base's
    // uv (uv / uvPerTile tiles, one tile = spec.tile_mm), leaning along the pack's comb by 2 B h height; a dot shows
    // while its height fraction R >= h, gated by the pack's coverage R; lit as the cards (the comb as the tangent)
    const { texture, uv, float, vec2, vec3, vec4, mix, smoothstep, max, int, dFdx, dFdy, uniformArray } = THREE;
    const st = uv();
    const layers = CU.shellLayers;
    const hk = float(THREE.instanceIndex).add(1.0).div(layers);
    const pkV = texture(pack, st).level(0);                        // (vertex stage: an explicit level)
    const heightM = float(CU.look.heightM ?? 0.0036);
    const { CoatNodeMaterial } = coatClasses();
    const m = new CoatNodeMaterial({
        metalness: 0, roughness: CU.look.envRoughness, side: THREE.DoubleSide, transparent: false, depthWrite: true,
        alphaTest: CU.look.cut ?? 0.34, alphaToCoverage: false,
    });
    const H = pkV.g.mul(heightM);
    const N = THREE.normalLocal.normalize();
    m.positionNode = THREE.positionLocal.add(N.mul(hk.mul(H)));
    // fragment: the comb in the base tangent frame (x along the tangent, y along the bitangent), the lean offset
    const pk = texture(pack, st);
    const comb = vec2(pk.b, pk.a).sub(0.5).mul(2.0);
    const tileMm = spec.tile_mm || 10.0;
    const tuv0 = st.div(uvPerTile);
    const lean0 = texture(shell, tuv0).b;
    const leanTiles = comb.mul(lean0.mul(2.0).mul(hk).mul(pk.g.mul(heightM)).div(tileMm * 1e-3));
    const tuv = tuv0.add(leanTiles);
    const tl = texture(shell, tuv);
    // the per-mip clip for the dot mask, at the level the sampler reads (anisotropic, as the cards)
    const clip = tileClip(shell, CU.look.cut ?? 0.34);
    const sz = [shell.image?.width || 512, shell.image?.height || 512];
    const px = tuv.mul(vec2(sz[0], sz[1]));
    const rx = vec2(dFdx(px.x), dFdx(px.y)).length(), ry = vec2(dFdy(px.x), dFdy(px.y)).length();
    const rMax = max(rx, ry).max(1e-6), rMin = THREE.min(rx, ry).max(1e-6);
    const aniso = Math.max(1, shell.anisotropy || 1);
    const lod = rMax.div(rMax.div(rMin).clamp(1.0, aniso)).log2().clamp(0, clip.length - 1);
    const clipArr = uniformArray(clip.map(Number), 'float');
    const l0 = lod.floor();
    const thr = mix(clipArr.element(int(l0)), clipArr.element(int(l0.add(1).min(clip.length - 1))), lod.sub(l0)).max(0.02);
    let alpha = tl.a.mul(float(CU.look.cut ?? 0.34).div(thr))
        .mul(smoothstep(hk.sub(0.06), hk, tl.r))
        .mul(smoothstep(0.02, 0.25, pk.r))
        .mul(CU.shellFade);
    // colour: the skin's own albedo here (per pixel: the shell IS the skin's uv) through the remap / tint / display, then
    // the style's ramp with h = the layer
    const masks = base.thicknessMap ? texture(base.thicknessMap, st) : vec4(0.0, 0.0, 0.0, 0.5);
    const disp = base.emissiveMap ? texture(base.emissiveMap, st) : vec4(0.0, 0.0, 0.0, 0.5);
    let col = texture(base.map, st).rgb;
    if (opts.remap) col = opts.remap(col, { masks, display: disp });
    if (U?.tint) col = col.mul(U.tint);
    if (opts.display && U) {
        const pg = THREE.positionGeometry || THREE.positionLocal;
        if (opts.display.masks) col = opts.display.masks(col, U, disp);
        if (opts.display.clouds && U.clouds) col = opts.display.clouds(col, U, disp, masks, pg).col;
    }
    col = mix(col, CU.color, CU.colorMix).mul(CU.tint);
    const rootDark = mix(CU.rootDark, float(1), smoothstep(0.0, CU.rootDarkEnd.max(1e-3), hk));
    const tipLift = float(1).add(CU.tipLift.mul(smoothstep(0.35, 1.0, hk)));
    const vj = float(1).add(tl.g.sub(0.5).mul(2.0).mul(CU.strandJitter));
    const rgb = col.mul(rootDark).mul(tipLift).mul(vj).clamp(0, 0.98);
    // the comb as the strand tangent, tilted up by the lean (view space)
    const Nv = THREE.normalViewGeometry.normalize();
    const T = THREE.tangentView.mul(comb.x).add(THREE.bitangentView.mul(comb.y)).add(Nv.mul(0.35)).normalize();
    m.coatNodes = {
        T, h: hk, rough: CU.roughness, specular: CU.specular, shift: CU.shift, backlit: CU.backlit, envSpec: CU.envSpec, ttBundle: CU.ttBundle,
        scatterW: CU.scatter, wrap: CU.wrap, wrapMix: CU.wrapMix,
        shadowH: mix(CU.selfShadow, float(1), smoothstep(0.0, 0.9, hk)), ttMask: smoothstep(0.15, 0.90, hk),
    };
    m.colorNode = vec4(rgb, alpha);
    m.normalNode = THREE.normalViewGeometry;
    m.roughnessNode = CU.envRoughness;
    m.metalnessNode = float(0.0);
    m.aoNode = float(1).sub(float(1).sub(hk).mul(CU.aoRoot)).clamp(0.45, 1.0);
    // (g5) the host's ground occlusion (coatMaterial's note), the ventral weight at the shell's own uv (the skin's)
    if (typeof opts.groundOcclusion === 'function' && U) m.aoNode = m.aoNode.mul(opts.groundOcclusion(U, masks.g));
    m.userData.noAutoAlphaToCoverage = true;
    m.userData.coat = true;
    m.coatCut = CU.look.cut ?? 0.34;
    m.name = `coat_shells_${base?.name || 'base'}`;
    return m;
}

export async function coatShells(api, ctl, shellTex, opts = {}) {
    // the SHELLS for a short coat (the forge's 'shells' spec in the manifest): one instanced draw per skin set over the
    // furred triangles (the skin's own vertex buffers shared; the layer = instanceIndex), riding the creature's skin;
    // drawn only close up (screen >= the spec's from, faded over 20 % below it) unless forced (opts.force true / false)
    const man = ctl.manifest, spec = man.shells, CU = ctl.uniforms;
    if (!spec || !shellTex) return null;
    CU.look.heightM = man.look?.height_m ?? CU.look.heightM ?? 0.0036;
    CU.shellLayers ??= THREE.uniform(opts.layers ?? spec.layers ?? 8);
    CU.shellFade ??= THREE.uniform(1.0);
    const from = opts.from ?? man.short_end?.shells_from_screen ?? 4.0;
    const meshes = [];
    let baseSk = null;
    api.group.traverse((o) => { if (o.isSkinnedMesh && !baseSk && !o.userData?.bestiaryCoat) baseSk = o; });
    api.group.traverse((o) => {
        if (!o.isMesh || o.userData?.bestiaryCoat || o.userData?.coatShell) return;
        const nm = String(o.material?.name || '').replace(/_(bestiary|remix)$/, '');
        const pack = ctl.packs?.[nm], upt = spec.uv_per_tile?.[nm];
        if (!pack || !upt) return;
        meshes.push({ o, nm, pack, upt });
    });
    const out = [];
    for (const { o, nm, pack, upt } of meshes) {
        const g = new THREE.InstancedBufferGeometry();
        for (const k of ['position', 'normal', 'tangent', 'uv', 'skinIndex', 'skinWeight']) {
            if (o.geometry.attributes[k]) g.setAttribute(k, o.geometry.attributes[k]);
        }
        g.setIndex(furredIndex(o.geometry, pack));
        g.instanceCount = Math.round(CU.shellLayers.value);
        g.boundingSphere = o.geometry.boundingSphere;
        const base = await baseSource(api, nm);
        if (!base) continue;
        const mat = shellMaterial(base, shellTex, pack, api.uniforms, CU, spec, upt, opts);
        const mesh = new THREE.SkinnedMesh(g, mat);
        mesh.name = `coat_shells_${nm}`;
        mesh.userData.bestiaryCoat = true;
        mesh.userData.coatShell = true;
        mesh.userData.coatShellSources = { base, pack, upt, tex: shellTex, spec };     // for rebuilds (a remix)
        mesh.frustumCulled = false;
        mesh.castShadow = false;
        mesh.receiveShadow = true;
        api.group.add(mesh);
        mesh.bind(baseSk.skeleton, baseSk.bindMatrix);
        out.push(mesh);
    }
    // the close-up gate per frame (the cards' LOD screen size): instanceCount 0 skips the draw entirely
    const ctlS = { meshes: out, force: opts.force ?? null, from };
    for (const mesh of out) {
        const prev = mesh.onBeforeRender;
        mesh.onBeforeRender = function (renderer, scene, camera, geometry, material, group) {
            ctl.lodUpdate?.(renderer, camera, mesh);
            const s = ctl.lod.screen;
            const f = ctlS.force === true ? 1 : ctlS.force === false ? 0 : Math.min(1, Math.max(0, (s - from * 0.8) / (from * 0.2)));
            CU.shellFade.value = f;
            geometry.instanceCount = f > 0 ? Math.round(CU.shellLayers.value) : 0;
            if (prev) prev.call(this, renderer, scene, camera, geometry, material, group);
        };
    }
    return ctlS;
}

async function baseSource(api, name) {
    // the base's glTF source material by name (the parser caches it: the textures bestiary.js bound, no second upload)
    const parser = api.gltf?.parser;
    const defs = parser?.json?.materials || [];
    const k = defs.findIndex((d) => d.name === name);
    if (k < 0) return null;
    return await parser.getDependency('material', k);
}

function sameSkeleton(skA, namesB, inversesB) {
    if (skA.bones.length !== namesB.length) return false;
    for (let i = 0; i < namesB.length; i++) {
        if (skA.bones[i].name !== namesB[i]) return false;
        const a = skA.boneInverses[i].elements, b = inversesB[i].elements;
        for (let j = 0; j < 16; j++) if (Math.abs(a[j] - b[j]) > 1e-5) return false;
    }
    return true;
}

// (B3, HAIR_FUR H6) THE SCALP LAYER: human hair's skin under the cards (study T's haircap, baked into the skin as HS §9.6
// chose), from the forge's scalp pack (coatmaps.scalp: R the hair's cover with the part opened, G painted near-scalp
// strands, BA their direction). It works on ANY node material that exposes colorNode (and, on the human's skin material,
// m.skin.diffuse, which its lighting model reads): the skin's colour goes toward the hair's ROOT colour (the pigment model
// darkened by look.rootDark) by the cover, the painted strands lighter than the gaps between them, so no pale scalp shows
// between cards and the part reads as a thin line of skin. Call before the material's first render.
export function scalpLayer(m, pack, CU, opts = {}) {
    if (!m || !pack) return false;
    const { texture, uv, vec3, mix, float } = THREE;
    pack.colorSpace = THREE.NoColorSpace;
    const p = texture(pack, uv());
    const sigma = vec3(0.419, 0.697, 1.37).mul(CU.eumelanin).add(vec3(0.187, 0.4, 1.05).mul(CU.pheomelanin));
    let hair = THREE.exp(sigma.mul(CU.pigmentPath).negate());
    hair = mix(hair, hair.mul(CU.dye).mul(2.0).clamp(0, 1), CU.dyeAmount).mul(CU.tint);
    const root = hair.mul(CU.rootDark);
    const strands = mix(root.mul(0.7), hair, p.g);
    // (B3b) 0.9 x (0.75 .. 1) -> 1 x (0.92 .. 1): under the cards the scalp is the hair's (study T's haircap, HS §3.6); at
    // the crown whorl every card begins (its root fading in), the scalp carried the read there and showed as a
    // skin-coloured disc (b3b_e13 crown)
    const cover = p.r.mul(opts.strength ?? 1.0).mul(mix(float(0.92), float(1.0), p.g));
    const c0 = m.colorNode || vec3(m.color?.r ?? 0.5, m.color?.g ?? 0.5, m.color?.b ?? 0.5);
    m.colorNode = mix(c0, strands, cover);
    if (m.skin) m.skin.diffuse = m.colorNode;
    m.userData.scalpLayer = true;
    m.needsUpdate = true;
    return true;
}

export async function attachCoat(api, coatGltf, opts = {}) {
    // bind a coat (a parsed coat glb) to a Bestiary creature (bestiary.js create()'s api): one SkinnedMesh per coat
    // primitive on the creature's bones (by name), each in a CoatNodeMaterial built from its base material's maps; the
    // skin layer on the base's skin materials when the coat carries a pack (opts.skinLayer !== false); the LOD on
    // every frame's camera. opts: look ({...COAT_LOOK}), remap / display (see coatMaterial), force (an LOD cut),
    // skinLayer, shadows (cards cast: off by default; the body casts the stable shadow, CG 16.39)
    const man = coatGltf.userData?.bestiary?.coat || coatGltf.parser?.json?.extras?.bestiary?.coat || {};
    // (round 2) the coverage mode follows the host's TAA (opts.temporalAA; in the eidoverse harness globalThis._taa)
    // unless a look says otherwise: (g5) the dither walks with TAA and holds still without it, at the pixel's own mip
    const taa = opts.temporalAA ?? (globalThis._taa === true);
    const CU = coatUniforms(man.look, taa ? null : { ditherWalk: 0.0, taaBias: 0.0 }, opts.look);
    const U = api.uniforms || null;
    let baseSk = null;
    api.group.traverse((o) => { if (o.isSkinnedMesh && !baseSk && !o.userData?.bestiaryCoat) baseSk = o; });
    if (!baseSk) throw new Error('[coat] the creature has no skinned mesh to ride');
    const boneByName = new Map(baseSk.skeleton.bones.map((b) => [b.name, b]));
    const src = [];
    coatGltf.scene.traverse((o) => { if (o.isMesh && (o.material?.userData?.bestiary === 'coat' || /coat/.test(o.material?.name || ''))) src.push(o); });
    if (!src.length) throw new Error('[coat] the glb has no coat primitive (material extras bestiary: coat)');
    const meshes = [];
    const report = [];
    let shared = null;
    // the coat packs first (the cards read their density at the root; the skin's layer below reads them all over)
    const packTex = {};
    for (const [name, ti] of Object.entries(man.coat_pack || {})) {
        try { packTex[name] = await packTexture(coatGltf, ti); } catch (e) { report.push(`coat pack ${name}: ${e.message}`); }
    }
    // (W3a) the tip packs (man.tip_pack, per base material, as the coat packs; read only when look.tipMix > 0)
    const tipTex = {};
    if (CU.look.tipMix > 0) {
        for (const [name, ti] of Object.entries(man.tip_pack || {})) {
            try { tipTex[name] = await packTexture(coatGltf, ti); } catch (e) { report.push(`tip pack ${name}: ${e.message}`); }
        }
    }
    // (g5) THE ATTRIBUTE PAGE AS STORED. The harness decodes a glTF material's images through three's ImageBitmapLoader
    // ({ premultiplyAlpha: 'none' }), and Deno 2.8's createImageBitmap then DIVIDES each texel's colour by its alpha
    // wherever 0 < alpha < 255 (work/bestiary/patches/scratch_decode/NOTES.md; the H3 and axolotl rounds' finding). The
    // attribute page carries its sideways slope in A (0.39-0.62 over the covered texels: partial everywhere), so its
    // depth, strand id and root-to-tip reached the shader x ~2, clipped at 1 on half the strands: measured on the shipped
    // pages, the depth term's mean 0.052 -> 0.001 (the clump's self-shadow and its AO off), the strand id's jitter mean
    // 0 -> +0.49 (half the strands one value, every strand's tilt one way). The coat decodes that page itself, as it does
    // its packs (packTexture: the harness's loadImageTexture, default options, which keep the bytes), once per image and
    // shared by the primitives that sample it; in a browser the parser's texture is the page as stored already. (The
    // coverage page is one grey channel, no alpha; the packs come through packTexture; the velvet shell tile's alpha is
    // 0 or 255 only: no other coat image is touched by the division)
    const attrPages = new Map();
    const parserJson = coatGltf.parser?.json;
    async function attributePage(material) {
        const k = coatGltf.parser?.associations?.get(material)?.materials;
        const ti = k !== undefined ? parserJson?.materials?.[k]?.emissiveTexture?.index : undefined;
        if (ti === undefined || !material.emissiveMap) return null;
        if (!attrPages.has(ti)) {
            attrPages.set(ti, (async () => {
                const t = await packTexture(coatGltf, ti, material.emissiveMap.wrapS ?? THREE.ClampToEdgeWrapping);
                if (t !== material.emissiveMap) {
                    t.anisotropy = Math.max(t.anisotropy || 1, material.emissiveMap.anisotropy || 1);
                    t.name = `${material.emissiveMap.name || 'attributes'}_stored`;
                }
                return t;
            })().catch((e) => { report.push(`attribute page: ${e.message} (the material's own kept)`); return null; }));
        }
        return await attrPages.get(ti);
    }
    for (const o of src) {
        const baseName = o.material.userData?.base_material || man.primitives?.[0]?.base_material;
        const base = await baseSource(api, baseName);
        if (!base) { report.push(`no base material '${baseName}': coat primitive skipped`); continue; }
        const nvb = vertexBufferCount(o.geometry);
        if (nvb > 8) report.push(`${o.name}: ${nvb} vertex buffers (> 8 drops the draw silently): interleave _furdata/_rootdata/_furcenter`);
        // the skeleton: the creature's bones in the coat's joint order (shared when the joints and inverses are the
        // creature's own), the coat's own bind inverses (they match its vertices)
        let skeleton;
        if (o.isSkinnedMesh) {
            const names = o.skeleton.bones.map((b) => b.name);
            if (sameSkeleton(baseSk.skeleton, names, o.skeleton.boneInverses)) skeleton = baseSk.skeleton;
            else {
                const bones = names.map((n) => boneByName.get(n));
                const miss = names.filter((n, i) => !bones[i]);
                if (miss.length) throw new Error(`[coat] joints missing on the creature: ${miss.slice(0, 5).join(', ')}`);
                skeleton = shared && sameSkeleton(shared, names, o.skeleton.boneInverses) ? shared
                    : new THREE.Skeleton(bones, o.skeleton.boneInverses.map((m) => m.clone()));
                shared = skeleton;
            }
        } else {
            skeleton = baseSk.skeleton;            // a coat without a skin node: its skinIndex addresses the base's joints
        }
        const geo = o.geometry;
        const pack = packTex[baseName] || null;
        const tip = tipTex[baseName] || null;
        const attributes = await attributePage(o.material);
        const mat = coatMaterial(base, o.material, geo, U, CU, man, { ...opts, pack, attributes, tip });
        const mesh = new THREE.SkinnedMesh(geo, mat);
        mesh.name = `coat_${man.style || 'coat'}_${baseName}`;
        mesh.userData.bestiaryCoat = true;
        mesh.userData.coatBase = baseName;
        mesh.userData.coatSources = { base, src: o.material, pack, attributes, tip };  // for rebuilds (a remix)
        // (round 2) THE COAT'S OWN OCCLUSION: the cards opt out of the host's screen-space AO (N8AO's own convention,
        // userData.cannotReceiveAO, which the vendored N8AO keeps) and carry their own (root occlusion and the atlas
        // depth on the indirect light, the self-shadow through the clump on the direct); the body under them still
        // takes the AO. opts.receiveAO true: the first pass's behaviour
        mesh.userData.cannotReceiveAO = opts.receiveAO !== true;
        mesh.frustumCulled = false;                 // skinned: bind-pose bounds would cull moved arms (AG 00.72)
        mesh.castShadow = opts.shadows === true;
        mesh.receiveShadow = true;
        api.group.add(mesh);
        mesh.bind(skeleton, baseSk.bindMatrix);
        coatPosition(mat, mesh, CU, opts);
        meshes.push(mesh);
        // a coat primitive that came INSIDE the creature's glb: its loader mesh leaves (the new one replaces it)
        let p = o.parent;
        while (p && p !== api.group) p = p.parent;
        if (p === api.group && o !== mesh) o.parent.remove(o);
    }
    // the skin's coat layer, from the packs in the coat glb
    const layered = [];
    const baseMaps = {};                            // the base albedo per skin material (the layer softens it)
    if (opts.skinLayer !== false && man.coat_pack) {
        const todo = [];
        api.group.traverse((o) => {
            if (!o.isMesh || o.userData?.bestiaryCoat || !o.material) return;
            const nm = String(o.material.name || '').replace(/_(bestiary|remix)$/, '');
            if (packTex[nm] && !o.material.userData?.coatLayer) todo.push([o, nm]);
        });
        for (const [o, nm] of todo) {
            if (!(nm in baseMaps)) baseMaps[nm] = (await baseSource(api, nm))?.map || null;
            coatSkinLayer(o.material, packTex[nm], CU, baseMaps[nm], tipTex[nm] || null);
            layered.push(o);
        }
    }
    const lod = coatLOD(meshes, man, CU, opts);
    // (round 2's integration) THE FURRED SKIN'S AO CLAIM (coatSkinLayer's coatAOMaterial, built when look.layerAOClaim
    // > 0 at attach): in N8AO's transparency pass each layered skin draws its AO-only material, swapped in for that one
    // draw as the cards' are (scene.overrideMaterial, put back after it); ctl.update flags the skins cannotReceiveAO each
    // frame only while that material can be drawn there, so the pass never takes a skin's lit material (alpha 1: a whole
    // claim) instead
    const skinClaim = CU.look.layerAOClaim > 0 && layered.length > 0;
    let skinAncestors = false;
    if (skinClaim) {
        for (const o of layered) {
            const prev = o.onBeforeRender, prevAfter = o.onAfterRender;
            let swapped = null;
            o.onBeforeRender = function (renderer, scene, camera, geometry, material, group) {
                if (prev) prev.call(this, renderer, scene, camera, geometry, material, group);
                if (material?.coatAOMaterial && scene && scene.overrideMaterial == null
                    && renderer?.getRenderTarget?.()?.texture?.name === 'N8AO.TransparencyDepthWriteFalse') {
                    scene.overrideMaterial = material.coatAOMaterial;
                    swapped = scene;
                }
            };
            o.onAfterRender = function (renderer, scene, camera, geometry, material, group) {
                if (swapped) { swapped.overrideMaterial = null; swapped = null; }
                if (prevAfter) prevAfter.call(this, renderer, scene, camera, geometry, material, group);
            };
        }
    }
    const wv = new THREE.Vector3(), q = new THREE.Quaternion();
    let aoAsked = false;
    const ctl = {
        meshes, manifest: man, uniforms: CU, report, layered, packs: packTex, tips: tipTex, shells: null,
        get lod() { return { screen: lod.screen, cut: lod.cut, width: lod.width, triangles: lod.drawn }; },
        lodUpdate: (renderer, camera, mesh) => lod.update(renderer, camera, mesh),
        force(cut) { lod.force = cut; lod.frame = -1; },
        look(l = {}) { CU.set(l); },
        // (the second restart) N8AO's transparency pass draws each card's AO-only material (coatMaterial); false: the lit
        // material there, as before (the same frame either way; for timing and debugging; attachCoat's opts.aoMaterial)
        get aoMaterial() { return lod.aoMaterial; },
        set aoMaterial(v) { lod.aoMaterial = v !== false; },
        update() {
            // the wind's world direction in the creature's space
            api.group.updateWorldMatrix(true, false);
            api.group.getWorldQuaternion(q).invert();
            wv.copy(CU.windDir.value).applyQuaternion(q).normalize();
            CU.windLocal.value.copy(wv);
            // (round 2's integration) the furred skins take part in N8AO's transparency pass only while their AO-only
            // material can be drawn there and claims something; their material-less ancestors carry the flag too (the
            // vendored pass's traversal, below), once
            if (skinClaim) {
                // (and only while cards are drawn over the skin: a fin coat, or the ladder's far end, never pays the
                // skins' extra draw in that pass)
                const on = lod.aoMaterial && CU.layerAOClaim.value > 0 && CU.closeW.value > 0;
                for (const o of layered) o.userData.cannotReceiveAO = on && !!o.material?.coatAOMaterial;
                if (on && !skinAncestors) {
                    skinAncestors = true;
                    for (const o of layered) for (let p = o.parent; p; p = p.parent) if (!p.isMesh) p.userData.cannotReceiveAO = true;
                }
            }
            // (round 2) the AO opt-out needs the host's AO to honour it: the vendored N8AO renders the objects flagged
            // cannotReceiveAO in its transparency pass (their alpha lifts its AO there) only while transparencyAware is
            // on, which it turns on by itself only for a transparent material; so the coat asks for it, once, before a
            // frame (setting it mid-pass would rebuild N8AO's composite inside a render). And the vendored port's pass
            // sets visible = (transparent || cannotReceiveAO) on EVERY node it traverses, material or not (upstream
            // N8AO skips nodes without a material): the scene root and the creature's groups turn invisible and the pass
            // draws nothing at all (measured 10-30: the opt-out changed no pixel). Until that line is fixed in the
            // harness (staged: work/bestiary/coat/patches/n8ao_transparency_traversal.md), the coat's ancestors carry the flag too,
            // so they stay visible in that pass; a node without a material draws nothing itself, and every other mesh
            // keeps its own flag (the body under the coat still takes the AO)
            const n8 = globalThis._n8ao;
            if (!aoAsked && n8?.configuration && meshes.some((m) => m.userData.cannotReceiveAO)) {
                aoAsked = true;
                for (const m of meshes) {
                    if (!m.userData.cannotReceiveAO) continue;
                    for (let p = m.parent; p; p = p.parent) if (!p.isMesh) p.userData.cannotReceiveAO = true;
                }
                if (!n8.configuration.transparencyAware) {
                    n8.configuration.transparencyAware = true;
                    console.log('[coat] the cards opt out of the screen-space AO: N8AO transparencyAware on (cannotReceiveAO)');
                }
            }
        },
        // a rebuilt skin material (a remix) takes the layer again
        relayer(m) {
            const nm = String(m.name || '').replace(/_(bestiary|remix)$/, '');
            return coatSkinLayer(m, packTex[nm], CU, baseMaps[nm] || null, tipTex[nm] || null);
        },
        rebuild(o2 = {}) {
            // new materials (a remix: o2.remap, o2.display, o2.affix(m, ndv)); the uniforms and LOD stay
            for (const mesh of meshes) {
                const old = mesh.material;
                const { base, src: s, pack, attributes, tip } = mesh.userData.coatSources;
                const m = coatMaterial(base, s, mesh.geometry, U, CU, man, { ...opts, ...o2, pack, attributes, tip });
                coatPosition(m, mesh, CU, { ...opts, ...o2 });
                if (o2.affix) {
                    const e0 = m.emissiveNode;
                    o2.affix(m, coatNdv());
                    // (coat G6) A FIN'S SHARE OF A CREATURE-WIDE GLOW fades from its root to its tip (look.finAffixFade,
                    // fin coats). The glows that read the facing (rim_pulse's (1 - N.V)^power) take a fin's ROOT normal,
                    // edge-on to the view over the whole fin, so every fin glowed at the rim's peak from root to tip: in
                    // ringed, salmon lines round the eye and along every arm crossing the head (g6/look/rx2_hero_x3.png:
                    // gone with rim_pulse taken out of the block, there with the zones smoothed, so NOT the zone colour
                    // the G5 integrator read). Faded along the fin, the skin's rim carries on outward as a halo that dies
                    // over the pile's height, as a rim does through a fringe
                    if (CU.look.finOnly > 0 && CU.look.finAffixFade > 0 && m.emissiveNode && m.emissiveNode !== e0) {
                        const add = e0 ? m.emissiveNode.sub(e0) : m.emissiveNode;
                        const fade = THREE.float(1).sub(THREE.smoothstep(0.0, 1.0, m.coatNodes.h).mul(CU.finAffixFade));
                        m.emissiveNode = e0 ? e0.add(add.mul(fade)) : add.mul(fade);
                    }
                }
                mesh.material = m;
                old.dispose?.();
            }
            // the shells too (when built): the same remap and affixes, so a recolour reaches the close-up layer
            for (const sm of ctl.shells?.meshes || []) {
                const S = sm.userData.coatShellSources;
                const old = sm.material;
                const m = shellMaterial(S.base, S.tex, S.pack, U, CU, S.spec, S.upt, { ...opts, ...o2 });
                if (o2.affix) o2.affix(m, coatNdv());
                sm.material = m;
                old.dispose?.();
            }
        },
        dispose() {
            for (const m of meshes) { m.parent?.remove(m); m.material?.dispose?.(); }
        },
    };
    // the SHELLS, on request, when the forge's manifest carries a shell spec (a short coat's close-up layer: opts.shells
    // true, or { force, layers, from } for their gate). Not by default: x8 took the velvet octopus's frame at 0.6 m from
    // 0.61 to 1.60 ms (1080p, 10-29), where the skin layer alone carries the velvet for +0.03 ms or less
    if (man.shells && opts.shells && man.shells.tile !== undefined) {
        try {
            const tile = await packTexture(coatGltf, man.shells.tile, THREE.RepeatWrapping);
            ctl.shells = await coatShells(api, ctl, tile, { ...(typeof opts.shells === 'object' ? opts.shells : {}),
                remap: opts.remap, display: opts.display, groundOcclusion: opts.groundOcclusion });
        } catch (e) { report.push(`shells: ${e.message}`); }
    }
    ctl.update();
    if (opts.auto !== false) (globalThis._autoCreatures || (globalThis._autoCreatures = [])).push(() => ctl.update());
    for (const r of report) console.warn(`[coat] ${r}`);
    const tris = meshes.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : 0), 0);
    console.log(`[coat] ${man.style || 'coat'}: ${meshes.length} primitives, ${(man.primitives || []).reduce((s, p) => s + (p.cards || 0), 0)} cards, ${tris} triangles, ${man.ranks || 1} ranks; skin layer on ${layered.length} meshes` +
        ` (packs: ${Object.entries(packTex).map(([k, t]) => `${k} ${t.image?.width}x${t.image?.height}${t.isDataTexture ? ' data' : ' bitmap'}`).join(', ') || 'none'})` +
        ` (tip packs: ${Object.entries(tipTex).map(([k, t]) => `${k} ${t.image?.width}x${t.image?.height}`).join(', ') || 'none'}; tipMix ${CU.look.tipMix})`);
    return ctl;
}
