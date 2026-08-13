// SHALLOW-WATER HEIGHTFIELD LIQUID — the realtime bulk-water system.
//
// Architecture (Müller/Chentanez heightfield-water family): the pool is a
// 2D column field — water DEPTH h over a static bed b — stepped with the
// shallow water equations in FLUX FORM, so mass is conserved EXACTLY by
// construction: a basin filling from emitters cannot lose volume, ever.
// Foam lives in an advected 2D map fed by the quantities the sim already
// knows (divergence churn, crest steepness, shorelines, collider wakes).
// The surface renders as a DISPLACED GRID MESH — smooth by construction,
// no raymarch, no iso-contour, no torn edges — wearing the same shading
// language the 3D water tuned (depth tint, fresnel, key spec, glow, foam).
//
// This is v1 of the hybrid plan (2026-07-28, Skye + Fable): v2 adds a small
// mass-conserving particle layer promoted where the heightfield assumption
// breaks (jets, crest collapse, breach spray) and demoted back on landing.
//
// What a heightfield CANNOT do: overhangs, curling breakers, submersion
// interiors. Those stay fluid_water.js's (or v2's) job.
//
// ⚠ STACK LAWS INHERITED FROM fluid_water.js — do not innovate here:
//   • rgba16float Storage3DTexture (depth-1 for 2D fields) — the r184-proven
//     recipe; StorageTexture-2D is UNPROVEN on this stack, don't pioneer it.
//   • ONE textureStore per kernel. Multi-write kernels silently no-op.
//   • writes into texture OBJECTS via explicit AB/BA kernel pairs; reads via
//     texture3D(obj, uvw, 0). A swapping node is a silent no-op.
//   • explicit .level(0) on every sample — REQUIRED in vertex stage anyway.
//
// ⚠ CFL: explicit SWE needs dt ≤ dx / (|u|max + √(g·hmax)). We substep to
// keep it; velocities are clamped to o.maxSpeed as the backstop.
//
// Usage:
//   const swe = await createWaterSWE(renderer, { worldSize:[10.8,10.8], ... });
//   scene.add(swe.surfaceMesh);
//   swe.setEmitters([{x,z,rate,vx,vz,foam}]);       // rate in m³/s
//   swe.setSpheres([{x,y,z,r,vx,vz}]);              // character coupling
//   await swe.step(dt);                             // per frame
//   swe.bedFromHeightFn((x,z)=>y, opts) at init via o.bedFn — bed in WORLD y.

import * as THREE from 'three/webgpu';
import {
    vec2, vec3, vec4, float, Fn, uniform, uniformArray, uvec3, int, ivec3,
    texture3D, textureStore, textureLoad, instanceIndex, vertexIndex, storage, atomicAdd,
    smoothstep, mix, min, max, abs, floor, fract, clamp, normalize, dot,
    reflect, pow, exp, If, Loop, Break, length, sign, hash, cross,
    positionLocal, positionWorld, cameraPosition, cameraViewMatrix, uv, atan,
    texture, equirectUV, transformNormalToView,
} from 'three/tsl';

// ── LIQUID PRESETS — the eidoverse contract: complicated behaviour as one
// API word. createWaterSWE(renderer, { preset: 'gel', ... }) — any option
// still overrides. Sim knobs each preset drives:
//   yieldSlope  Bingham-style yield: below this surface gradient the liquid
//               does NOT flow — gels HOLD mounds instead of levelling.
//   waveScale   scales gravity's pull on the surface (slow gloopy response
//               vs snappy water waves) — the honest SWE stand-in for
//               viscosity's sluggishness.
//   sprayStretch  how needle-like airborne droplets stretch (gel blobs ~0.3).
//   specPow/specGain  highlight tightness/strength (gel = tight and glossy).
export const LIQUID_PRESETS = {
    water: {},
    gel: {          // firm translucent gel: holds mounds, tight gloss
        yieldSlope: 0.22, waveScale: 0.32,
        bedFriction: 0.4, drag: 0.12, maxSpeed: 2.5,
        rippleAmp: 0.005, rippleSpeed: 0.35, flowT: 2.4,
        surfaceOpacity: 0.97, absorption: 4.5,
        specPow: 260, specGain: 1.7,
        foamDecay: 0.8, shoreFade: 0.05,
        sprayStretch: 0.3, spraySize: 0.06,
        streamAeration: 0.12, dropletVisibility: 0.4, foamGain: 0.22,   // ropey unbroken filaments
        promoTaMin: 0.9, promoCrestMin: 5.0,   // gel resists aeration
    },
    goo: {          // slow-flowing heavy goo: creeps, blobs, sticky froth
        yieldSlope: 0.09, waveScale: 0.45,
        bedFriction: 0.25, drag: 0.08, maxSpeed: 3.0,
        rippleAmp: 0.007, rippleSpeed: 0.45, flowT: 2.0,
        surfaceOpacity: 0.95, absorption: 3.6,
        specPow: 180, specGain: 1.4,
        foamDecay: 1.0, shoreFade: 0.04,
        sprayStretch: 0.45, spraySize: 0.065,
        streamAeration: 0.2, dropletVisibility: 0.5, foamGain: 0.35,
    },
    lava: {         // creeping incandescent flow, crusting froth
        yieldSlope: 0.3, waveScale: 0.18,
        bedFriction: 0.55, drag: 0.16, maxSpeed: 1.6,
        rippleAmp: 0.004, rippleSpeed: 0.2, flowT: 3.2,
        surfaceOpacity: 1.0, absorption: 6.0,
        specPow: 40, specGain: 0.35,
        emissiveStrength: 1.4, emissiveFalloff: 2.2,
        foamDecay: 0.5, shoreFade: 0.06,
        sprayStretch: 0.5, promoRate: 1.2,
        streamAeration: 0.1, dropletVisibility: 0.35, foamGain: 0.3,
    },
    mud: {          // opaque sluggish slurry, matte
        yieldSlope: 0.14, waveScale: 0.4,
        bedFriction: 0.35, drag: 0.1, maxSpeed: 2.2,
        rippleAmp: 0.006, rippleSpeed: 0.3, flowT: 2.6,
        surfaceOpacity: 1.0, absorption: 7.0,
        specPow: 18, specGain: 0.25,
        foamDecay: 1.2, shoreFade: 0.05,
        sprayStretch: 0.5,
        streamAeration: 0.15, dropletVisibility: 0.4, foamGain: 0.5, 
    },
};

const DEFAULTS = {
    preset: 'water',              // one word picks a LIQUID_PRESETS bundle
    worldSize: [10.8, 10.8],      // metres, x/z extent of the domain
    gridSize: [256, 256],
    domainCenter: [0, 0, 0],      // world position of the domain's centre
    bedFn: null,                  // (x,z)->world y of the bed. REQUIRED.
    bedYMin: -2.6,                // world y treated as "deep floor" reference
    gravity: 9.8,
    yieldSlope: 0.0,              // Bingham yield: |∇η| below this → no flow
    waveScale: 1.0,               // surface-gravity response (viscous feel < 1)
    specPow: 90, specGain: 0.9,   // highlight tightness / strength
    sprayStretch: 1.0,            // droplet velocity-stretch factor
    momentumTransfer: 0.25,       // fraction of a landing's momentum that
                                  // becomes lateral surface current — the
                                  // rest dissipates as subsurface turbulence.
                                  // At 1.0 every pour lands like a firehose:
                                  // the consumption clamp becomes the
                                  // OPERATING POINT (hurricane forcing).
    streamAeration: 1.0,          // white breakup on falling streams (honey ~0)
    dropletVisibility: 1.0,       // spray alpha scale (viscous liquids stay ropey;
                                  // the mass ledger is untouched — style only)
    foamGain: 1.0,                // scales ALL foam generation — gel barely
                                  // foams; its landings must not go cream-white
    maxSpeed: 6.0,                // m/s clamp — the CFL backstop
    maxDepth: 4.0,                // clamp h; a basin never legitimately exceeds it
    substeps: 3,                  // substeps per 1/60 s of SIM time (dtSub = fixedStep/substeps)
    maxSubSteps: 12,              // accumulator cap — a hitch never spirals
    fixedStep: 1 / 60,            // seconds of sim time per step() call
    drag: 0.015,                  // bulk momentum damping per second (calm settle)
    bedFriction: 0.06,            // Manning-style k in v *= 1/(1 + k·|v|·dt/h)
    // ⚠ DEPRECATED chop (sim-domain agitation): forcing near-grid
    // wavelengths through the nonlinear SWE reads as FERROFLUID (Skye).
    // The paper's way (hfFluid §2.4/§2.5): sub-grid waves are a RENDER-TIME
    // displacement + normal layer, activity-gated. That is rippleAmp below.
    chop: 0.0,                    // leave 0; kept only for A/B archaeology
    rippleAmp: 0.014,             // render-domain detail wave height, metres
    rippleScale: 9.0,             // ripples per metre-ish (wavelength ~0.3 m)
    rippleSpeed: 0.9,
    // ── HYDRAULIC EROSION (opt-in: pass {} or overrides; null = off, nothing
    // built). The bed becomes DYNAMIC: flowing water carves it where the
    // current is fast, carries the spoil as suspended sediment (the water
    // visibly muddies), and lays it down where the flow slackens — gullies
    // deepen upstream, deltas fan out downstream, and steep cut banks CAVE
    // to the angle of repose. Ships its own eroding terrain-patch mesh
    // (swe.terrainMesh) displaced from the live bed — give it the scene's
    // PBR set via terrainMaps and lay it over the static terrain.
    erosion: null,                // {capacity, erode, deposit, talusSlope,
                                  //  talusRate, maxDelta, siltColor, cutColor,
                                  //  terrain, terrainMaps, terrainRepeat, ...}
    // ── RAIN — distributed mass over the whole domain (m of depth per
    // second; 4.5e-5 ≈ a violent 160 mm/h cloudburst). THE natural source
    // for wash/gully erosion: sheetwash gathers into rills, rills capture
    // each other, a channel wins. Patchiness animates slow squall bands
    // sweeping the domain instead of a uniform drizzle. Pair the look with
    // makeWeatherSystem's falling rain — this term is where its water LANDS.
    rainRate: 0,
    rainPatchiness: 0.6,
    // SPRAY (v2.0): ballistic white-water particles — visible falling jets
    // from spout mouths and burst spray on hard breaches. VISUAL layer: the
    // pours' mass still flows through the conserving emitter path (aerated
    // spray is mostly air); v2.1 adds fixed-point-atomic mass deposit.
    sprayMax: 0,                  // particle budget; 0 = spray off, nothing built
    spraySize: 0.055,             // sprite radius, metres
    sprayJetSpread: 0.06,         // mouth jitter, metres
    // ── THE EXCHANGE (hfFluid core): particles CARRY volume. Pours deliver
    // all their mass as droplets that deposit volume+momentum+foam where
    // they land (fixed-point atomics); the field PROMOTES fast/steep cells
    // into spray (withdrawing the volume), so breach collars and breaking
    // crests spawn from the WATER STATE, not from parametric effects.
    pourVol: 3.0e-4,              // m3 carried per pour droplet
    promoVol: 1.5e-4,             // m3 withdrawn per promoted droplet
    // ── PROMOTION POTENTIALS (Ihmsen et al. 2012, adapted to a heightfield).
    // ⚠ binary gates on absolute speed + steepness are wrong by construction:
    // absolute speed saturates in a shallow filling pool and is BLIND to
    // impacts. Ihmsen: soft ramps PHI(I,min,max)→[0,1], count = Ik·(kta·Ita
    // + kwc·Iwc). Ita = CONVERGING relative velocity (the impact detector —
    // a breach collar is water masses colliding); Iwc = convex curvature ×
    // rising surface; Ik = kinetic energy (incl. VERTICAL dh/dt) multiplies.
    promoTaMin: 0.5, promoTaMax: 2.5,     // trapped-air ramp: Σ converging Δv, m/s
    promoCrestMin: 3.0, promoCrestMax: 14.0, // crest ramp: −∇²η, 1/m (fp16 noise floor ~1)
    promoEnMin: 0.10, promoEnMax: 1.5,    // energy ramp: |v|²+½(dh/dt)², m²/s²
                                          // (basin regime ~0.3–1; debug view
                                          // showed 0.25/4.0 dimming the collar
                                          // to Ik≈0.1 while crest+air lit up)
    promoKta: 0.7, promoKwc: 0.6,         // class weights inside the sum
    promoRate: 2.5,               // global spawn-probability scale — polls are
                                  // sparse (dead slots × bias × in-band), so
                                  // >1 lets hot cells actually saturate
    promoVy: 0.45,                // vertical kick as fraction of field speed
    flowT: 1.4,                   // flowmap phase period for detail ripples
    chopScale: 55.0,              // noise frequency in uvw units (~3-cell waves)
    chopSpeed: 2.6,               // agitation animation rate
    dryEps: 0.004,                // below this depth a column is "dry"
    initLevel: null,              // world y: start pre-filled to this waterline
                                  // (null = start empty; scenes with standing
                                  // ponds shouldn't spend runtime filling)
    // emitters: up to 4, set via setEmitters — {x,z,rate m³/s,vx,vz,foam 0..1}
    // spheres: up to 12 character-coupling spheres via setSpheres
    // foam
    foamDecay: 1.5,               // fraction lost per second
    foamChurn: 0.55,              // deposit gain from thresholded |divergence|
    foamCrest: 0.7,               // deposit gain from steepness
    foamWake: 1.5,                // deposit gain inside collider stamps
    // rendering
    envTex: null,                 // equirect sky texture (e.g. sky.bakeEnv's
                                  // target). The fresnel term reflects THIS
                                  // along the reflected ray; without it, the
                                  // constant skyColor paints a grazing-angle
                                  // pond as one flat milky sheet.
    deepColor: '#06283d',
    shallowColor: '#2f8f9d',
    skyColor: '#9db8c9',
    absorption: 2.2,              // 1/m of DEPTH
    surfaceOpacity: 0.9,
    keyLightDir: [0.4, 0.8, 0.45],
    emissiveColor: '#2ffbe0',
    emissiveStrength: 0.0,        // 0 = ordinary water
    emissiveFalloff: 3.8,
    foamColor: '#eefaf6',
    foamStrength: 1.0,
    // foam COVERAGE erosion (SoT/Crest mechanism, tuned realistic): the foam
    // value drives coverage through a flow-advected noise threshold — dense
    // foam reads solid, decaying foam goes lacy, nothing is a flat white
    // sheet. Two octaves: patch structure + fine lace.
    foamTexScale: 5.5,            // patch noise frequency, 1/m
    shoreFade: 0.03,              // metres of depth over which the edge fades in
};

