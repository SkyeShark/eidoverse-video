// species.js (A1, the runtime spine; ROADMAP §3 A1 and §6 decision 5): THE SPECIES TABLE AS A MANIFEST. Each forge glb already
// carries its body plan in extras.bestiary (species, family, units, up, forward, life_scale, chains: every limb / tentacle / tail
// chain's joints, side, label and tip socket; the stand, the rig's records), so the runtime reads WHAT a creature is from its glb:
//   manifestOf(gltf, row) -> { species, family, motion (the locomotion case), lifeScale, materials, chains, sockets, seats, gait,
//                             body, swim, ... }
// and keeps here only WHERE each known glb lives and the tuned numbers the rig rounds gated before the glbs carried them (the
// rows below, moved verbatim from bestiary.js's SPECIES: data, not code). A glb's own extras.bestiary.motion ({ case, walk, swim,
// talk, idles }) overrides a row's numbers (axolotl.js already reads its walk / swim from there), so a rig round that re-tunes the
// motion writes the glb, not this file.
//
// A NEW BASE IS A GLB, NOT A CODE EDIT:
//   const hawk = await Bestiary.create({ path: 'work/bestiary/hawk/out/hawk_rig.glb' });       // the glb says it all, or
//   Bestiary.register('hawk', { path: 'work/bestiary/hawk/out/hawk_rig.glb' });                // a name for create({ species })
// its locomotion case from its manifest (motion.case, else the family and chains: radial -> 'radial'; arthropod on six legs ->
// 'hexapod'; a sprawl body plan with the salamander's rows -> 'salamander'; hominid -> 'limbed' (the biped; the VRM path is B1's);
// any other base standing on leg chains -> 'limbed' over its support slots), its materials from its materials' extras keys.
//
// THE ROWS (the tuned numbers per known glb; comments as they stood in bestiary.js):
//   octopus      body: the forge SPEC values the motion needs (species/octopus.py: arm radius at the crown and at the tip)
//   stag_beetle  (B11) BEETLE_PLAN §6.4-§6.6, B10's glb: one skinned mesh on the 104-joint skeleton, typed sockets, the hat and glasses
//                seats; authored at x10, so `lifeScale` 0.1 is its real size (create({ size: 'hero' }) keeps the authored x10). Its
//                materials by the extras key (beetle_cuticle.js), its motion the HEXAPOD gait (locomotion.js hexapodMotion): duty 0.65
//                at the usual walk (§6.4: 0.6-0.75); the stride 17 mm at life (0.17 authored), the step rate 1-3 Hz (fMin, fMax); the
//                hind and fore pairs' stance centred at 0.65 of it (b10/h11 + g01, h13_legclear); lift 2.4 mm. The VARIANTS built on it
//                (work/bestiary/beetle/variants, rigged by B10's r01_rig.py): create({ variant }), each its own glb; ice refracts
//   axolotl      (AX12) AXOLOTL_PLAN §9.3, §10, §11's AX12 row: AX11's glb at x4, lifeScale 0.25; body: the SPEC's numbers the motion
//                reads; gait: species/axolotl_rig.py's WALK (0.08 TL/s, stride 0.18 TL, duty fore 0.36 and hind 0.51 after Gamel
//                2024, the lateral sequence's phases, lift 2.2 / 2.6 life mm, sway 4 deg, jitter 0.03) and the runtime's own
//                (accel, v_settle, pivot, hinge); swim: the SPEC's motion rows and AX13's ADPRESS (runtime/axolotl.js)
export const SPECIES = {
    octopus: { path: 'work/bestiary/octopus/octopus.glb', asset: 'octopus', motion: 'radial',
        body: { armR0: 0.026, armTipR: 0.0011 } },
    stag_beetle: { path: 'work/bestiary/beetle/out_b58/stag_beetle_rig.glb', asset: 'stag_beetle', motion: 'hexapod',
        materials: 'beetle', lifeScale: 0.1,
        gait: { duty: 0.65, stride: 0.17, fMin: 1.0, fMax: 3.0, lift: 0.024, center: { f: 0.65, h: 0.65 } },
        variants: {
            crystal: { path: 'work/bestiary/beetle/variants/crystal/out/crystal_r3/stag_beetle_crystal_rig.glb',
                asset: 'stag_beetle_crystal' },
            ice: { path: 'work/bestiary/beetle/variants/crystal/out/ice_clear_r3/stag_beetle_crystal_rig.glb',
                asset: 'stag_beetle_ice', opts: { growTrans: 0.9, growIOR: 1.31 } },
            cyborg: { path: 'work/bestiary/beetle/variants/cyborg_stag_beetle_rig.glb', asset: 'stag_beetle_cyborg' },
            cyborg_crystal: { path: 'work/bestiary/beetle/variants/cyborg_crystal/cyborg_crystal_stag_beetle_rig.glb',
                asset: 'stag_beetle_cyborg_crystal' },
        } },
    axolotl: { path: 'work/bestiary/axolotl/ax11/axolotl.glb', asset: 'axolotl', motion: 'salamander',
        materials: 'axolotl', lifeScale: 0.25,
        body: { TL_mm: 241.6, k_mm: 0.004, s_hip: 0.465 },
        gait: { speed: 0.08, stride: 0.18, duty: [0.36, 0.51], phase: { hind_L: 0.0, fore_L: 0.25, hind_R: 0.5, fore_R: 0.75 },
            lift: [2.2, 2.6], yaw: 4.0, jitter: 0.03, accel: 0.12, v_settle: 1.0, pivot: 0.117,
            hinge: { fore: [60.0, 165.0], hind: [65.0, 165.0] } },
        swim: { wavelength: 0.60, amp: 0.097, stride: 0.345, above: 0.25, height: 0.04, blend: 0.6, accel: 0.8, hover: 0.0,
            neck_share: 0.5,
            adpress: { fore: [[0.65, -0.18, -1.0], [0.08, -0.50, -1.0], [0.10, -0.30, -1.0]],
                hind: [[0.42, -0.10, -1.0], [0.10, -0.45, -1.0], [0.30, -0.25, -1.0]] } } },
    // (A1) the human's glb (H4d, the canonical base) for the runtime's non-VRM path (the limbed biped case; B1 builds the VRM path)
    human: { path: 'work/bestiary/human/h4d/build/glb/human_F.glb', asset: 'human_F',
        variants: { M: { path: 'work/bestiary/human/h4d/build/glb/human_M.glb', asset: 'human_M' } } },
};
// the remix's base name for it (remix/recipe.py SPECIES['beetle']: remix.js create() builds block.base)
SPECIES.beetle = SPECIES.stag_beetle;

// a new base by name (its glb's path or ASSETS key; the rest comes from the glb)
export function registerSpecies(name, row) {
    if (!row || (!row.path && !row.asset && !row.bytes)) throw new Error(`[Bestiary] register('${name}'): give a path, asset or bytes`);
    SPECIES[name] = { ...row };
    return SPECIES[name];
}

// the glb's own record (extras.bestiary: the root's extras; the beetle's later rounds nest a manifest block too)
export function extrasOf(gltf) {
    const ex = gltf?.userData?.bestiary || gltf?.parser?.json?.extras?.bestiary || {};
    return ex;
}

// THE LOCOMOTION CASE from the record: an explicit motion.case, else the family and the chains
export function motionCase(ex) {
    if (ex.motion?.case) return ex.motion.case;
    const fam = ex.family || ex.manifest?.family;
    const chains = ex.chains || [];
    const legs = chains.filter((c) => /^leg/.test(c.kind)).length;
    if (fam === 'radial') return 'radial';
    if (fam === 'arthropod' && legs === 6) return 'hexapod';
    if (legs === 6 && chains.some((c) => c.kind === 'leg' && /^coxa_/.test(c.joints?.[0] || ''))) return 'hexapod';
    if (ex.body_plan === 'sprawl' && ex.species === 'axolotl') return 'salamander';
    if (legs >= 2) return 'limbed';
    return 'none';
}

// the materials' family from their extras keys (bestiary.js routes by these)
export function materialsOf(gltf) {
    const ms = gltf?.parser?.json?.materials || [];
    if (ms.some((m) => ['cuticle', 'compound_eye', 'membrane'].includes(m.extras?.bestiary))) return 'beetle';
    if (ms.some((m) => m.extras?.recipe === 'axolotl')) return 'axolotl';
    if (ms.some((m) => String(m.extras?.bestiary || '').startsWith('human_'))) return 'human';
    return null;
}

// THE MANIFEST: the glb's record under the row's tuned numbers (the row wins where it has a key: the gated numbers), the glb's
// motion block over both
export function manifestOf(gltf, row = {}, name = null) {
    const ex = extrasOf(gltf);
    const M = ex.motion || {};
    const sockets = [], seats = [];
    gltf.scene?.traverse?.((o) => {
        if (o.name?.startsWith('socket_')) sockets.push(o.name);
        if (o.name?.startsWith('seat_')) seats.push(o.name);
    });
    const sp = {
        species: name || ex.species || ex.manifest?.species || 'creature',
        family: ex.family || ex.manifest?.family || null,
        motion: motionCase(ex),
        lifeScale: ex.life_scale ?? 1.0,
        materials: materialsOf(gltf),
        chains: ex.chains || [],
        sockets, seats,
        ...row,
    };
    if (M.walk) sp.gait = { ...(sp.gait || {}), ...M.walk };
    if (M.swim) sp.swim = { ...(sp.swim || {}), ...M.swim };
    if (M.talk) sp.talk = { ...(sp.talk || {}), ...M.talk };
    if (M.idles) sp.idles = { ...(sp.idles || {}), ...M.idles };
    return sp;
}