export async function createWaterSWE(renderer, options = {}) {
    const presetName = options.preset ?? DEFAULTS.preset;
    const preset = LIQUID_PRESETS[presetName];
    if (!preset) throw new Error(`[swe] unknown liquid preset "${presetName}" — have: ${Object.keys(LIQUID_PRESETS).join(', ')}`);
    const o = { ...DEFAULTS, ...preset, ...options };
    const [NX, NZ] = o.gridSize;
    const CELLS = NX * NZ;
    const [WX, WZ] = o.worldSize;
    const DX = WX / NX, DZ = WZ / NZ;
    if (Math.abs(DX - DZ) > 1e-6) {
        console.warn('[swe] ⚠ non-square cells (' + DX.toFixed(4) + ' vs '
            + DZ.toFixed(4) + ') — flux form assumes square; keep them equal.');
    }
    if (!o.bedFn) throw new Error('[swe] bedFn(x,z)->worldY is required');
    const center = new THREE.Vector3(...o.domainCenter);

    // ── uniforms ──────────────────────────────────────────────────────────
    const NEMI = 4, NSPH = 12;
    const U = {
        dt: uniform(o.fixedStep / o.substeps),
        time: uniform(0),
        consume: uniform(0),
        // emitters: pos.xy = cell-space x/z, pos.z = rate (m³/s); vel.xy, vel.z = foam
        emiPos: uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector3(0, 0, 0))),
        emiVel: uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector3(0, 0, 0))),
        // spheres: pos = world x,y,z; aux = r, vx, vz; aux2.x = vy (a plunging
        // body's DOWNWARD speed is the entry-splash driver — dropping it made
        // ball entry read as a gentle set-down, never a crown)
        sphPos: uniformArray(Array.from({ length: NSPH }, () => new THREE.Vector3(0, -99, 0))),
        sphAux: uniformArray(Array.from({ length: NSPH }, () => new THREE.Vector3(0, 0, 0))),
        sphAux2: uniformArray(Array.from({ length: NSPH }, () => new THREE.Vector3(0, 0, 0))),
        deepColor: uniform(new THREE.Color(o.deepColor)),
        shallowColor: uniform(new THREE.Color(o.shallowColor)),
        skyColor: uniform(new THREE.Color(o.skyColor)),
        absorption: uniform(o.absorption),
        surfaceOpacity: uniform(o.surfaceOpacity),
        keyLightDir: uniform(new THREE.Vector3(...o.keyLightDir).normalize()),
        emissiveColor: uniform(new THREE.Color(o.emissiveColor)),
        emissiveStrength: uniform(o.emissiveStrength),
        emissiveFalloff: uniform(o.emissiveFalloff),
        foamColor: uniform(new THREE.Color(o.foamColor)),
        foamStrength: uniform(o.foamStrength),
        rain: uniform(o.rainRate),
    };

    // ── storage (depth-1 3D textures; the proven recipe) ──────────────────
    const mk = (name) => {
        const t = new THREE.Storage3DTexture(NX, 1, NZ);
        t.name = name;
        t.format = THREE.RGBAFormat;
        t.type = THREE.HalfFloatType;
        t.minFilter = THREE.LinearFilter;
        t.magFilter = THREE.LinearFilter;
        t.wrapS = t.wrapT = t.wrapR = THREE.ClampToEdgeWrapping;
        return t;
    };
    const hA = mk('sweHA'), hB = mk('sweHB');        // r = depth h (m)
    const velA = mk('sweVelA'), velB = mk('sweVelB');// rg = u,w (m/s)
    const fluxT = mk('sweFlux');                     // rg = face fluxes Fx,Fz
    const foamA = mk('sweFoamA'), foamB = mk('sweFoamB'); // r = foam 0..1
    // detail-ripple HEIGHT (metres) — a PER-FRAME field evaluation, fully
    // realtime (recomputed each frame from the live velocity/height state;
    // nothing precomputed). ⚠ the fragment used to evaluate the ripple
    // noise stack PER PIXEL (~32 noise calls/px); the 256² grid can't hold
    // more detail than 65k values, so evaluating per-cell-per-frame and
    // interpolating is the same image at ~3% of the arithmetic — the
    // standard realtime-ocean pattern (FFT seas do exactly this).
    const rippleT = mk('sweRipple');

    // ── indexing ──────────────────────────────────────────────────────────
    const cellOf = (id) => uvec3(id.mod(NX), id.mul(0), id.div(NX));
    const uvwOf = (c) => vec3(c).add(0.5).div(vec3(NX, 1, NZ));
    const duv = vec3(1 / NX, 0, 0), dwv = vec3(0, 0, 1 / NZ);
    // cell centre in world xz
    const worldXZ = (c) => uvwOf(c).xz.sub(0.5).mul(vec2(WX, WZ))
        .add(vec2(center.x, center.z));

    const R = (tex, p) => texture3D(tex, p, 0);

    // ── bed: CPU-baked at BUILD time (allowed) ────────────────────────────
    // CPU-baked bed as a regular Data3DTexture (read-only in kernels) — the
    // exact pattern fluid_water uses for solidTex.
    const bedData = new Float32Array(NX * NZ);
    let bedMin = Infinity, bedMax = -Infinity;
    for (let k = 0; k < NZ; k++) for (let i = 0; i < NX; i++) {
        const wx = (i + 0.5) / NX * WX - WX / 2 + center.x;
        const wz = (k + 0.5) / NZ * WZ - WZ / 2 + center.z;
        const y = o.bedFn(wx, wz);
        bedData[k * NX + i] = y;
        if (y < bedMin) bedMin = y; if (y > bedMax) bedMax = y;
    }
    // ⚠ HALF-float, not float32: binding a float32 texture to a FILTERING
    // sampler needs the 'float32-filterable' feature, which this stack does
    // not grant — the fragment module comes back "invalid" and the mesh
    // silently never draws. rgba16float storage textures filter fine in
    // core, and so does a half-float data texture. fp16's ~1 mm precision
    // over a ±2.6 m bed is far below anything the eye meets.
    const bedTex = new THREE.Data3DTexture(
        (() => {
            const f = new Uint16Array(NX * 1 * NZ);
            for (let i = 0; i < bedData.length; i++) f[i] = THREE.DataUtils.toHalfFloat(bedData[i]);
            return f;
        })(),
        NX, 1, NZ);
    bedTex.format = THREE.RedFormat;
    bedTex.type = THREE.HalfFloatType;
    bedTex.minFilter = THREE.LinearFilter;
    bedTex.magFilter = THREE.LinearFilter;
    bedTex.wrapS = bedTex.wrapT = bedTex.wrapR = THREE.ClampToEdgeWrapping;
    bedTex.needsUpdate = true;
    console.log('[swe] bed baked: y ' + bedMin.toFixed(2) + '..' + bedMax.toFixed(2)
        + ' over ' + NX + 'x' + NZ + ' (' + DX.toFixed(3) + ' m cells)');

    const bed = (p) => texture3D(bedTex, p, 0).r;

    // ── EROSION state: ONE extra ping-pong pair. R = bed DELTA in metres
    // (negative = carved, positive = deposited), G = suspended sediment
    // (column-metres, advected with the flow), B = fresh-silt age 0..1
    // (drives the wet-silt tint on the terrain), A unused. The original
    // bedTex stays pristine — the live bed is bedTex + delta, so erosion
    // can never corrupt the baked terrain reference.
    const ERO = !!o.erosion;
    const EK = ERO ? {
        capacity: 0.5,      // sediment capacity ∝ speed·depth (Kc)
        erode: 0.55,        // pickup rate toward capacity (Ks, 1/s)
        deposit: 0.35,      // settling rate above capacity (Kd, 1/s)
        bank: 1.0,          // LATERAL pickup: flow eats its banks sideways —
                            // without it every channel incises a narrow slot
                            // (depth was the only degree of freedom)
        minDepth: 0.004,    // films thinner than this don't erode
        talusSlope: 0.55,   // angle of repose as rise/run (0.55 ≈ 29° wet sand;
                            // 1.0 ≈ 45° holds slot walls up — desert alluvium
                            // slumps far flatter)
        talusRate: 2.2,     // relaxation speed of over-steep banks
        maxDelta: 0.9,      // cut/fill depth clamp, metres
        siltColor: '#96754e',      // fresh wet deposit tint (terrain)
        cutColor: '#6b4f33',       // exposed cut-bank earth tint (terrain)
        siltWaterColor: '#8a6b42', // suspended-load water tint
        wetDarken: 0.4,     // wet-ground darkening under standing water
        terrain: true,      // build the eroding terrain-patch mesh
        terrainMaps: null,  // { albedo, normal, rough } textures (scene loads)
        terrainRepeat: 7,   // uv repeats of the maps across the domain
        ...o.erosion,
    } : null;
    const dBedA = ERO ? mk('sweDBedA') : null, dBedB = ERO ? mk('sweDBedB') : null;
    // per-phase live bed for the AB/BA kernel factories
    const bedOf = (dSrc) => ERO ? ((p) => bed(p).add(R(dSrc, p).r)) : bed;
    // frame-level (phase-mixed) delta/sediment reads — phaseU is set before
    // any frame-level kernel or material samples these
    const EU = ERO ? {
        siltColor: uniform(new THREE.Color(EK.siltColor)),
        cutColor: uniform(new THREE.Color(EK.cutColor)),
        siltWaterColor: uniform(new THREE.Color(EK.siltWaterColor)),
    } : null;

    // zero-init the dynamic fields
    const mkInit = (dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        textureStore(dst, c, vec4(0, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    // height init honours initLevel: h0 = max(0, level − bed)
    const mkInitH = (dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const h0 = o.initLevel === null ? float(0)
            : max(float(o.initLevel).sub(texture3D(bedTex, uvwOf(c), 0).r), 0.0);
        textureStore(dst, c, vec4(h0, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kInitH_A = mkInitH(hA, 'sweInitHA'), kInitH_B = mkInitH(hB, 'sweInitHB');
    const kInitV_A = mkInit(velA, 'sweInitVA'), kInitV_B = mkInit(velB, 'sweInitVB');
    const kInitF_A = mkInit(foamA, 'sweInitFA'), kInitF_B = mkInit(foamB, 'sweInitFB');

    // ── shared procedural noise (render detail + optional legacy chop) ──
    const vnoise = (q) => {
        const iq2 = floor(q), fq = fract(q);
        const u2 = fq.mul(fq).mul(fq).mul(
            fq.mul(fq.mul(6.0).sub(15.0)).add(10.0));      // quintic
        const hcorn = (ox, oz) => hash(iq2.x.add(ox).mul(157.31)
            .add(iq2.y.add(oz).mul(113.97)));
        return mix(
            mix(hcorn(0, 0), hcorn(1, 0), u2.x),
            mix(hcorn(0, 1), hcorn(1, 1), u2.x), u2.y);
    };
    const fbm2 = (q) => vnoise(q).add(vnoise(q.mul(2.13).add(7.7)).mul(0.5));
    // the detail-wave field (hfFluid: sub-grid waves live at RENDER time).
    // Two counter-scrolled layers so nothing repeats; centred on 0.
    const rippleField = (wx, wz, t) => {
        const rs = float(o.rippleScale);
        // ⚠ intrinsic drift must be PERCEPTIBLE: at scale 9, a 0.31 time
        // coefficient is a 3 cm/s pattern speed — Skye read it as frozen.
        // These give ~0.2 m/s baseline shimmer; flow advection (the flowmap
        // phases in the callers) dominates wherever the water actually moves.
        const q1 = vec2(wx, wz).mul(rs).add(vec2(t.mul(2.3), t.mul(1.4)));
        const q2 = vec2(wx, wz).mul(rs).mul(1.41).sub(vec2(t.mul(1.7), t.mul(2.6)));
        return fbm2(q1).add(fbm2(q2)).sub(1.5);            // ~[-1.5, 1.5]
    };

    // ── kernel builders (direction-paired) ────────────────────────────────
    // 1) velocity: semi-Lagrangian self-advection + gravity on the SURFACE
    //    gradient η = bed + h (water flows downhill off dry bumps correctly),
    //    sphere impulses, drag, dry/wall zeroing, clamp.
    const mkVel = (hSrc, vSrc, vDst, name, dBedSrc) => {
        const bedL = bedOf(dBedSrc);
        return Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const h = R(hSrc, p).r;
        // semi-Lagrangian back-trace in uvw
        const v0 = R(vSrc, p).rg;
        const back = p.sub(vec3(v0.x.mul(U.dt).div(WX), 0, v0.y.mul(U.dt).div(WZ)));
        const v = R(vSrc, back).rg.toVar();
        // surface-gradient gravity (central differences of η = bed + h);
        // bedL is the LIVE bed (bedTex + erosion delta) when erosion is on
        const ex1 = bedL(p.add(duv)).add(R(hSrc, p.add(duv)).r);
        const ex0 = bedL(p.sub(duv)).add(R(hSrc, p.sub(duv)).r);
        const ez1 = bedL(p.add(dwv)).add(R(hSrc, p.add(dwv)).r);
        const ez0 = bedL(p.sub(dwv)).add(R(hSrc, p.sub(dwv)).r);
        // waveScale slows the surface's pull (viscous sluggishness); the
        // Bingham yield gate stops flow entirely below yieldSlope — a gel
        // HOLDS its mounds instead of levelling like water
        const gx5 = ex1.sub(ex0).div(2 * DX);
        const gz5 = ez1.sub(ez0).div(2 * DZ);
        let gEff = float(o.gravity * o.waveScale);
        if (o.yieldSlope > 0) {
            gEff = gEff.mul(smoothstep(o.yieldSlope * 0.7, o.yieldSlope * 1.3,
                length(vec2(gx5, gz5))));
        }
        v.x.subAssign(gx5.mul(gEff).mul(U.dt));
        v.y.subAssign(gz5.mul(gEff).mul(U.dt));
        // exchange: landed droplets' momentum, consumed on the frame's first
        // substep (U.consume gates; kDepClear runs right after)
        If(U.consume.greaterThan(0.5).and(h.greaterThan(o.dryEps)), () => {
            const ci2 = vec3(c).z.toInt().mul(NX).add(vec3(c).x.toInt());
            const mAdd = vec2(
                float(depMxRd.element(ci2)).div(FXP),
                float(depMzRd.element(ci2)).div(FXP));
            const dv2 = mAdd.div(h.mul(DX * DZ).add(1e-4));
            // guard-level clamp: with momentumTransfer the typical impulse
            // sits well below it — it catches outliers, not every frame
            v.addAssign(clamp(dv2, vec2(-1.2, -1.2), vec2(1.2, 1.2)));
        });
        // spheres: radial shove + wake drag inside the stamp
        const w = worldXZ(c);
        for (let s = 0; s < NSPH; s++) {
            const sp = U.sphPos.element(int(s)), sa = U.sphAux.element(int(s));
            const d2 = w.sub(sp.xz);
            const dist = length(d2).max(1e-4);
            const surfY = bedL(p).add(h);
            const dy = sp.y.sub(surfY).abs();
            const inStamp = dist.lessThan(sa.x).and(dy.lessThan(sa.x.mul(1.4)))
                .and(h.greaterThan(o.dryEps));
            If(inStamp, () => {
                // plunge: a body entering at speed |vy| displaces volume at
                // ~π r²·|vy| — that flux leaves RADIALLY. Scaling the shove by
                // the downward speed is what makes an impact erupt a collar
                // while a floating body only dents the surface.
                // 0.35/plunge-unit (max ~3×): 0.9 drove single-cell pileups
                // that spiked the mesh into white shards at impact
                const plunge = max(U.sphAux2.element(int(s)).x.negate(), 0.0).min(6.0);
                const push = d2.div(dist).mul(sa.x.sub(dist).div(sa.x))
                    .mul(plunge.mul(0.35).add(1.0)).mul(2.2);
                v.x.addAssign(push.x.add(sa.y.mul(0.7)).mul(U.dt).mul(8));
                v.y.addAssign(push.y.add(sa.z.mul(0.7)).mul(U.dt).mul(8));
            });
        }
        // emitter impact momentum: a pour PLUNGES — its fall speed converts
        // to a radial current at the impact disc. Without this, mass arrives
        // inert, piles into a standing mound, and the pool goes glassy; with
        // it the pours drive continuous currents that keep the surface alive.
        if (globalThis.Deno?.env.get('SWE_NOEMOM') !== '1') for (let e3 = 0; e3 < NEMI; e3++) {
            const ep3 = U.emiPos.element(int(e3)), ev3 = U.emiVel.element(int(e3));
            const d3 = w.sub(ep3.xy);
            const dist3 = length(d3).max(1e-4);
            const rad3 = float(0.55);
            If(ep3.z.greaterThan(0.0).and(dist3.lessThan(rad3)).and(h.greaterThan(o.dryEps)), () => {
                const prox3 = rad3.sub(dist3).div(rad3);
                const dir3 = d3.div(dist3);
                v.x.addAssign(dir3.x.mul(3.4).add(ev3.x).mul(prox3).mul(U.dt).mul(10));
                v.y.addAssign(dir3.y.mul(3.4).add(ev3.y).mul(prox3).mul(U.dt).mul(10));
            });
        }
        // ── CHOP: activity-scaled small-wave agitation ────────────────────
        // SWE is non-dispersive and semi-Lagrangian advection eats every
        // wavelength under ~4 cells, so the pool carries only long slow
        // swells — which reads as SILICONE even when the bulk is right.
        // Inject gradient-of-noise velocity perturbations (2-4 cell
        // wavelength) scaled by local flow activity: they become real height
        // ripples that PROPAGATE through the sim, mass stays exact (velocity-
        // mediated), and a still pool stays still. ⚠ sin-hash args kept small.
        if (o.chop > 0) {
            // legacy sim-domain agitation — deprecated, see rippleAmp
            const cs = float(o.chopScale);
            const t1 = U.time.mul(o.chopSpeed);
            const field = (px, pz) => fbm2(vec2(px, pz).mul(cs).add(vec2(t1.mul(0.23), t1.mul(0.11))))
                .add(fbm2(vec2(px, pz).mul(cs).mul(1.37).sub(vec2(t1.mul(0.17), t1.mul(0.29)))));
            const e4 = float(0.006);
            const gx = field(p.x.add(e4), p.z).sub(field(p.x.sub(e4), p.z));
            const gz = field(p.x, p.z.add(e4)).sub(field(p.x, p.z.sub(e4)));
            const sp3 = length(v);
            const act = smoothstep(0.06, 0.5, sp3)
                .mul(float(1).sub(smoothstep(1.1, 2.2, sp3)))
                .mul(o.chop).mul(U.dt).mul(26.0);
            v.x.addAssign(gx.mul(act));
            v.y.addAssign(gz.mul(act));
        }
        // ── BED FRICTION (Manning-style): the canonical SWE term this build
        // was missing. Drag ~ |u|/h — huge for thin films, negligible for
        // deep water — which is precisely what stops wave runup from PINNING
        // as translucent curtains on the basin slope: thin sheets lose their
        // momentum and drain back instead of tenting the mesh. Replaces the
        // old depth-blind drag AND most of the dry-zeroing (which was itself
        // a pinning mechanism: a 3 mm film with v=0 just... stays).
        const sp0 = length(v);
        const fric = float(1).div(float(1).add(
            sp0.mul(float(o.bedFriction)).mul(U.dt).div(max(h, 0.008))));
        v.mulAssign(fric);
        v.mulAssign(float(1).sub(min(float(o.drag).mul(U.dt), 0.5)));
        If(h.lessThan(0.0006), () => { v.assign(vec2(0, 0)); });
        // clamp (CFL backstop)
        const sp2 = length(v).max(1e-5);
        v.mulAssign(min(float(o.maxSpeed), sp2).div(sp2));
        textureStore(vDst, c, vec4(v, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    };

    // 2) PER-CELL OUTFLOWS (pipe model, Chentanez) with PROPORTIONAL
    //    rescale. ⚠ the first cut capped each FACE at 1/4 column per substep
    //    — which back-computes to a hard 0.25·dx/dt ≈ 1.9 m/s speed limit on
    //    ALL flow. Gravity waves here want 3-4 m/s, so water piled into
    //    meringue mounds that oozed instead of levelling: the limiter WAS
    //    the "thick foam" look. Rescaling the SUM only when it would
    //    overdraw the column removes the speed cap while keeping h >= 0
    //    exact. Layout: r,g,b,a = outflow through +x, -x, +z, -z (m²/s).
    const mkFlux = (hSrc, vSrc, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const h = R(hSrc, p).r;
        const uC = R(vSrc, p).r, wC = R(vSrc, p).g;
        const uXp = R(vSrc, p.add(duv)).r, uXm = R(vSrc, p.sub(duv)).r;
        const wZp = R(vSrc, p.add(dwv)).g, wZm = R(vSrc, p.sub(dwv)).g;
        // outward face velocities (positive = leaving this column)
        const fPx = max(uC.add(uXp).mul(0.5), 0.0).mul(h);
        const fMx = max(uC.add(uXm).mul(0.5).negate(), 0.0).mul(h);
        const fPz = max(wC.add(wZp).mul(0.5), 0.0).mul(h);
        const fMz = max(wC.add(wZm).mul(0.5).negate(), 0.0).mul(h);
        // proportional rescale: total outflow over the substep <= the column
        const total = fPx.add(fMx).add(fPz).add(fMz);
        const k = min(float(1), h.mul(DX).div(U.dt).div(total.add(1e-6)));
        textureStore(fluxT, c, vec4(fPx, fMx, fPz, fMz).mul(k)).toWriteOnly();
    })().compute(CELLS).setName(name);

    // 3) height update: h += dt·(inflow−outflow)/dx + emitter mass. EXACT
    //    conservation: every face flux leaves one column and enters exactly
    //    one other (border faces clamp to zero via ClampToEdge reads of vel
    //    — closed basin).
    const mkHeight = (hSrc, hDst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const h = R(hSrc, p).r.toVar();
        const own = R(fluxT, p);                       // r,g,b,a = +x,-x,+z,-z out
        const inXm = R(fluxT, p.sub(duv)).r;           // -x neighbour's +x outflow
        const inXp = R(fluxT, p.add(duv)).g;           // +x neighbour's -x outflow
        const inZm = R(fluxT, p.sub(dwv)).b;
        const inZp = R(fluxT, p.add(dwv)).a;
        const net = inXm.add(inXp).add(inZm).add(inZp)
            .sub(own.r.add(own.g).add(own.b).add(own.a));
        h.addAssign(net.div(DX).mul(U.dt));
        // emitters: mass into a small disc around the impact point
        const w = worldXZ(c);
        for (let e = 0; e < NEMI; e++) {
            const ep = U.emiPos.element(int(e)), ev = U.emiVel.element(int(e));
            const rate = ep.z;
            const d = length(w.sub(ep.xy));
            const rad = float(0.30);
            If(rate.greaterThan(0.0).and(d.lessThan(rad)), () => {
                const area = float(Math.PI).mul(rad).mul(rad);
                h.addAssign(rate.div(area).mul(U.dt)
                    .mul(float(1).sub(d.div(rad)).mul(3)));   // cone; disc-mean of (1-d/R)=1/3, x3 makes the rate exact
            });
        }
        If(U.consume.greaterThan(0.5), () => {
            const ci3 = vec3(c).z.toInt().mul(NX).add(vec3(c).x.toInt());
            h.addAssign(float(depVolRd.element(ci3)).div(FXP).div(DX * DZ));
        });
        // rain: distributed depth, modulated by slow-drifting squall bands.
        // U.rain is a UNIFORM so a scene can ramp the storm in and out
        // (api.setRain); o.rainRate is the initial value AND the build gate.
        if (o.rainRate > 0) {
            const squall = fbm2(w.mul(0.16).add(vec2(U.time.mul(0.11), U.time.mul(0.045))));
            const bands = clamp(squall.mul(1.5).sub(0.25), 0.0, 1.6);
            const rainMul = mix(float(1), bands, float(o.rainPatchiness));
            h.addAssign(U.rain.mul(rainMul).mul(U.dt));
        }
        h.assign(clamp(h, 0.0, o.maxDepth));
        textureStore(hDst, c, vec4(h, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);

    // 4) foam: advect by the NEW velocity, deposit from churn/crest/wake/
    //    emitter impact, decay.
    const mkFoam = (hSrc, vNew, fSrc, fDst, name, dBedSrc) => {
        const bedL = bedOf(dBedSrc);
        return Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const v = R(vNew, p).rg;
        const back = p.sub(vec3(v.x.mul(U.dt).div(WX), 0, v.y.mul(U.dt).div(WZ)));
        const f = R(fSrc, back).r.toVar();
        // churn: divergence magnitude of the velocity field
        const dux = R(vNew, p.add(duv)).r.sub(R(vNew, p.sub(duv)).r).div(2 * DX);
        const dwz = R(vNew, p.add(dwv)).g.sub(R(vNew, p.sub(dwv)).g).div(2 * DZ);
        const churn = abs(dux.add(dwz));
        // crest: surface steepness
        const e = (q) => bedL(q).add(R(hSrc, q).r);
        const steep = length(vec2(
            e(p.add(duv)).sub(e(p.sub(duv))).div(2 * DX),
            e(p.add(dwv)).sub(e(p.sub(dwv))).div(2 * DZ)));
        const h = R(hSrc, p).r;
        const wet = smoothstep(0.0, o.dryEps * 2, h);
        // threshold + saturating response: during a violent fill |div| hits
        // ~100/s across a cell, so a linear gain paints the whole pool white.
        // Normalise to a 0..1 response that needs REAL churn to reach 1.
        const churnN = smoothstep(6.0, 30.0, churn);
        f.addAssign(churnN.mul(o.foamChurn * o.foamGain).mul(U.dt).mul(wet));
        f.addAssign(smoothstep(0.55, 1.6, steep).mul(o.foamCrest * o.foamGain).mul(U.dt).mul(wet));
        // emitter impact churn + sphere wakes
        const w = worldXZ(c);
        for (let e2 = 0; e2 < NEMI; e2++) {
            const ep = U.emiPos.element(int(e2)), ev = U.emiVel.element(int(e2));
            const d = length(w.sub(ep.xy));
            If(ep.z.greaterThan(0.0).and(d.lessThan(0.45)), () => {
                f.addAssign(ev.z.mul(U.dt).mul(2.0).mul(wet));
            });
        }
        for (let s = 0; s < NSPH; s++) {
            const sp = U.sphPos.element(int(s)), sa = U.sphAux.element(int(s));
            const d = length(w.sub(sp.xz));
            const plungeF = max(U.sphAux2.element(int(s)).x.negate(), 0.0).min(6.0);
            const spd = length(vec2(sa.y, sa.z)).add(plungeF.mul(0.6));
            // ⚠ SAME vertical gate as the velocity coupling: without it a
            // sphere still FALLING toward the pool painted its wake from any
            // altitude — white on the water before the body ever arrives
            const dyF = sp.y.sub(bedL(p).add(h)).abs();
            If(d.lessThan(sa.x).and(dyF.lessThan(sa.x.mul(1.4)))
                .and(spd.greaterThan(0.15)), () => {
                f.addAssign(spd.mul(o.foamWake).mul(U.dt).mul(wet));
            });
        }
        If(U.consume.greaterThan(0.5), () => {
            const ci4 = vec3(c).z.toInt().mul(NX).add(vec3(c).x.toInt());
            f.addAssign(float(depFoamRd.element(ci4)).div(FXP).mul(wet));
        });
        f.mulAssign(float(1).sub(min(float(o.foamDecay).mul(U.dt), 0.9)));
        f.assign(clamp(f, 0.0, 1.5));
        textureStore(fDst, c, vec4(f, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    };

    // ── EROSION KERNEL — runs LAST in each substep on the freshly updated
    // depth/velocity, writing the other phase's delta field (the AB/BA
    // discipline). Physics per cell:
    //   capacity C = Kc·|v|·min(h, .35)   (fast, deep flow carries more)
    //   under capacity → ERODE bed toward it; over → DEPOSIT the excess.
    //   Suspended sediment ADVECTS semi-Lagrangian with the flow (the foam
    //   recipe), so spoil travels downstream and fans out where |v| dies.
    //   TALUS: pairwise antisymmetric exchange with the 4 neighbours where
    //   the LIVE bed slope exceeds the angle of repose — cut banks cave in
    //   instead of standing as razor walls. Both sides of every pair read
    //   the SAME source phase and compute the same |excess|, so the
    //   exchange conserves bed volume exactly.
    //   Gates: dry cells neither erode nor advect; talus only acts where
    //   the neighbourhood has actually been touched (|delta| > 3 mm) so
    //   pristine terrain never creeps.
    const mkErode = ERO ? (hNew, vNew, dSrc, dDst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const h = R(hNew, p).r;
        const v = R(vNew, p).rg;
        const here = R(dSrc, p);
        const delta = here.r.toVar();
        const age = here.b.toVar();
        // sediment advects with the flow; delta/age are bed-fixed
        const back = p.sub(vec3(v.x.mul(U.dt).div(WX), 0, v.y.mul(U.dt).div(WZ)));
        const s = R(dSrc, back).g.toVar();
        const wet = smoothstep(EK.minDepth, EK.minDepth * 3, h);
        const spd = length(v);
        // live-bed slope (reused below for talus): steep ground erodes
        // faster — headward retreat, the gully eating uphill
        const bT = (q) => bed(q).add(R(dSrc, q).r);
        const bC = bT(p);
        const slope = length(vec2(
            bT(p.add(duv)).sub(bT(p.sub(duv))).div(2 * DX),
            bT(p.add(dwv)).sub(bT(p.sub(dwv))).div(2 * DZ)));
        // STREAM-POWER capacity: |v|^1.7 with a SATURATING depth term —
        // concentrated fast flow carries far more than a broad slow sheet
        // (the channelization feedback), but past ~8 cm extra depth buys
        // NOTHING: a deepening column stops out-carrying its widening
        // neighbours, which is what lets a wash grow broad instead of
        // drilling a slot
        const C = float(EK.capacity).mul(pow(spd, 1.7)).mul(min(h, 0.08).mul(12.0)).mul(wet);
        const diff = C.sub(s);
        // taper pickup as the cut approaches maxDelta — a gully bottoms out
        const cutRoom = smoothstep(-EK.maxDelta, -EK.maxDelta * 0.6, delta);
        const ero = max(diff, 0.0).mul(EK.erode).mul(U.dt).mul(wet).mul(cutRoom)
            .mul(float(1).add(min(slope, 1.2).mul(1.6))).toVar();
        // BANK EROSION — the widening mechanism: a cell standing above a
        // flowing neighbour is a bank face exposed to that neighbour's
        // current; the flow undercuts it SIDEWAYS regardless of how little
        // water sits on the bank itself. Pickup ∝ the neighbour's stream
        // power × the exposed face height.
        if (EK.bank > 0) {
            let bankPow = float(0);
            for (const dq of [duv, duv.mul(-1), dwv, dwv.mul(-1)]) {
                const pn = p.add(dq);
                const hN = R(hNew, pn).r;
                const vN = R(vNew, pn).rg;
                const face = clamp(bC.sub(bT(pn)), 0.0, 0.6);      // exposed bank height
                const powN = pow(length(vN), 1.7).mul(min(hN, 0.08).mul(12.0))
                    .mul(smoothstep(EK.minDepth, EK.minDepth * 3, hN));
                bankPow = bankPow.add(powN.mul(face));
            }
            const bankEro = bankPow.mul(EK.bank).mul(EK.erode).mul(0.35).mul(U.dt).mul(cutRoom);
            ero.addAssign(bankEro);
        }
        const dep = min(max(diff.negate(), 0.0).mul(EK.deposit).mul(U.dt), s);
        delta.subAssign(ero);
        delta.addAssign(dep);
        s.addAssign(ero);
        s.subAssign(dep);
        // fresh-silt tracker: deposits paint it up, time fades it
        age.addAssign(dep.mul(26.0));
        age.mulAssign(float(1).sub(min(float(0.08).mul(U.dt), 0.5)));
        // talus relaxation vs the 4 neighbours on the LIVE bed
        const reposeH = EK.talusSlope * DX;
        let slump = float(0);
        for (const dq of [duv, duv.mul(-1), dwv, dwv.mul(-1)]) {
            const dEl = bT(p.add(dq)).sub(bC);           // + = neighbour higher
            const ex2 = abs(dEl).sub(reposeH);
            const touched = smoothstep(0.003, 0.012,
                max(abs(R(dSrc, p.add(dq)).r), abs(here.r)));
            slump = slump.add(
                max(ex2, 0.0).mul(0.25 * EK.talusRate).mul(U.dt)
                    .mul(sign(dEl)).mul(touched));
        }
        delta.addAssign(slump);
        delta.assign(clamp(delta, -EK.maxDelta, EK.maxDelta));
        s.assign(clamp(s, 0.0, 0.6));
        age.assign(clamp(age, 0.0, 1.0));
        textureStore(dDst, c, vec4(delta, s, age, 1)).toWriteOnly();
    })().compute(CELLS).setName(name) : null;

    // direction A→B and B→A pairs (erosion kernels read the NEW h/vel)
    const kVelAB = mkVel(hA, velA, velB, 'sweVelAB', dBedA);
    const kFluxB_A = mkFlux(hA, velB, 'sweFluxB_hA');
    const kHeightAB = mkHeight(hA, hB, 'sweHeightAB');
    const kFoamAB = mkFoam(hA, velB, foamA, foamB, 'sweFoamAB', dBedA);
    const kVelBA = mkVel(hB, velB, velA, 'sweVelBA', dBedB);
    const kFluxA_B = mkFlux(hB, velA, 'sweFluxA_hB');
    const kHeightBA = mkHeight(hB, hA, 'sweHeightBA');
    const kFoamBA = mkFoam(hB, velA, foamB, foamA, 'sweFoamBA', dBedB);
    const kErodeAB = ERO ? mkErode(hB, velB, dBedA, dBedB, 'sweErodeAB') : null;
    const kErodeBA = ERO ? mkErode(hA, velA, dBedB, dBedA, 'sweErodeBA') : null;

    let phase = 0;   // 0: state in A, 1: state in B
    let simTime = 0;
    let acc = 0;

    async function step(delta = o.fixedStep) {
        // ⚠⚠ REAL-TIME ACCUMULATOR — the first cut ran a FIXED 1/60 s of sim
        // per call, but the demo renders at 30 fps, so the water played at
        // HALF SPEED. Skye read the slow-motion as "thick jelly" through two
        // physics fixes — a clock error is perceived as viscosity. Advance
        // exactly the wall-clock dt handed in, in CFL-sized substeps.
        const dtSub = o.fixedStep / o.substeps;
        acc = Math.min(acc + Math.min(delta, 0.1), dtSub * o.maxSubSteps);
        U.dt.value = dtSub;
        // spray integrates FIRST so this frame's landings are on the books
        // before the field consumes them in its first substep
        if (spray) {
            spray.SU.dtF.value = Math.min(delta, 0.1);
            spray.SU.time.value = simTime;
            phaseU.value = phase;
            await renderer.computeAsync(spray.kSpray);
            await renderer.computeAsync(spray.kStream);
        }
        let firstSub = true;
        while (acc >= dtSub) {
            acc -= dtSub;
            simTime += dtSub;
            U.time.value = simTime;
            U.consume.value = firstSub ? 1 : 0;
            if (phase === 0) {
                await renderer.computeAsync(kVelAB);
                await renderer.computeAsync(kFluxB_A);
                await renderer.computeAsync(kHeightAB);
                await renderer.computeAsync(kFoamAB);
                if (ERO) await renderer.computeAsync(kErodeAB);
                phase = 1;
            } else {
                await renderer.computeAsync(kVelBA);
                await renderer.computeAsync(kFluxA_B);
                await renderer.computeAsync(kHeightBA);
                await renderer.computeAsync(kFoamBA);
                if (ERO) await renderer.computeAsync(kErodeBA);
                phase = 0;
            }
            if (firstSub) { await renderer.computeAsync(kDepClear); firstSub = false; }
        }
        // evaluate this frame's detail-ripple field, then refresh the
        // surface's vertex buffer from the CURRENT height field
        await renderer.computeAsync(phase === 0 ? kRippleA : kRippleB);
        await renderer.computeAsync(phase === 0 ? kDisplaceA : kDisplaceB);
        if (ERO && kTerraA) await renderer.computeAsync(phase === 0 ? kTerraA : kTerraB);
    }


    // ── SPRAY (v2.0) ────────────────────────────────────────────────────
    // GPU ballistic particles: state in storage buffers, one integrate
    // kernel per FRAME (not per substep), instanced sprites via the proven
    // storage().element(instanceIndex) path. Slots 0..3/4 of the pool are
    // jet particles (home source = i mod NEMI); the top quarter is the
    // breach-burst pool, re-armed by a generation counter in vel.w.
    // ── exchange accumulators: fixed-point (1e-6) int buffers the spray
    // kernel atomically deposits into (landings +, promotions -) and the
    // FIRST substep of each frame consumes. Multi-write is fine here: the
    // one-write law applies to textureStore, not storage buffers.
    const FXP = 1e6;
    const depVolBuf = new THREE.StorageBufferAttribute(new Int32Array(CELLS), 1);
    const depMxBuf = new THREE.StorageBufferAttribute(new Int32Array(CELLS), 1);
    const depMzBuf = new THREE.StorageBufferAttribute(new Int32Array(CELLS), 1);
    const depFoamBuf = new THREE.StorageBufferAttribute(new Int32Array(CELLS), 1);
    const depVolAt = storage(depVolBuf, 'int', CELLS).toAtomic();
    const depMxAt = storage(depMxBuf, 'int', CELLS).toAtomic();
    const depMzAt = storage(depMzBuf, 'int', CELLS).toAtomic();
    const depFoamAt = storage(depFoamBuf, 'int', CELLS).toAtomic();
    const depVolRd = storage(depVolBuf, 'int', CELLS).toReadOnly();
    const depMxRd = storage(depMxBuf, 'int', CELLS).toReadOnly();
    const depMzRd = storage(depMzBuf, 'int', CELLS).toReadOnly();
    const depFoamRd = storage(depFoamBuf, 'int', CELLS).toReadOnly();
    const depVolWr = storage(depVolBuf, 'int', CELLS);
    const depMxWr = storage(depMxBuf, 'int', CELLS);
    const depMzWr = storage(depMzBuf, 'int', CELLS);
    const depFoamWr = storage(depFoamBuf, 'int', CELLS);
    const kDepClear = Fn(() => {
        const id = instanceIndex;
        depVolWr.element(id).assign(int(0));
        depMxWr.element(id).assign(int(0));
        depMzWr.element(id).assign(int(0));
        depFoamWr.element(id).assign(int(0));
    })().compute(CELLS).setName('sweDepClear');
    // world xz -> cell index helpers for the spray kernel
    const cellIdxOf = (x, z) => {
        const ci = clamp(x.sub(center.x).div(WX).add(0.5).mul(NX), 0.5, NX - 0.5).toInt();
        const ck = clamp(z.sub(center.z).div(WZ).add(0.5).mul(NZ), 0.5, NZ - 0.5).toInt();
        return ck.mul(NX).add(ci);
    };

    let spray = null;
    if (o.sprayMax > 0) {
        const MAXP = o.sprayMax;
        const NPROMO = Math.floor(MAXP * 0.3);
        const PROMO0 = MAXP - NPROMO;              // ids >= PROMO0 are field-promoted
        const posBuf = new THREE.StorageBufferAttribute(new Float32Array(MAXP * 4), 4); // xyz pos, w life
        const velBuf = new THREE.StorageBufferAttribute(new Float32Array(MAXP * 4), 4); // xyz vel, w carried m3
        const posSt = storage(posBuf, 'vec4', MAXP);
        const velSt = storage(velBuf, 'vec4', MAXP);
        const SU = {
            dtF: uniform(1 / 30),
            time: uniform(0),
            // pours: system-level water sources. ALL pour mass travels as
            // droplets; there is no hidden injection. pos=(x,y,z),
            // vel=(vx,vy,vz), meta=(spawnProb, on, 0)
            pourPos: uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector3(0, -99, 0))),
            pourVel: uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector3(0, 0, 0))),
            pourMeta: uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector3(0, 0, 0))),
            // aux.x = style (0 jet | 1 seep), aux.y = seep face width (m)
            pourAux: uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector3(0, 0.5, 0))),
        };
        // phase-mixed LIVE bed (bedTex + erosion delta when erosion is on)
        const bedAt = ERO
            ? (uvw) => texture3D(bedTex, uvw, 0).r
                .add(mix(R(dBedA, uvw).r, R(dBedB, uvw).r, phaseU))
            : (uvw) => texture3D(bedTex, uvw, 0).r;
        const surfAt = (x, z) => {
            const uvw = vec3(x.sub(center.x).div(WX).add(0.5), 0.5,
                z.sub(center.z).div(WZ).add(0.5));
            const hh = mix(R(hA, uvw).r, R(hB, uvw).r, phaseU);
            return bedAt(uvw).add(hh);
        };
        const hAt = (uvw) => mix(R(hA, uvw).r, R(hB, uvw).r, phaseU);
        const hPrevAt = (uvw) => mix(R(hB, uvw).r, R(hA, uvw).r, phaseU); // one substep older
        const vAt = (uvw) => mix(R(velA, uvw).rg, R(velB, uvw).rg, phaseU);
        const kSprayInit = Fn(() => {
            const id = instanceIndex;
            posSt.element(id).assign(vec4(0, -99, 0, hash(id).mul(-0.8)));
            velSt.element(id).assign(vec4(0, 0, 0, 0));
        })().compute(MAXP).setName('sweSprayInit');

        const kSpray = Fn(() => {
            const id = instanceIndex;
            const P = posSt.element(id).toVar();
            const V = velSt.element(id).toVar();
            const life = P.w.toVar();
            const isPromo = id.greaterThanEqual(int(PROMO0));
            If(life.greaterThan(0.0), () => {
                If(V.w.lessThan(-0.5), () => {
                    // ── FOAM STATE (Ihmsen lifecycle): a landed splash droplet
                    // does not die — it becomes surface foam RIDING THE FLUID'S
                    // OWN VELOCITY FIELD (position-only updates, pinned to the
                    // surface) until its lifetime runs out. This is the visible
                    // particle↔liquid integration loop.
                    const uvwF = vec3(P.x.sub(center.x).div(WX).add(0.5), 0.5,
                        P.z.sub(center.z).div(WZ).add(0.5));
                    const vF = vAt(uvwF);
                    P.x.addAssign(vF.x.mul(SU.dtF));
                    P.z.addAssign(vF.y.mul(SU.dtF));
                    P.y.assign(surfAt(P.x, P.z).add(0.012));
                    V.xyz.assign(vec3(vF.x, 0, vF.y));      // render reads this
                    // the particle is INVISIBLE in this state (a camera-facing
                    // billboard lying on water reads as a ghost circle) — its
                    // presence is a moving FOAM SOURCE: it feeds the surface
                    // foam field along its drift, and the eroded foam texture
                    // renders the trail flat on the water where it belongs.
                    atomicAdd(depFoamAt.element(cellIdxOf(P.x, P.z)),
                        float(0.55 * o.foamGain).mul(SU.dtF).mul(FXP).round().toInt());
                    life.subAssign(SU.dtF);
                    If(hAt(uvwF).lessThan(o.dryEps).or(life.lessThan(0.0)), () => {
                        life.assign(hash(id.add(int(77))).mul(-0.22));
                        V.w.assign(float(0));
                    });
                }).Else(() => {
                    V.y.subAssign(float(9.8).mul(SU.dtF));
                    P.xyz.addAssign(V.xyz.mul(SU.dtF));
                    life.subAssign(SU.dtF);
                    const surf = surfAt(P.x, P.z);
                    const hitWater = P.y.lessThan(surf);
                    If(hitWater.or(life.lessThan(0.0)), () => {
                        // ── DEMOTION: return carried volume + momentum + foam
                        // to the field where we land. This IS the pour/splash
                        // mass.
                        const vol = V.w;
                        const impact = length(V.xyz);
                        If(vol.greaterThan(0.0), () => {
                            // single centre-cell deposit. (A 5-tap
                            // neighbourhood split was tried against the
                            // pile-spikes: it did NOT fix them and its atomic
                            // contention cost 7 ms/frame — the real cure is
                            // the plunge-to-current momentum below, which
                            // carries mass OUT of the landing zone.)
                            const ci = cellIdxOf(P.x, P.z);
                            atomicAdd(depVolAt.element(ci), vol.mul(FXP).round().toInt());
                            // plunge-to-current: a landing droplet's VERTICAL
                            // momentum converts to lateral flow (Chentanez
                            // momentum return). Without this a near-vertical
                            // pour has nothing carrying water OUT of its
                            // landing zone and piles a spiked mound there.
                            const hv9 = length(vec2(V.x, V.z)).max(0.15);
                            const spreadK = float(1)
                                .add(abs(V.y).mul(0.35).div(hv9)).min(1.2)
                                .mul(o.momentumTransfer);
                            atomicAdd(depMxAt.element(ci),
                                vol.mul(V.x).mul(spreadK).mul(FXP).round().toInt());
                            atomicAdd(depMzAt.element(ci),
                                vol.mul(V.z).mul(spreadK).mul(FXP).round().toInt());
                            // sized so a sustained rain-in zone SATURATES the
                            // field's foam (≈1.0 vs 1.5/s decay): the LIQUID
                            // goes white where droplets land, not just the air
                            // above it — the churn is the field's own state
                            atomicAdd(depFoamAt.element(ci), vol.mul(45.0 * o.foamGain).mul(FXP).round().toInt());
                        });
                        // an energetic splash that truly hit water becomes FOAM.
                        // Pour droplets still die on landing: their cycle time
                        // IS the pour's mass throughput (see setPours capacity).
                        If(isPromo.and(hitWater).and(impact.greaterThan(0.8)), () => {
                            V.w.assign(float(-1));
                            P.y.assign(surf.add(0.012));
                            life.assign(hash(id.add(int(83))).mul(0.9).add(0.4));
                        }).Else(() => {
                            life.assign(hash(id.add(int(77))).mul(-0.22));
                            V.w.assign(float(0));
                        });
                    });
                });
            }).Else(() => {
                life.addAssign(SU.dtF);
                If(life.greaterThan(0.0), () => {
                    const bkt = SU.time.mul(60).toInt();
                    If(isPromo.not(), () => {
                        // ── POUR DROPLET: from its pour's mouth, throttled so
                        // droplet-rate x pourVol = the pour's m3/s.
                        const src = id.mod(NEMI);
                        const meta = SU.pourMeta.element(src);
                        const roll = hash(id.add(int(3)).add(bkt));
                        If(meta.y.greaterThan(0.5).and(roll.lessThan(meta.x)), () => {
                            const jp = SU.pourPos.element(src), jv = SU.pourVel.element(src);
                            const aux = SU.pourAux.element(src);
                            const j1 = hash(id.add(int(5)).add(bkt));
                            const j2 = hash(id.add(int(7)).add(bkt));
                            const j3 = hash(id.add(int(11)).add(bkt));
                            const j4 = hash(id.add(int(23)).add(bkt));
                            const j6 = hash(id.add(int(29)).add(bkt));
                            // spawn IN THE BREAKUP BAND of the stream's arc —
                            // the tube renders the top of the arc as solid
                            // water, and droplets take over exactly where it
                            // fades. The band lives INSIDE the arc's actual
                            // surface-crossing time tL (solved against the
                            // live surface, one refinement step): a fixed
                            // window let late droplets spawn UNDERWATER along
                            // the parabola tail and shard the mesh with
                            // point-hammered deposits.
                            const solveTL = (ys) => {
                                const disc = jv.y.mul(jv.y)
                                    .add(jp.y.sub(ys).mul(19.6)).max(0.01);
                                return jv.y.add(disc.sqrt()).div(9.8);
                            };
                            const uvwM = vec3(jp.x.sub(center.x).div(WX).add(0.5), 0.5,
                                jp.z.sub(center.z).div(WZ).add(0.5));
                            const t1 = solveTL(bedAt(uvwM).add(hAt(uvwM)));
                            const lx = jp.x.add(jv.x.mul(t1)), lz = jp.z.add(jv.z.mul(t1));
                            const uvwL = vec3(lx.sub(center.x).div(WX).add(0.5), 0.5,
                                lz.sub(center.z).div(WZ).add(0.5));
                            const tL = solveTL(bedAt(uvwL).add(hAt(uvwL)))
                                .clamp(0.08, 1.35);
                            // style 'seep': no ballistic arc — a slow dribble
                            // CURTAIN across the seep face (width aux.y),
                            // falling straight into the pool at the rock line.
                            // Same mass ledger either way.
                            const isSeep = aux.x.greaterThan(0.5);
                            const jvS = jv.mul(isSeep.select(float(0.3), float(1)));
                            const ts = isSeep.select(j6.mul(0.2),
                                tL.mul(float(0.72).add(j6.mul(0.27))));
                            const perp = normalize(vec3(jv.z.negate(), 0, jv.x)
                                .add(vec3(0.001, 0, 0)));
                            const lat = isSeep.select(j1.sub(0.5).mul(aux.y), float(0));
                            P.xyz.assign(jp.add(perp.mul(lat)).add(jvS.mul(ts))
                                .add(vec3(0, -4.9, 0).mul(ts).mul(ts)).add(vec3(
                                    j1.sub(0.5).mul(o.sprayJetSpread * 2),
                                    j2.sub(0.5).mul(o.sprayJetSpread),
                                    j3.sub(0.5).mul(o.sprayJetSpread * 2))));
                            V.xyz.assign(jvS.add(vec3(0, -9.8, 0).mul(ts))
                                .mul(j4.mul(0.24).add(0.9)).add(vec3(
                                    j2.sub(0.5).mul(0.55), j3.sub(0.5).mul(0.3),
                                    j1.sub(0.5).mul(0.55))
                                    .mul(isSeep.select(float(0.45), float(1)))));
                            V.w.assign(float(o.pourVol));
                            life.assign(float(1.6));
                        }).Else(() => { life.assign(float(-0.03)); });
                    }).Else(() => {
                        // ── FIELD PROMOTION (paper §2.4): poll a random cell;
                        // fast + steep + wet -> this droplet IS that water:
                        // withdraw the volume and fly with the field velocity.
                        // Breach collars and breaking crests spawn themselves.
                        // ⚠ uniform polling starves small hot regions (a
                        // breach collar is ~10 cells of 65k: ~0.2 hits/frame).
                        // Bias 70% of polls to rings around REGISTERED
                        // disturbances (spheres); the promotion condition
                        // itself stays purely field-driven.
                        const rc1 = hash(id.add(int(31)).add(bkt)).toVar();
                        const rc2 = hash(id.add(int(37)).add(bkt)).toVar();
                        const pick = hash(id.add(int(53)).add(bkt));
                        If(pick.lessThan(0.7), () => {
                            const si2 = pick.mul(NSPH * 10).toInt().mod(NSPH);
                            const spC = U.sphPos.element(si2);
                            const srC = U.sphAux.element(si2).x;
                            If(srC.greaterThan(0.01), () => {
                                const aa = hash(id.add(int(59)).add(bkt)).mul(6.2832);
                                const rr2 = srC.mul(hash(id.add(int(61)).add(bkt)).mul(1.6).add(0.7));
                                rc1.assign(spC.x.add(aa.cos().mul(rr2)).sub(center.x).div(WX).add(0.5));
                                rc2.assign(spC.z.add(aa.sin().mul(rr2)).sub(center.z).div(WZ).add(0.5));
                            });
                        });
                        const uvw = vec3(clamp(rc1, 0.01, 0.99), 0.5, clamp(rc2, 0.01, 0.99));
                        const hC = hAt(uvw);
                        const vC = vAt(uvw);
                        const spdC = length(vC);
                        // ── Ihmsen soft potentials, heightfield form ──
                        const PHI = (I, mn, mx) => I.sub(mn).div(mx - mn).clamp(0, 1);
                        // trapped air: CONVERGING relative velocity vs the 4
                        // neighbours — |Δv| + Δv·dir per pair (head-on 2|Δv|,
                        // pure shear |Δv|, separating 0), halved. This is the
                        // impact detector a speed gate can never be.
                        const taOf = (dq, dirx, dirz) => {
                            const dv = vC.sub(vAt(uvw.add(dq)));
                            return length(dv).add(dv.x.mul(dirx).add(dv.y.mul(dirz))).mul(0.5);
                        };
                        const taRaw = taOf(duv, 1, 0).add(taOf(duv.negate(), -1, 0))
                            .add(taOf(dwv, 0, 1)).add(taOf(dwv.negate(), 0, -1));
                        const Ita = PHI(taRaw, o.promoTaMin, o.promoTaMax);
                        // wave crest: CONVEX curvature (−∇²η) gated by a RISING
                        // surface (Ihmsen's move-in-normal-direction check)
                        const eta = (q) => bedAt(q).add(hAt(q));
                        const etaC = eta(uvw);
                        const lap = eta(uvw.add(duv)).add(eta(uvw.sub(duv)))
                            .add(eta(uvw.add(dwv))).add(eta(uvw.sub(dwv)))
                            .sub(etaC.mul(4)).div(DX * DX);
                        const dhdt = hC.sub(hPrevAt(uvw)).div(U.dt);
                        const rising = smoothstep(0.02, 0.25, dhdt);
                        const Iwc = PHI(lap.negate(), o.promoCrestMin, o.promoCrestMax).mul(rising);
                        // kinetic energy MULTIPLIES — incl. the VERTICAL term:
                        // a breach collar rises fast while barely translating
                        const Ik = PHI(spdC.mul(spdC).add(dhdt.mul(dhdt).mul(0.5)),
                            o.promoEnMin, o.promoEnMax);
                        const pot = Ik.mul(
                            Ita.mul(o.promoKta).add(Iwc.mul(o.promoKwc)).clamp(0, 1));
                        const roll2 = hash(id.add(int(43)).add(bkt));
                        If(hC.greaterThan(0.03).and(roll2.lessThan(pot.mul(o.promoRate))), () => {
                            const wx2 = uvw.x.sub(0.5).mul(WX).add(center.x);
                            const wz2 = uvw.z.sub(0.5).mul(WZ).add(center.z);
                            const ci = cellIdxOf(float(0).add(wx2), float(0).add(wz2));
                            const vol = float(o.promoVol).mul(pot.mul(0.9).add(0.5));
                            atomicAdd(depVolAt.element(ci),
                                vol.negate().mul(FXP).round().toInt());
                            // Ihmsen sampling: positions in a DISC around the
                            // cell + a spread ALONG the velocity (cylinder of
                            // length |v·dt|), and the radial offset acts AS
                            // velocity — an organic staggered cone, never a
                            // synchronized ring.
                            const a6 = hash(id.add(int(41)).add(bkt)).mul(6.2832);
                            const r6 = hash(id.add(int(47)).add(bkt)).sqrt().mul(DX * 2.5);
                            const along = hash(id.add(int(59)).add(bkt)).mul(SU.dtF);
                            const j5 = hash(id.add(int(61)).add(bkt));
                            P.xyz.assign(vec3(
                                wx2.add(a6.cos().mul(r6)).add(vC.x.mul(along)),
                                etaC.add(0.02).add(j5.mul(0.03)),
                                wz2.add(a6.sin().mul(r6)).add(vC.y.mul(along))));
                            const radV = pot.mul(0.9).add(0.35);
                            V.xyz.assign(vec3(
                                vC.x.add(a6.cos().mul(radV)),
                                clamp(dhdt, 0.0, 3.0).mul(1.1)
                                    .add(spdC.mul(o.promoVy)).mul(j5.mul(0.6).add(0.7)),
                                vC.y.add(a6.sin().mul(radV))));
                            V.w.assign(vol);
                            // Ihmsen: lifetime ∝ generation potential — violent
                            // births live longer
                            life.assign(hash(id.add(int(67))).mul(0.5).add(0.35)
                                .mul(pot.mul(0.8).add(0.6)));
                        }).Else(() => { life.assign(float(-0.05)); });
                    });
                });
            });
            P.w.assign(life);
            posSt.element(id).assign(P);
            velSt.element(id).assign(V);
        })().compute(MAXP).setName('sweSpray');

        // Ihmsen renders diffuse material as ACCUMULATED DENSITY — individual
        // particles must never be resolvable. Real-time analog: three splat
        // classes in one pool. DROPLETS (small, velocity-stretched [VdLGS09])
        // + MIST (~18%: large, very soft, barely stretched — fills the gaps
        // so spray reads as one connected volume) + FOAM (landed particles:
        // soft patches drifting with the flow, spreading as they age). All
        // alpha-soft with heavy overlap; realistic grey-white albedo, never
        // cartoon white.
        const smat = new THREE.SpriteNodeMaterial({
            transparent: true, depthWrite: false, fog: false,
        });
        const pRead = posSt.element(instanceIndex);
        const vRead = velSt.element(instanceIndex);
        smat.positionNode = pRead.xyz;
        const alive = pRead.w.greaterThan(0.0);
        const isFoamP = vRead.w.lessThan(-0.5);
        const isMist = hash(instanceIndex.add(int(991))).lessThan(0.18);
        const lifeK = pRead.w.div(1.3).clamp(0, 1);
        const born = float(1).sub(lifeK);
        const vView = cameraViewMatrix.mul(vec4(vRead.xyz, 0.0)).xyz;
        const vvLen = length(vView.xy);
        // sprayStretch: water droplets streak into needles; gel stays blobby
        const stretchD = vvLen.mul(0.14 * o.sprayStretch).add(1.0)
            .min(1.0 + 2.4 * o.sprayStretch);
        const stretch = isFoamP.select(float(1.0),
            isMist.select(vvLen.mul(0.04).add(1.0).min(1.6), stretchD));
        // ⚠ mist gigantism: at 2.8× plus velocity stretch a mist sprite
        // reached ~0.5 m — sparse arc droplets rendered as isolated floating
        // SLABS (the demo's "detached dashes", misdiagnosed as tube geometry
        // three times) and dense muzzle clouds fused into hovering cream
        // comets (the gel gun). Smaller class + a hard world-length cap.
        const szK = isFoamP.select(
            float(0.0),                               // foam renders via the FIELD
            isMist.select(float(1.8), float(1.0)));
        const baseS = float(o.spraySize)
            .mul(hash(instanceIndex).mul(0.9).add(0.55))
            .mul(born.mul(0.5).add(0.6)).mul(szK);
        smat.scaleNode = alive.select(
            vec2(baseS.mul(stretch).min(0.26),
                baseS.div(stretch.mul(0.5).add(0.5))), vec2(0));
        smat.rotationNode = atan(vView.y, vView.x).negate();
        const uvc = uv();
        const rr = uvc.sub(0.5).length();
        const brk = vnoise(uvc.mul(3.7).add(hash(instanceIndex).mul(41.0)))
            .mul(0.5).add(0.62);
        const brk2 = vnoise(uvc.mul(7.9).add(hash(instanceIndex.add(int(17))).mul(31.0)))
            .mul(0.4).add(0.72);
        const lit = uvc.y.mul(0.3).add(0.78);
        const albedo = isFoamP.select(vec3(0.86, 0.90, 0.90),
            isMist.select(vec3(0.80, 0.87, 0.89), vec3(0.90, 0.95, 0.94)));
        smat.colorNode = vec4(albedo.mul(lit), float(1));
        const edge = isFoamP.select(smoothstep(0.5, 0.06, rr),
            isMist.select(smoothstep(0.5, 0.0, rr), smoothstep(0.5, 0.10, rr)));
        // mist only earns its size in DENSE fast spray where overlap hides
        // individuals; an isolated slow drifter would read as a bokeh ghost,
        // so it fades with speed
        const mistFade = smoothstep(0.3, 1.2, length(vRead.xyz));
        const aK = isFoamP.select(float(0.0),
            isMist.select(float(0.11).mul(mistFade), lifeK.mul(0.6).add(0.2)));
        smat.opacityNode = edge.mul(brk).mul(brk2)
            .mul(smoothstep(0.0, 0.15, born))
            .mul(aK).mul(o.dropletVisibility)
            .mul(alive.select(float(1), float(0)));
        const sprayMesh = new THREE.InstancedMesh(
            new THREE.PlaneGeometry(1, 1), smat, MAXP);
        sprayMesh.name = 'water_swe_spray';
        sprayMesh.frustumCulled = false;
        sprayMesh.renderOrder = 11;
        for (const k of ['noClippingCheck', 'noSupportCheck', 'allowIntersect',
            'noMotionCheck', 'noZFightCheck']) sprayMesh.userData[k] = true;
        // ── POUR STREAMS: the visible JET connecting each mouth to the pool.
        // Droplets alone read as dots hanging near a spout (Skye, twice): a
        // real pour is a solid glassy stream that necks down (A·|v| = Q),
        // aerates, and BREAKS UP into droplets. The tube is computed from the
        // SAME ballistic arc the droplets fly and is cut by the LIVE water
        // surface — one physics, three renderings: stream → droplets → churn.
        const SSEG = 28, SRAD = 8, STMAX = 1.35;
        const NSV = NEMI * SSEG * SRAD;
        const strPosBuf = new THREE.StorageBufferAttribute(new Float32Array(NSV * 4), 4);
        const strNorBuf = new THREE.StorageBufferAttribute(new Float32Array(NSV * 4), 4);
        const strPosSt = storage(strPosBuf, 'vec4', NSV);
        const strNorSt = storage(strNorBuf, 'vec4', NSV);
        const kStream = Fn(() => {
            const id = instanceIndex;
            const pi = id.div(SSEG * SRAD);
            const rem = id.mod(SSEG * SRAD);
            const ring = rem.div(SRAD), spoke = rem.mod(SRAD);
            const s = float(ring).div(SSEG - 1);
            const th = float(spoke).div(SRAD).mul(6.2832);
            const jp = SU.pourPos.element(pi), jv = SU.pourVel.element(pi);
            const meta = SU.pourMeta.element(pi);
            // parameterize the tube over the arc's ACTUAL surface-crossing
            // time (same solve as the droplet breakup band, so the tube fade
            // and the droplet takeover stay aligned at the same spot)
            const solveTL = (ys) => {
                const disc = jv.y.mul(jv.y).add(jp.y.sub(ys).mul(19.6)).max(0.01);
                return jv.y.add(disc.sqrt()).div(9.8);
            };
            const uvwM = vec3(jp.x.sub(center.x).div(WX).add(0.5), 0.5,
                jp.z.sub(center.z).div(WZ).add(0.5));
            const ysM = bedAt(uvwM).add(hAt(uvwM));
            const t1g = solveTL(ysM);
            const lxg = jp.x.add(jv.x.mul(t1g)), lzg = jp.z.add(jv.z.mul(t1g));
            const uvwL = vec3(lxg.sub(center.x).div(WX).add(0.5), 0.5,
                lzg.sub(center.z).div(WZ).add(0.5));
            // ⚠ the refined solve can DEGENERATE when the landing sample hits
            // a transient runup tongue standing ABOVE the mouth (disc<0 →
            // collapsed tL → the tube crumples into a kinked ribbon). Floor
            // it against the mouth-based solve; overshoot is safe (the
            // waterline cut hides submerged rings), undershoot is the artifact
            const tL = max(solveTL(bedAt(uvwL).add(hAt(uvwL))),
                t1g.mul(0.6)).clamp(0.08, STMAX);
            const tF = s.mul(tL).mul(1.03);
            const pos = jp.add(jv.mul(tF)).add(vec3(0, -4.9, 0).mul(tF).mul(tF)).toVar();
            const vNow = jv.add(vec3(0, -9.8, 0).mul(tF));
            const spd = length(vNow).max(0.4);
            const Q = meta.z.max(0.001);
            // radius: mouth radius from mass conservation (CAPPED — demo-scale
            // rates are physically firehoses), then the NECKING taper applied
            // to the capped value: real falling water thins as it accelerates
            // (r ∝ 1/√v). Capping the raw formula froze the radius wherever
            // the cap engaged → uniform "bent pipe" (Skye). Wobble on top.
            const spd0 = length(jv).max(0.4);
            const rMouth = Q.div(spd0.mul(Math.PI)).sqrt().min(0.08);
            // the wobble TRAVELS mouth→water in exactly tL (real columns
            // carry their surface waves at flow speed — a fixed-clock wobble
            // reads as a rigid bent pipe once the arc is short)
            const r0 = rMouth.mul(spd0.div(spd).sqrt())
                .mul(vnoise(vec2(s.sub(U.time.div(tL)).mul(9.0), float(pi).mul(9.7)))
                    .mul(0.55).add(0.75));
            const Tn = normalize(vNow);
            // ⚠ frame from cross(T, up) DEGENERATES as the fall steepens to
            // vertical — rings collapse and flip into a kinked ribbon. The
            // jet's horizontal heading is constant along the whole arc and
            // never parallel to T: a stable reference by construction.
            const Nn = normalize(vec3(jv.z.negate(), 0, jv.x).add(vec3(0.001, 0, 0)));
            const Bn = normalize(cross(Tn, Nn));
            const rad = Nn.mul(th.cos()).add(Bn.mul(th.sin()));
            pos.addAssign(rad.mul(r0));
            // ⚠ cut MONOTONE along the arc via the tL solve, never per-vertex
            // against the live surface: a per-ring waterline test over spiky
            // runup water chopped the tube into detached floating DASHES.
            // tL already targets the crossing; everything past it is gone.
            const sCut = float(1).sub(smoothstep(0.94, 1.0, s));
            // the tube stays a body of water until just above CONTACT — a
            // stream that fades out mid-air before its own landing reads as
            // a hologram. The last ~15% dissolves into the droplet band.
            const brkA = float(1).sub(smoothstep(0.85, 1.0, s).mul(0.7));
            // a mouth below the local waterline has no airborne jet at all;
            // 'seep' pours render no tube — their water is a droplet curtain
            const dryMouth = smoothstep(0.02, 0.12, jp.y.sub(ysM));
            const alpha = meta.y.mul(dryMouth)
                .mul(float(1).sub(SU.pourAux.element(pi).x))
                .mul(sCut).mul(brkA.mul(0.85));
            strPosSt.element(id).assign(vec4(
                pos.x.sub(center.x), pos.y.sub(center.y), pos.z.sub(center.z), alpha));
            strNorSt.element(id).assign(vec4(rad, tL));   // w = arc flight time tL
        })().compute(NSV).setName('sweStream');
        const strGeo = new THREE.BufferGeometry();
        {
            const idx = [];
            for (let p2 = 0; p2 < NEMI; p2++) {
                const base = p2 * SSEG * SRAD;
                for (let i2 = 0; i2 < SSEG - 1; i2++) for (let j2 = 0; j2 < SRAD; j2++) {
                    const a = base + i2 * SRAD + j2;
                    const b = base + i2 * SRAD + (j2 + 1) % SRAD;
                    const c2 = base + (i2 + 1) * SRAD + j2;
                    const d2 = base + (i2 + 1) * SRAD + (j2 + 1) % SRAD;
                    idx.push(a, c2, b, b, c2, d2);
                }
            }
            strGeo.setIndex(idx);
            strGeo.setAttribute('position',
                new THREE.BufferAttribute(new Float32Array(NSV * 3), 3));
            const uvArr = new Float32Array(NSV * 2);
            for (let v2 = 0; v2 < NSV; v2++) {
                const rem2 = v2 % (SSEG * SRAD);
                uvArr[v2 * 2] = (rem2 % SRAD) / SRAD;
                uvArr[v2 * 2 + 1] = Math.floor(rem2 / SRAD) / (SSEG - 1);
            }
            strGeo.setAttribute('uv', new THREE.BufferAttribute(uvArr, 2));
        }
        const strMat = new THREE.MeshBasicNodeMaterial({
            transparent: true, depthWrite: false, fog: false,
        });
        strMat.positionNode = strPosSt.element(vertexIndex).xyz;
        strMat.colorNode = Fn(() => {
            const s2 = uv().y;
            const nrm = normalize(strNorSt.element(vertexIndex).xyz);
            const vd = normalize(cameraPosition.sub(positionWorld));
            // restrained reflection: at full mirror weight the thin tube read
            // as a chrome/heat-haze "distortion", not falling water
            const fr = pow(float(1).sub(abs(dot(nrm, vd))), 2.0).mul(0.4).add(0.10);
            const skyC = o.envTex
                ? texture(o.envTex, equirectUV(normalize(reflect(vd.negate(), nrm)))).rgb
                : U.skyColor;
            // aeration: white streaks scrolling down the jet. Real small falls
            // (checked against reference photos) aerate almost FROM THE LIP —
            // glass survives only a short laminar stretch, then the stream is
            // whitewater-dominant ribbon, not a glassy pipe that whitens late.
            // ⚠ around-tube frequency must stay ≤ ~2 cycles over the 8 spokes
            // or the interpolation aliases into hard zigzag bands
            // aeration grows with ABSOLUTE flight time (s2·tL), and the
            // streak pattern TRAVELS down the column at flow rate — both
            // cues a short arc loses on a fixed clock ("collapses back to a
            // solid teal tube" — Skye, twice)
            const tLv = strNorSt.element(vertexIndex).w.max(0.08);
            const streak = smoothstep(0.35, 0.85,
                vnoise(vec2(s2.sub(U.time.div(tLv)).mul(16.0),
                    uv().x.mul(2.0).add(s2.mul(1.5)))))
                .mul(smoothstep(0.06, 0.4, s2.mul(tLv)))
                .mul(o.streamAeration);   // honey stays glass; water whitens
            const base2 = mix(mix(U.shallowColor, U.deepColor, 0.35), skyC, fr);
            return vec4(mix(base2, U.foamColor.mul(0.95), streak.mul(0.85)), 1.0);
        })();
        strMat.opacityNode = Fn(() => {
            // ligament breakup: the lower stream erodes into ragged strands
            // through scrolling noise instead of thinning uniformly — the
            // difference between a dissolving jet and a fading hologram
            const s3 = uv().y;
            const tLe = strNorSt.element(vertexIndex).w.max(0.08);
            const nzE = vnoise(vec2(s3.sub(U.time.div(tLe)).mul(18.0),
                uv().x.mul(2.0).add(s3.mul(1.5))));
            // ⚠ capped at 0.55: erosion at 0.85 depth SEVERED edge-on tubes
            // into detached floating dashes (misdiagnosed twice as frame
            // collapse, then as the waterline cut — hash-compare proved both
            // wrong). The tube must always keep a thread of continuity.
            const erode = smoothstep(0.5, 0.95, s3)
                .mul(smoothstep(0.3, 0.8, nzE)).mul(0.55 * o.streamAeration);
            return strPosSt.element(vertexIndex).w.mul(float(1).sub(erode));
        })();
        const streamMesh = new THREE.Mesh(strGeo, strMat);
        streamMesh.userData._strPosBuf = strPosBuf;   // debug readback handle
        streamMesh.name = 'water_swe_stream';
        streamMesh.position.copy(center);
        streamMesh.renderOrder = 10;
        streamMesh.frustumCulled = false;
        for (const k of ['noClippingCheck', 'noSupportCheck', 'allowIntersect',
            'noMotionCheck', 'noZFightCheck']) streamMesh.userData[k] = true;
        spray = { kSpray, kSprayInit, SU, mesh: sprayMesh, streamMesh, kStream };
    }

    // ── surface mesh ──────────────────────────────────────────────────────
    // ⚠ the height/foam READ NODES must follow the ping-pong. A swapping JS
    // reference is the classic silent no-op; instead the material reads BOTH
    // textures and lerps by a phase uniform (0 → A, 1 → B). Two taps, zero
    // rebinding, always current.
    const phaseU = uniform(0);
    const hRead = (p) => mix(R(hA, p).r, R(hB, p).r, phaseU);
    const foamRead = (p) => mix(R(foamA, p).r, R(foamB, p).r, phaseU);
    // phase-mixed LIVE bed + suspended-sediment reads for the materials
    const bedRd = ERO
        ? (p) => bed(p).add(mix(R(dBedA, p).r, R(dBedB, p).r, phaseU))
        : bed;
    const siltRd = ERO
        ? (p) => mix(R(dBedA, p).g, R(dBedB, p).g, phaseU)
        : () => float(0);
    // ⚠⚠ NO TEXTURE READS IN THE VERTEX STAGE — ANY form of them (sampled OR
    // textureLoad, storage OR data texture) makes this stack emit an invalid
    // vertex module ("ShaderModule with 'vertex' label is invalid") and the
    // mesh silently never draws. The proven road is the compute-particles
    // pattern: a DISPLACE KERNEL (compute reads are proven by every sim
    // kernel) writes each grid vertex's position into a storage buffer, and
    // the vertex stage does a plain storage().element(vertexIndex).

    // ripple bake: same flowmap-advected field the fragment used to compute
    // per pixel, now once per cell — stored in METRES (amp + activity gate
    // applied), so consumers just add it to the surface height
    const mkRipple = (hSrc, vSrc, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const h = R(hSrc, p).r;
        const vv2 = R(vSrc, p).rg;
        const actR = smoothstep(0.04, 0.45, length(vv2))
            .mul(smoothstep(0.0, o.dryEps * 6, h));
        const w = worldXZ(c);
        const tt = U.time;
        const ph1 = fract(tt.div(o.flowT));
        const ph2 = fract(tt.div(o.flowT).add(0.5));
        const r1 = rippleField(w.x.sub(vv2.x.mul(ph1.mul(o.flowT))),
            w.y.sub(vv2.y.mul(ph1.mul(o.flowT))), tt.mul(o.rippleSpeed));
        const r2 = rippleField(w.x.sub(vv2.x.mul(ph2.mul(o.flowT))),
            w.y.sub(vv2.y.mul(ph2.mul(o.flowT))), tt.mul(o.rippleSpeed).add(31.7));
        const rip = mix(r1, r2, abs(ph1.mul(2).sub(1)))
            .mul(o.rippleAmp).mul(actR);
        // .g carries the flow-advected foam-erosion noise (same two-phase
        // advection), sparing another ~8 noise calls per wet pixel
        const fsc = float(o.foamTexScale);
        const nzF = (off) => fbm2(vec2(w.x, w.y).sub(off).mul(fsc).add(3.1)).mul(0.55)
            .add(fbm2(vec2(w.x, w.y).sub(off).mul(fsc.mul(3.7)).add(17.3)).mul(0.45));
        const foamNz = mix(nzF(vv2.mul(ph1.mul(o.flowT))),
            nzF(vv2.mul(ph2.mul(o.flowT))), abs(ph1.mul(2).sub(1)));
        textureStore(rippleT, c, vec4(rip, foamNz, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kRippleA = mkRipple(hA, velA, 'sweRippleA');
    const kRippleB = mkRipple(hB, velB, 'sweRippleB');

    const geo = new THREE.PlaneGeometry(WX, WZ, NX - 1, NZ - 1);
    geo.rotateX(-Math.PI / 2);
    const NVERT = NX * NZ;
    const posAttr = new THREE.StorageBufferAttribute(new Float32Array(NVERT * 4), 4);
    const posStore = storage(posAttr, 'vec4', NVERT);
    // vertex (i,k) of the plane grid: vertexIndex = k*NX + i, u=i/(NX-1),
    // v row order matches PlaneGeometry (v=1 at -z after the rotateX above).
    const mkDisplace = (hSrc, vSrc, name, dBedSrc) => {
        const bedL = bedOf(dBedSrc);
        return Fn(() => {
        const id = instanceIndex;
        const i = id.mod(NX), k = id.div(NX);
        const u2 = vec2(float(i).div(NX - 1), float(k).div(NZ - 1));
        const wx = u2.x.sub(0.5).mul(WX);
        const wz = u2.y.sub(0.5).mul(WZ);          // plane row k runs +z (verified by probe)
        const p = vec3(u2.x, 0.5, u2.y);
        const h = R(hSrc, p).r;
        // detail ripples come pre-baked (metres) from the ripple kernel
        const rip = R(rippleT, p).r;
        const y = bedL(p).add(h).add(rip).sub(center.y);
        posStore.element(id).assign(vec4(wx, y, wz, h));
    })().compute(NVERT).setName(name);
    };
    const kDisplaceA = mkDisplace(hA, velA, 'sweDisplaceA', dBedA);
    const kDisplaceB = mkDisplace(hB, velB, 'sweDisplaceB', dBedB);

    // ── ERODING TERRAIN PATCH — the ground the water carves, as a mesh.
    // Same storage-buffer displacement discipline as the water surface
    // (vertex-stage texture reads silently kill the draw on this stack).
    // The fragment tints live off the phase-mixed delta field: carved cells
    // expose raw cut earth, fresh deposits wear wet silt, standing water
    // darkens the ground under it.
    let terraMesh = null, kTerraA = null, kTerraB = null;
    if (ERO && EK.terrain) {
        const tGeo = new THREE.PlaneGeometry(WX, WZ, NX - 1, NZ - 1);
        tGeo.rotateX(-Math.PI / 2);
        const tAttr = new THREE.StorageBufferAttribute(new Float32Array(NVERT * 4), 4);
        const tStore = storage(tAttr, 'vec4', NVERT);
        const mkTerra = (dBedSrc, name) => Fn(() => {
            const id = instanceIndex;
            const i = id.mod(NX), k = id.div(NX);
            const u2 = vec2(float(i).div(NX - 1), float(k).div(NZ - 1));
            const wx = u2.x.sub(0.5).mul(WX);
            const wz = u2.y.sub(0.5).mul(WZ);
            const p = vec3(u2.x, 0.5, u2.y);
            const dd = R(dBedSrc, p).r;
            const y = bed(p).add(dd).sub(center.y);
            tStore.element(id).assign(vec4(wx, y, wz, dd));
        })().compute(NVERT).setName(name);
        kTerraA = mkTerra(dBedA, 'sweTerraA');
        kTerraB = mkTerra(dBedB, 'sweTerraB');
        const tMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.95, metalness: 0 });
        tMat.positionNode = tStore.element(vertexIndex).xyz;
        const dPh = (q) => mix(R(dBedA, q).r, R(dBedB, q).r, phaseU);
        const agePh = (q) => mix(R(dBedA, q).b, R(dBedB, q).b, phaseU);
        const bedT = (q) => bed(q).add(dPh(q));
        const tUv = uv();
        const tP = (u2) => vec3(u2.x, 0.5, float(1).sub(u2.y));
        tMat.normalNode = Fn(() => {
            const p = tP(tUv);
            return transformNormalToView(normalize(vec3(
                bedT(p.sub(duv)).sub(bedT(p.add(duv))).div(2 * DX),
                1.0,
                bedT(p.sub(dwv)).sub(bedT(p.add(dwv))).div(2 * DZ))));
        })();
        tMat.colorNode = Fn(() => {
            const p = tP(tUv);
            const base = EK.terrainMaps && EK.terrainMaps.albedo
                ? texture(EK.terrainMaps.albedo, tUv.mul(EK.terrainRepeat)).rgb
                : EU.cutColor.mul(1.35);
            const dd = dPh(p);
            const cut = smoothstep(0.015, 0.3, dd.negate());
            const silt = smoothstep(0.06, 0.5, agePh(p))
                .max(smoothstep(0.01, 0.2, dd));
            const hW = hRead(p);
            const wet = smoothstep(0.0, 0.02, hW).mul(EK.wetDarken);
            const col = mix(base, EU.cutColor, cut.mul(0.75)).toVar();
            col.assign(mix(col, EU.siltColor, silt.mul(0.8)));
            col.mulAssign(float(1).sub(wet));
            return vec4(col, 1.0);
        })();
        if (EK.terrainMaps && EK.terrainMaps.rough) {
            tMat.roughnessNode = texture(EK.terrainMaps.rough, tUv.mul(EK.terrainRepeat)).r;
        }
        terraMesh = new THREE.Mesh(tGeo, tMat);
        terraMesh.name = 'water_swe_terrain';
        terraMesh.position.copy(center);
        terraMesh.frustumCulled = false;
        terraMesh.receiveShadow = true;
        for (const k of ['noClippingCheck', 'noSupportCheck', 'allowIntersect',
            'noMotionCheck', 'noZFightCheck']) terraMesh.userData[k] = true;
    }
    const mat = new THREE.MeshBasicNodeMaterial({
        transparent: true, depthWrite: false, fog: false,
    });

    const uvNode = uv();
    const pTex = (u2) => vec3(u2.x, 0.5, float(1).sub(u2.y));
    // vertex: pure storage-buffer read, zero texture bindings in this stage
    mat.positionNode = posStore.element(vertexIndex).xyz;

    // fragment
    mat.colorNode = Fn(() => {
        const p = pTex(uvNode);
        const h = hRead(p);
        // normal from ∇(bed + h + ripple), central differences — the ripple
        // term reads the per-frame bake, so the whole detail-normal path is
        // four texture taps instead of a per-pixel noise stack
        const e = (q) => bedRd(q).add(hRead(q)).add(R(rippleT, q).r);
        const velH = mix(R(velA, p).rg, R(velB, p).rg, phaseU);   // debug view
        const n = normalize(vec3(
            e(p.sub(duv)).sub(e(p.add(duv))).div(2 * DX),
            1.0,
            e(p.sub(dwv)).sub(e(p.add(dwv))).div(2 * DZ)));
        const viewD = normalize(cameraPosition.sub(positionWorld));
        const fresnel = pow(float(1).sub(max(dot(n, viewD), 0.0)), 3.0)
            .mul(0.85).add(0.04);
        const depthTint = mix(U.shallowColor, U.deepColor,
            float(1).sub(exp(h.negate().mul(U.absorption)))).toVar();
        // suspended sediment MUDDIES the water — the visible proof the flow
        // is carrying the hillside downstream
        if (ERO) {
            const muddy = smoothstep(0.004, 0.10, siltRd(p));
            depthTint.assign(mix(depthTint, EU.siltWaterColor, muddy.mul(0.85)));
        }
        const spec = pow(max(dot(reflect(U.keyLightDir.negate(), n), viewD), 0.0), o.specPow);
        const glow = float(1).sub(exp(h.negate().mul(U.emissiveFalloff)));
        // reflection color: the real sky along the reflected ray when an env
        // equirect is provided; the flat skyColor constant otherwise
        const skyRef = o.envTex
            ? texture(o.envTex, equirectUV(normalize(
                reflect(viewD.negate(), n)).mul(vec3(1, 1, 1)))).rgb
            : U.skyColor;
        const surface = mix(depthTint, skyRef, fresnel).add(vec3(spec.mul(o.specGain)));
        const lit = U.emissiveColor.mul(U.emissiveStrength);
        const col = mix(surface, lit, glow.mul(U.emissiveStrength.min(1.0))).toVar();
        // SWE_DEBUG=promo: paint the Ihmsen potentials — R = trapped air
        // (converging Δv), G = crest (convex+rising), B = energy. Promotion
        // probability ≈ B·(kta·R + kwc·G), so spray sources glow magenta/
        // white-ish while a calm pool stays dark. Diagnosis only.
        if (globalThis.Deno?.env.get('SWE_DEBUG') === 'promo') {
            const vD = (q) => mix(R(velA, q).rg, R(velB, q).rg, phaseU);
            const PHI = (I, mn, mx) => I.sub(mn).div(mx - mn).clamp(0, 1);
            const taOf = (dq, dirx, dirz) => {
                const dv = velH.sub(vD(p.add(dq)));
                return length(dv).add(dv.x.mul(dirx).add(dv.y.mul(dirz))).mul(0.5);
            };
            const taRaw = taOf(duv, 1, 0).add(taOf(duv.negate(), -1, 0))
                .add(taOf(dwv, 0, 1)).add(taOf(dwv.negate(), 0, -1));
            const eD = (q) => bedRd(q).add(hRead(q));
            const lapD = eD(p.add(duv)).add(eD(p.sub(duv)))
                .add(eD(p.add(dwv))).add(eD(p.sub(dwv)))
                .sub(eD(p).mul(4)).div(DX * DX);
            const hPrevD = mix(R(hB, p).r, R(hA, p).r, phaseU);
            const dhdtD = h.sub(hPrevD).div(U.dt);
            const risingD = smoothstep(0.02, 0.25, dhdtD);
            const spdD = length(velH);
            return vec4(
                PHI(taRaw, o.promoTaMin, o.promoTaMax),
                PHI(lapD.negate(), o.promoCrestMin, o.promoCrestMax).mul(risingD),
                PHI(spdD.mul(spdD).add(dhdtD.mul(dhdtD).mul(0.5)),
                    o.promoEnMin, o.promoEnMax),
                1.0);
        }
        const f = foamRead(p).mul(U.foamStrength).clamp(0, 1.2);
        // ── ERODED FOAM COVERAGE (Jacobian-foam rendering practice): the
        // foam value drives coverage through a FLOW-ADVECTED noise threshold
        // — dense foam is solid, decaying foam thins into lace, the pattern
        // travels with the water. Two octaves: patch structure + fine lace.
        const foamNz = R(rippleT, p).g;   // per-frame advected field, ~0..1.5
        const cov = smoothstep(0.02, 0.30, f.sub(foamNz.mul(0.55)));
        // sub-threshold residue so decay reads as thinning lace, not a clip
        const wisp = smoothstep(0.0, 0.5, f)
            .mul(smoothstep(0.75, 0.35, foamNz)).mul(0.25);
        col.assign(mix(col, U.foamColor.mul(0.92), cov.mul(0.8)));
        col.assign(mix(col, U.foamColor.mul(0.8), wisp));
        return vec4(col, 1.0);
    })();
    mat.opacityNode = Fn(() => {
        const p = pTex(uvNode);
        const h = hRead(p);
        const f = foamRead(p).clamp(0, 1);
        return smoothstep(0.0, o.shoreFade, h)
            .mul(U.surfaceOpacity).add(f.mul(0.22)).clamp(0, 1);
    })();

    const surfaceMesh = new THREE.Mesh(geo, mat);
    surfaceMesh.name = 'water_swe_surface';
    surfaceMesh.position.copy(center);
    surfaceMesh.renderOrder = 10;
    surfaceMesh.frustumCulled = false;
    for (const k of ['noClippingCheck', 'noSupportCheck', 'allowIntersect',
        'noMotionCheck', 'noZFightCheck']) surfaceMesh.userData[k] = true;

    // ── API ───────────────────────────────────────────────────────────────
    const api = {
        surfaceMesh, uniforms: U, step,
        sprayMesh: spray ? spray.mesh : null,
        streamMesh: spray ? spray.streamMesh : null,
        /** the eroding ground patch (erosion:{terrain:true} only) — add it to
         *  the scene OVER the static terrain; it carves live as water works */
        terrainMesh: terraMesh,
        /** POURS — the system's water sources. Each is a mouth + jet velocity
         *  + rate (m3/s); ALL mass travels as droplets and lands where the
         *  arc lands. No hidden injection, no separate visual jets. */
        setPours(list = []) {
            if (!spray) return;
            const NPOUR = NEMI;
            const slotsPer = Math.floor(o.sprayMax * 0.7 / NPOUR);
            const cycleEst = 1.05;         // avg flight+cooldown, seconds
            for (let i = 0; i < NPOUR; i++) {
                const j = list[i];
                spray.SU.pourPos.array[i].set(j ? j.x : 0, j ? j.y : -99, j ? j.z : 0);
                spray.SU.pourVel.array[i].set(j ? (j.vx || 0) : 0, j ? (j.vy || 0) : 0, j ? (j.vz || 0) : 0);
                const rate = j ? (j.rate || 0) : 0;
                const needed = rate / o.pourVol;                  // droplets/s
                const capacity = slotsPer / cycleEst;
                // meta.z carries the rate: the stream tube's radius comes from
                // mass conservation A·|v| = Q
                spray.SU.pourMeta.array[i].set(Math.min(1, needed / capacity), rate > 0 ? 1 : 0, rate);
                // style: 'jet' (default, ballistic tube + droplets) or 'seep'
                // (no tube; slow dribble curtain of width seepWidth)
                spray.SU.pourAux.array[i].set(
                    j && j.style === 'seep' ? 1 : 0, j ? (j.seepWidth ?? 0.5) : 0.5, 0);
            }
        },
        get simTime() { return simTime; },
        /** flip the material's read phase — call ONCE per frame after step() */
        syncRenderPhase() { phaseU.value = phase; },
        /** live rainfall dial, m/s of depth (needs rainRate > 0 at build so
         *  the kernel path exists) — ramp a storm in and out on camera */
        setRain(v) { U.rain.value = Math.max(0, v); },
        setEmitters(list = []) {
            for (let i = 0; i < NEMI; i++) {
                const e = list[i];
                U.emiPos.array[i].set(e ? e.x : 0, e ? e.z : 0, e ? (e.rate ?? 0) : 0);
                U.emiVel.array[i].set(e ? (e.vx ?? 0) : 0, e ? (e.vz ?? 0) : 0, e ? (e.foam ?? 0.8) : 0);
            }
        },
        setSpheres(list = []) {
            for (let i = 0; i < NSPH; i++) {
                const s = list[i];
                U.sphPos.array[i].set(s ? s.x : 0, s ? s.y : -99, s ? s.z : 0);
                U.sphAux.array[i].set(s ? s.r : 0, s ? (s.vx ?? 0) : 0, s ? (s.vz ?? 0) : 0);
                U.sphAux2.array[i].set(s ? (s.vy ?? 0) : 0, 0, 0);
            }
        },
        async init() {
            for (const k of [kInitH_A, kInitH_B, kInitV_A, kInitV_B, kInitF_A, kInitF_B])
                await renderer.computeAsync(k);
            if (ERO) {
                await renderer.computeAsync(mkInit(dBedA, 'sweInitDBA'));
                await renderer.computeAsync(mkInit(dBedB, 'sweInitDBB'));
                if (kTerraA) await renderer.computeAsync(kTerraA);
            }
            if (spray) await renderer.computeAsync(spray.kSprayInit);
            await renderer.computeAsync(kDepClear);
            return api;
        },
    };
    return api;
}

if (typeof globalThis !== 'undefined') globalThis.createWaterSWE = createWaterSWE;
