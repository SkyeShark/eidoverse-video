// fluid_grid.js — three.js `webgpu_volume_fire` for eidoverse.
//
// ════════════════════════════════════════════════════════════════════════
// THIS IS A VERBATIM PORT of examples/webgpu_volume_fire.html (three.js dev).
// Every constant, kernel, shading term and the full COMPOSITING PIPELINE
// (half-res volumetric pass → gaussian denoise → saturation → ×0.5 →
// max/add composite → bloom) is the example's own. Do not "improve" it.
// ════════════════════════════════════════════════════════════════════════
//
// The ONLY deviations, each forced by r184 vs dev (search "⚠R184"):
//   1. Vendored dev VolumetricLightingModel + FireVolumeMaterial subclass —
//      r184's shipped model has no `scatteringEmissiveNode`, and an emissive
//      body cannot be drawn without it.
//   2. Dye writes go to explicit texture OBJECTS via AB/BA pass pairs — on
//      r184, textureStore() through a storageTexture NODE silently writes
//      nowhere (velocity always worked because the example stores velocity
//      into objects; only dye went through the node).
//   3. computeAsync/renderAsync — headless deno needs the async paths.
//
// The sanctioned ADAPTATION (Skye's ask, search "ADAPTATION"): the emitter
// can run over area-weighted surface samples so ANY mesh can burn, not just
// a densely-tessellated teapot. With `emitterPoints: null` it dispatches over
// the mesh's raw vertex buffer exactly as the example does.
//
// USAGE (mirrors the example's scene):
//   const fire = await createVolumeFire(renderer, { mesh, keyLightPos });
//   scene.add(fire.volumeMesh, fire.shadowMesh);   // mesh gets fire.pointLight
//   const compose = createFireCompose(renderer, scene, camera, fire, [keyLight]);
//   await fire.warmup(4);
//   each frame: await fire.step(dt); await compose.renderAsync();

import * as THREE from 'three/webgpu';
import {
    vec3, vec4, uvec3, float, Fn, uniform,
    texture3D, textureStore, instanceIndex,
    screenCoordinate, pass,
    smoothstep, mix, min, max, floor,
    mx_noise_float, storage, If, cameraPosition, hue,
    Loop, positionWorld, positionLocal,
    interleavedGradientNoise, frameId, fract,
    saturation, cos, sin, atan,
    // ⚠R184(1): needed by the vendored lighting model
    property, modelRadius, cameraViewMatrix, cameraNear, cameraFar,
    linearDepth, viewZToPerspectiveDepth,
} from 'three/tsl';

import { snoise, snoiseVec3 } from './tsl_curl_noise.js';
import { ImprovedNoise } from 'npm:three@0.184.0/addons/math/ImprovedNoise.js';
import { gaussianBlur } from 'npm:three@0.184.0/addons/tsl/display/GaussianBlurNode.js';
import { bloom } from 'npm:three@0.184.0/addons/tsl/display/BloomNode.js';

// re-export for test scenes (scene scripts are eval'd and cannot bare-import)
export { TeapotGeometry } from 'npm:three@0.184.0/addons/geometries/TeapotGeometry.js';

// ════════════════════════════════════════════════════════════════════════
// ⚠R184(1) — VENDORED: src/nodes/functions/VolumetricLightingModel.js (dev),
// minus directRectArea (needs LTC_Evaluate_Volume, which r184 doesn't export).
// Delete this block the day our three ships `scatteringEmissiveNode`.
// ════════════════════════════════════════════════════════════════════════
const scatteringDensity = property('vec3');
const linearDepthRay = property('vec3');
const outgoingRayLight = property('vec3');

class VolumetricFireLightingModel extends THREE.LightingModel {

    start(builder) {
        const { material } = builder;

        const startPos = property('vec3');
        const endPos = property('vec3');
        const isFrontToBack = property('bool');

        If(cameraPosition.sub(positionWorld).length().greaterThan(modelRadius.mul(2)), () => {
            startPos.assign(cameraPosition);
            endPos.assign(positionWorld);
            isFrontToBack.assign(true);
        }).Else(() => {
            startPos.assign(positionWorld);
            endPos.assign(cameraPosition);
            isFrontToBack.assign(false);
        });

        const viewVector = endPos.sub(startPos);
        const steps = uniform('int').onRenderUpdate(({ material }) => material.steps);
        const stepSize = viewVector.length().div(steps).toVar();
        const rayDir = viewVector.normalize().toVar();
        const distTravelled = float(0.0).toVar();
        const transmittance = vec3(1).toVar();

        if (material.offsetNode) distTravelled.addAssign(material.offsetNode.mul(stepSize));

        Loop(steps, () => {
            const positionRay = startPos.add(rayDir.mul(distTravelled));
            const positionViewRay = cameraViewMatrix.mul(vec4(positionRay, 1)).xyz;

            if (material.depthNode !== null && material.depthNode !== undefined) {
                linearDepthRay.assign(linearDepth(
                    viewZToPerspectiveDepth(positionViewRay.z, cameraNear, cameraFar)));
                builder.context.sceneDepthNode = linearDepth(material.depthNode).toVar();
            }

            builder.context.positionWorld = positionRay;
            builder.context.shadowPositionWorld = positionRay;
            builder.context.positionView = positionViewRay;

            scatteringDensity.assign(0);

            let scatteringNode, scatteringEmissiveNode;
            if (material.scatteringNode) scatteringNode = material.scatteringNode({ positionRay });
            if (material.scatteringEmissiveNode) scatteringEmissiveNode = material.scatteringEmissiveNode({ positionRay });

            super.start(builder);

            if (scatteringNode) scatteringDensity.mulAssign(scatteringNode);

            const stepLight = scatteringDensity.mul(0.01).toVar();
            if (scatteringEmissiveNode) stepLight.addAssign(scatteringEmissiveNode.mul(0.01));

            // beer's law
            const falloff = scatteringDensity.mul(.01).negate().mul(stepSize).exp();

            If(isFrontToBack, () => {
                outgoingRayLight.addAssign(stepLight.mul(transmittance).mul(stepSize));
            }).Else(() => {
                outgoingRayLight.assign(outgoingRayLight.mul(falloff).add(stepLight.mul(stepSize)));
            });

            transmittance.mulAssign(falloff);
            distTravelled.addAssign(stepSize);
        });
    }

    scatteringLight(lightColor, builder) {
        const sceneDepthNode = builder.context.sceneDepthNode;
        if (sceneDepthNode) {
            If(sceneDepthNode.greaterThanEqual(linearDepthRay), () => {
                scatteringDensity.addAssign(lightColor);
            });
        } else {
            scatteringDensity.addAssign(lightColor);
        }
    }

    direct({ lightNode, lightColor }, builder) {
        // Ignore non-analytical lights and lights with infinite distance.
        // Consequence: Directional/Ambient contribute NOTHING to the volume —
        // the example's key light is a SpotLight for exactly this reason.
        if (lightNode.isAnalyticLightNode !== true || lightNode.light.distance === undefined) return;
        const directLight = lightColor.xyz.toVar();
        if (lightNode.shadowNode !== null && lightNode.shadowNode !== undefined) {
            directLight.mulAssign(lightNode.shadowNode);
        }
        this.scatteringLight(directLight, builder);
    }

    finish(builder) {
        builder.context.outgoingLight.assign(outgoingRayLight);
    }
}

class FireVolumeMaterial extends THREE.VolumeNodeMaterial {
    constructor(params) {
        super(params);
        this.scatteringEmissiveNode = null;   // the dev field r184 lacks
    }
    setupLightingModel() {
        return new VolumetricFireLightingModel();
    }
}

// ════════════════════════════════════════════════════════════════════════

export const VOLUMETRIC_LAYER = 10;

// The example's RUNTIME defaults: its `params` object + GUI wiring, not the
// raw uniform declarations (the GUI overrides several at startup).
const DEFAULTS = {
    gridSize: [100, 100, 200],
    worldSize: [12, 12, 24],
    pressureIterations: 2,        // example: "keep even! // default 6"
    steps: 16,                    // volumetricMaterial.steps in the example

    // params object (runtime)
    simSpeed: 1.2,
    fireLifespan: 1.3,            // uCooling = 1 / fireLifespan
    smokeLifespan: 3.5,           // uDissipation = 1 / smokeLifespan
    turbulence: 3.2,              // uTurbulence = turbulence / sqrt(simSpeed)
    fireStartColor: '#ffe68c',
    fireMidColor: '#ff7305',
    fireEndColor: '#ff0000',
    fireHue: 0,                   // degrees

    // sim uniforms (verbatim declarations)
    buoyancy: 3.0,
    weight: 0.15,
    turbulenceDecay: 0.1,
    turbFrequency: 10.0,
    velDamping: 0.25,
    emitDensity: 7.0,
    emitTemperature: 5.5,
    motionBoost: 0.25,
    windStrength: 6.5,
    emitterRadius: 1.0,           // wind bounding sphere (teapotRadius)

    // render uniforms (verbatim declarations)
    fireIntensity: 40.0,
    meshEmissiveIntensity: 0.2,   // uTeapotEmissiveIntensity
    fireGlowSpread: 5.0,
    shadowAbsorption: 2.0,
    shadowAmbient: 0.5,
    asymmetry: 0.0,
    powderStrength: 0.59,
    multiScattering: 1.0,
    pointLightVolumeIntensity: 2.0,
    pointLightSurfaceIntensity: 10.0,
    lightNearIntensity: 10.0,
    lightFarIntensity: 15.0,
    lightFarDistance: 10.0,
    projectionRadius: 20.0,
    projectionFrequency: 0.2,
    projectionNoiseFade: 17.0,
    projectionCenterFade: 3.25,
    saturationAmount: 1.1,        // uSaturation
    flameHeight: 3.5,

    // ADAPTATION: null = dispatch over the mesh's raw vertex buffer (the
    // example's exact emitter). A number = that many area-weighted surface
    // samples, so sparse meshes (a 150-vert cylinder, a GLB) emit correctly.
    emitterPoints: null,

    // video determinism: seconds of sim pre-rolled before frame 0 (the
    // example ignites live; its point light + mesh emissive fade in over the
    // first 3s of sim time, so ≥3 shows the established fire)
    warmupSeconds: 4.0,

    onTemporal: null,             // (simTime) => {} — the example rotates the
    // teapot here (rotation.y = time * 0.25)
};

// ADAPTATION helper — area-weighted surface samples across a whole hierarchy,
// seeded so re-renders are identical. Positions come out in the ROOT's local
// space (the emitter matrix maps them to world, like the example's vertices).
function sampleSurfacePoints(root, count, seed = 1) {
    root.updateWorldMatrix(true, true);
    const toLocal = new THREE.Matrix4().copy(root.matrixWorld).invert();

    const tris = [];
    const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
    const ab = new THREE.Vector3(), ac = new THREE.Vector3(), cr = new THREE.Vector3();
    const m = new THREE.Matrix4();

    root.traverse((o) => {
        if (!o.isMesh || !o.geometry?.attributes?.position) return;
        const g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry;
        const pos = g.attributes.position;
        m.copy(toLocal).multiply(o.matrixWorld);
        for (let t = 0; t + 2 < pos.count; t += 3) {
            a.fromBufferAttribute(pos, t).applyMatrix4(m);
            b.fromBufferAttribute(pos, t + 1).applyMatrix4(m);
            c.fromBufferAttribute(pos, t + 2).applyMatrix4(m);
            tris.push(a.clone(), b.clone(), c.clone());
        }
        if (g !== o.geometry) g.dispose();
    });

    const triCount = tris.length / 3;
    if (triCount === 0) throw new Error('[fluid_grid] nothing to burn: no meshes with positions');

    const cum = new Float32Array(triCount);
    let total = 0;
    for (let i = 0; i < triCount; i++) {
        const p0 = tris[i * 3], p1 = tris[i * 3 + 1], p2 = tris[i * 3 + 2];
        total += cr.crossVectors(ab.subVectors(p1, p0), ac.subVectors(p2, p0)).length() * 0.5;
        cum[i] = total;
    }

    let sd = seed >>> 0;
    const rnd = () => (((sd = (sd * 1664525 + 1013904223) >>> 0) >>> 8) / 16777216);
    const out = new Float32Array(count * 3);
    for (let n = 0; n < count; n++) {
        const r = rnd() * total;
        let lo = 0, hi = triCount - 1;
        while (lo < hi) { const mid = (lo + hi) >> 1; if (cum[mid] < r) lo = mid + 1; else hi = mid; }
        const p0 = tris[lo * 3], p1 = tris[lo * 3 + 1], p2 = tris[lo * 3 + 2];
        let u = rnd(), v = rnd();
        if (u + v > 1) { u = 1 - u; v = 1 - v; }
        out[n * 3] = p0.x + (p1.x - p0.x) * u + (p2.x - p0.x) * v;
        out[n * 3 + 1] = p0.y + (p1.y - p0.y) * u + (p2.y - p0.y) * v;
        out[n * 3 + 2] = p0.z + (p1.z - p0.z) * u + (p2.z - p0.z) * v;
    }
    return new THREE.StorageBufferAttribute(out, 3);
}

export async function createVolumeFire(renderer, options = {}) {
    const o = { ...DEFAULTS, ...options };
    const mesh = o.mesh;
    if (!mesh) throw new Error('[fluid_grid] options.mesh is required — the thing that burns');

    // ---------------------------------------------------------------
    // Globals (verbatim)
    // ---------------------------------------------------------------
    const [GRID_SIZE_X, GRID_SIZE_Y, GRID_SIZE_Z] = o.gridSize;
    const CELL_COUNT = GRID_SIZE_X * GRID_SIZE_Y * GRID_SIZE_Z;
    const PRESSURE_ITERATIONS = o.pressureIterations;
    const [VOLUME_WORLD_SIZE_X, VOLUME_WORLD_SIZE_Y, VOLUME_WORLD_SIZE_Z] = o.worldSize;
    const uVolumeWorldSize = uniform(new THREE.Vector3(VOLUME_WORLD_SIZE_X, VOLUME_WORLD_SIZE_Y, VOLUME_WORLD_SIZE_Z));
    const TEXEL_X = 1 / GRID_SIZE_X;
    const TEXEL_Y = 1 / GRID_SIZE_Y;
    const TEXEL_Z = 1 / GRID_SIZE_Z;

    const prevMeshPos = new THREE.Vector3();

    // sim uniforms (verbatim names; uTeapot* -> uEmitter*)
    const uDt = uniform(0.016);
    const uTime = uniform(0);

    const uBuoyancy = uniform(o.buoyancy);
    const uWeight = uniform(o.weight);
    const uTurbulence = uniform(o.turbulence);
    const uTurbulenceDecay = uniform(o.turbulenceDecay);
    const uTurbFrequency = uniform(o.turbFrequency);
    const uVelDamping = uniform(o.velDamping);

    const uCooling = uniform(1.0);
    const uDissipation = uniform(0.4);

    const uEmitDensity = uniform(o.emitDensity);
    const uEmitTemperature = uniform(o.emitTemperature);

    const uEmitterMatrix = uniform(new THREE.Matrix4());
    const uEmitterSpeed = uniform(0.0);
    const uMotionBoost = uniform(o.motionBoost);
    const uEmitterVelocity = uniform(new THREE.Vector3());
    const uWindStrength = uniform(o.windStrength);
    const uEmitterPosition = uniform(new THREE.Vector3());

    // render uniforms (verbatim)
    const uFireIntensity = uniform(o.fireIntensity);
    const uMeshEmissiveIntensity = uniform(o.meshEmissiveIntensity);
    const uFireGlowSpread = uniform(o.fireGlowSpread);
    const uShadowAbsorption = uniform(o.shadowAbsorption);
    const uShadowAmbient = uniform(o.shadowAmbient);
    const uFireStartColor = uniform(new THREE.Color(o.fireStartColor));
    const uFireMidColor = uniform(new THREE.Color(o.fireMidColor));
    const uFireEndColor = uniform(new THREE.Color(o.fireEndColor));
    const uFireHue = uniform(THREE.MathUtils.degToRad(o.fireHue));
    const uAsymmetry = uniform(o.asymmetry);
    const uPowderStrength = uniform(o.powderStrength);
    const uMultiScattering = uniform(o.multiScattering);
    const uPointLightVolumeIntensity = uniform(o.pointLightVolumeIntensity);
    const uPointLightSurfaceIntensity = uniform(o.pointLightSurfaceIntensity);
    const uLightNearIntensity = uniform(o.lightNearIntensity);
    const uLightFarIntensity = uniform(o.lightFarIntensity);
    const uLightFarDistance = uniform(o.lightFarDistance);
    const uPointLightProjectionRadius = uniform(o.projectionRadius);
    const uPointLightProjectionFrequency = uniform(o.projectionFrequency);
    const uPointLightProjectionNoiseFade = uniform(o.projectionNoiseFade);
    const uPointLightProjectionCenterFade = uniform(o.projectionCenterFade);
    const uSaturation = uniform(o.saturationAmount);

    const uFlameHeight = uniform(o.flameHeight);
    const uSway = uniform(new THREE.Vector3());
    const uFlicker = uniform(1.0);
    const uColorNoise = uniform(0.0);
    const cpuNoise = new ImprovedNoise();

    // key light position — uniform() over the live Vector3, as the example
    const uKeyLightPos = uniform(o.keyLightPos ?? new THREE.Vector3(
        -3 * (VOLUME_WORLD_SIZE_X / 8),
        6 * (VOLUME_WORLD_SIZE_Y / 8) + VOLUME_WORLD_SIZE_Y / 2 + 0.4,
        3 * (VOLUME_WORLD_SIZE_Z / 8)));

    // ---------------------------------------------------------------
    // Storage 3D textures (verbatim createStorage3D)
    // ---------------------------------------------------------------
    function createStorage3D(name) {
        const texture = new THREE.Storage3DTexture(GRID_SIZE_X, GRID_SIZE_Y, GRID_SIZE_Z);
        texture.name = name;
        texture.format = THREE.RGBAFormat;
        texture.type = THREE.HalfFloatType; // rgba16float -> storage-writable + linearly filterable
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.wrapR = THREE.ClampToEdgeWrapping;
        return texture;
    }

    const velTexA = createStorage3D('velocity A');
    const velTexB = createStorage3D('velocity B');
    const dyeTexA = createStorage3D('dye A');
    const dyeTexB = createStorage3D('dye B');
    const divTex = createStorage3D('divergence');
    const pressTexA = createStorage3D('pressure A');
    const pressTexB = createStorage3D('pressure B');
    const curlNoiseTex = createStorage3D('curlNoise');
    curlNoiseTex.wrapS = THREE.RepeatWrapping;
    curlNoiseTex.wrapT = THREE.RepeatWrapping;
    curlNoiseTex.wrapR = THREE.RepeatWrapping;

    // ⚠R184(2): reads go through this swapping node exactly as the example's
    // do; but there is NO dyeTexWriteNode — writes must hit texture OBJECTS,
    // so every dye-writing pass below exists as an AB/BA pair.
    const dyeTexNode = texture3D(dyeTexA);
    const curlNoiseTexNode = texture3D(curlNoiseTex);
    let dyeInA = true;

    // ---------------------------------------------------------------
    // TSL helpers shared by the compute kernels (verbatim)
    // ---------------------------------------------------------------
    const getVoxelCoord = (id) => {
        const x = id.mod(GRID_SIZE_X);
        const y = id.div(GRID_SIZE_X).mod(GRID_SIZE_Y);
        const z = id.div(GRID_SIZE_X * GRID_SIZE_Y);
        return uvec3(x, y, z);
    };
    const coordToUVW = (coord) => vec3(coord).add(0.5).div(vec3(GRID_SIZE_X, GRID_SIZE_Y, GRID_SIZE_Z));

    // ---------------------------------------------------------------
    // Fluid simulation - compute kernels (verbatim)
    // ---------------------------------------------------------------

    // 0) Precompute curl noise into 3D storage texture
    const computeCurlNoisePass = Fn(() => {
        const coord = getVoxelCoord(instanceIndex);
        const uvw = coordToUVW(coord);

        const freq = uTurbFrequency; // 10.0
        const e = float(0.1).div(freq);
        const dx = vec3(e, 0.0, 0.0);
        const dy = vec3(0.0, e, 0.0);
        const dz = vec3(0.0, 0.0, e);

        const p = uvw.mul(vec3(VOLUME_WORLD_SIZE_X / VOLUME_WORLD_SIZE_Y, 1.0, VOLUME_WORLD_SIZE_Z / VOLUME_WORLD_SIZE_Y));
        const p_x0 = snoiseVec3(p.sub(dx).mul(freq));
        const p_x1 = snoiseVec3(p.add(dx).mul(freq));
        const p_y0 = snoiseVec3(p.sub(dy).mul(freq));
        const p_y1 = snoiseVec3(p.add(dy).mul(freq));
        const p_z0 = snoiseVec3(p.sub(dz).mul(freq));
        const p_z1 = snoiseVec3(p.add(dz).mul(freq));

        const x = p_y1.z.sub(p_y0.z).sub(p_z1.y).add(p_z0.y);
        const y = p_z1.x.sub(p_z0.x).sub(p_x1.z).add(p_x0.z);
        const z = p_x1.y.sub(p_x0.y).sub(p_y1.x).add(p_y0.x);

        // Analytical curlNoise multiplier is 1.0 / (2.0 * e) = 5.0 (since e = 0.1)
        const noiseVal = vec3(x, y, z).mul(5.0);

        textureStore(curlNoiseTex, coord, vec4(noiseVal, 0.0)).toWriteOnly();
    })().compute(CELL_COUNT).setName('computeCurlNoise');

    // 1) Advect velocity + external forces (buoyancy, weight, turbulence)
    //    read: velTexA, dyeTexNode -> write: velTexB
    const advectVelocityPass = Fn(() => {
        const coord = getVoxelCoord(instanceIndex);
        const uvw = coordToUVW(coord);

        const vel = texture3D(velTexA, uvw, 0).xyz;

        // semi-Lagrangian advection: look back along the velocity
        const velUVW = vel.div(uVolumeWorldSize);
        const prevPos = uvw.sub(velUVW.mul(uDt));
        const newVel = texture3D(velTexA, prevPos, 0).xyz.toVar();

        const dye = dyeTexNode.sample(uvw).level(0);
        const density = dye.r;
        const temperature = dye.g;
        const age = dye.b;

        // buoyancy (hot rises) vs smoke weight (cold falls)
        const buoyancyForce = temperature.mul(uBuoyancy).sub(density.mul(uWeight)).mul(VOLUME_WORLD_SIZE_Y);
        newVel.addAssign(vec3(0, buoyancyForce, 0).mul(uDt));

        // turbulence: divergence-free noise force
        // 1) Thermal/Convective turbulence: stronger where it's hot, decaying over age
        const thermalNoisePos = uvw.add(vec3(0, age.negate().mul(0.6), age.mul(0.13)).div(uTurbFrequency));
        const decay = age.mul(uTurbulenceDecay.negate()).exp();
        const thermalTurbulence = curlNoiseTexNode.sample(thermalNoisePos).level(0).xyz.mul(uTurbulence).mul(temperature).mul(decay);

        // 2) Ambient/Atmospheric turbulence: lower frequency, weaker, acts on
        //    the smoke density (even when cooled down); uses uTime so it
        //    animates continuously regardless of age
        const ambientNoisePos = uvw.mul(0.5).add(vec3(0, uTime.mul(0.25), uTime.mul(0.06)).div(uTurbFrequency));
        const ambientTurbulence = curlNoiseTexNode.sample(ambientNoisePos).level(0).xyz.mul(uTurbulence.mul(0.2)).mul(density);

        const turbulence = thermalTurbulence.add(ambientTurbulence).mul(VOLUME_WORLD_SIZE_Y);
        newVel.addAssign(turbulence.mul(uDt));

        // damping
        newVel.mulAssign(max(float(1).sub(uVelDamping.mul(uDt)), 0));

        // Wind effect: bounding sphere around the burning mesh
        const worldPos = uvw.sub(0.5).mul(uVolumeWorldSize).add(vec3(0, VOLUME_WORLD_SIZE_Y / 2, 0));
        const dist = worldPos.distance(uEmitterPosition);
        const emitterRadius = float(o.emitterRadius);

        If(dist.lessThan(emitterRadius), () => {
            const ratio = dist.div(emitterRadius);
            const falloff = smoothstep(0.0, 1.0, float(1.0).sub(ratio));

            // Wind turbulence scales with uTurbulence and mesh speed
            const windNoisePos = uvw.add(vec3(0.0, uTime.mul(0.5), 0.0).div(uTurbFrequency));
            const windTurbulence = curlNoiseTexNode.sample(windNoisePos).level(0).xyz.mul(uTurbulence).mul(uEmitterSpeed);

            const windVel = uEmitterVelocity.mul(uWindStrength).add(windTurbulence).mul(uDt).mul(falloff);

            newVel.addAssign(windVel);
        });

        // fade velocity near the volume borders (soft boundary condition)
        const edge = min(uvw, vec3(1).sub(uvw));
        const boundary = smoothstep(0.0, 0.08, min(edge.x, min(edge.y, edge.z)));
        newVel.mulAssign(boundary);

        textureStore(velTexB, coord, vec4(newVel, 0)).toWriteOnly();
    })().compute(CELL_COUNT).setName('advectVelocity');

    // 2) Divergence of the advected velocity — read: velTexB -> write: divTex
    const divergencePass = Fn(() => {
        const coord = getVoxelCoord(instanceIndex);
        const uvw = coordToUVW(coord);

        const vR = texture3D(velTexB, uvw.add(vec3(TEXEL_X, 0, 0)), 0).x;
        const vL = texture3D(velTexB, uvw.sub(vec3(TEXEL_X, 0, 0)), 0).x;
        const vU = texture3D(velTexB, uvw.add(vec3(0, TEXEL_Y, 0)), 0).y;
        const vD = texture3D(velTexB, uvw.sub(vec3(0, TEXEL_Y, 0)), 0).y;
        const vF = texture3D(velTexB, uvw.add(vec3(0, 0, TEXEL_Z)), 0).z;
        const vB = texture3D(velTexB, uvw.sub(vec3(0, 0, TEXEL_Z)), 0).z;

        const divergence = vR.sub(vL).add(vU.sub(vD)).add(vF.sub(vB)).mul(0.5);

        textureStore(divTex, coord, vec4(divergence, 0, 0, 0)).toWriteOnly();
    })().compute(CELL_COUNT).setName('divergence');

    // 3) Jacobi pressure solve (ping-pong A <-> B)
    const jacobi = (pressRead, pressWrite, name) => Fn(() => {
        const coord = getVoxelCoord(instanceIndex);
        const uvw = coordToUVW(coord);

        const pR = texture3D(pressRead, uvw.add(vec3(TEXEL_X, 0, 0)), 0).x;
        const pL = texture3D(pressRead, uvw.sub(vec3(TEXEL_X, 0, 0)), 0).x;
        const pU = texture3D(pressRead, uvw.add(vec3(0, TEXEL_Y, 0)), 0).x;
        const pD = texture3D(pressRead, uvw.sub(vec3(0, TEXEL_Y, 0)), 0).x;
        const pF = texture3D(pressRead, uvw.add(vec3(0, 0, TEXEL_Z)), 0).x;
        const pB = texture3D(pressRead, uvw.sub(vec3(0, 0, TEXEL_Z)), 0).x;

        const divergence = texture3D(divTex, uvw, 0).x;

        const pressure = pR.add(pL).add(pU).add(pD).add(pF).add(pB).sub(divergence).div(6);

        textureStore(pressWrite, coord, vec4(pressure, 0, 0, 0)).toWriteOnly();
    })().compute(CELL_COUNT).setName(name);

    const jacobiPassAB = jacobi(pressTexA, pressTexB, 'jacobiAB');
    const jacobiPassBA = jacobi(pressTexB, pressTexA, 'jacobiBA');

    // 4) Project: subtract pressure gradient -> divergence-free velocity
    //    read: velTexB, pressTexA -> write: velTexA (final velocity)
    const projectPass = Fn(() => {
        const coord = getVoxelCoord(instanceIndex);
        const uvw = coordToUVW(coord);

        const pR = texture3D(pressTexA, uvw.add(vec3(TEXEL_X, 0, 0)), 0).x;
        const pL = texture3D(pressTexA, uvw.sub(vec3(TEXEL_X, 0, 0)), 0).x;
        const pU = texture3D(pressTexA, uvw.add(vec3(0, TEXEL_Y, 0)), 0).x;
        const pD = texture3D(pressTexA, uvw.sub(vec3(0, TEXEL_Y, 0)), 0).x;
        const pF = texture3D(pressTexA, uvw.add(vec3(0, 0, TEXEL_Z)), 0).x;
        const pB = texture3D(pressTexA, uvw.sub(vec3(0, 0, TEXEL_Z)), 0).x;

        const gradient = vec3(pR.sub(pL), pU.sub(pD), pF.sub(pB)).mul(0.5);

        const vel = texture3D(velTexB, uvw, 0).xyz.sub(gradient);

        textureStore(velTexA, coord, vec4(vel, 0)).toWriteOnly();
    })().compute(CELL_COUNT).setName('project');

    // 5) Advect density / temperature — ⚠R184(2): AB/BA pair over objects
    const makeAdvectDye = (dyeDst, name) => Fn(() => {
        const coord = getVoxelCoord(instanceIndex);
        const uvw = coordToUVW(coord);

        const vel = texture3D(velTexA, uvw, 0).xyz;
        const velUVW = vel.div(uVolumeWorldSize);
        const prevPos = uvw.sub(velUVW.mul(uDt));

        const dye = dyeTexNode.sample(prevPos).level(0);

        const density = dye.r.mul(max(float(1).sub(uDissipation.mul(uDt)), 0)).toVar();
        const temperature = dye.g.mul(max(float(1).sub(uCooling.mul(uDt)), 0)).toVar();

        // Nearest neighbor lookup for age to prevent numerical diffusion
        const gridDims = vec3(GRID_SIZE_X, GRID_SIZE_Y, GRID_SIZE_Z);
        const nearestUVW = floor(prevPos.mul(gridDims)).add(0.5).div(gridDims);
        const age = dyeTexNode.sample(nearestUVW).level(0).b.add(uDt).toVar();

        temperature.assign(temperature.clamp(0, 12));

        If(density.lessThanEqual(0.01), () => {
            age.assign(0.0);
        });

        textureStore(dyeDst, coord, vec4(density, temperature, age, 1.0)).toWriteOnly();
    })().compute(CELL_COUNT).setName(name);

    const advectDyeAB = makeAdvectDye(dyeTexB, 'advectDyeAB');
    const advectDyeBA = makeAdvectDye(dyeTexA, 'advectDyeBA');

    // 6) Emit density/temperature from the mesh — verbatim emitTeapotPass,
    //    generalized to any positions buffer. ⚠R184(2): AB/BA pair.
    let positionsAttr;
    if (o.emitterPoints == null) {
        // the example's exact emitter: the mesh's own vertex buffer
        const geo = mesh.geometry;
        if (!geo) throw new Error('[fluid_grid] emitterPoints:null needs mesh.geometry');
        const src = geo.attributes.position;
        // ⚠R184: storage() wants a StorageBufferAttribute here
        positionsAttr = src.isStorageBufferAttribute ? src
            : new THREE.StorageBufferAttribute(new Float32Array(src.array), 3);
    } else {
        positionsAttr = sampleSurfacePoints(mesh, o.emitterPoints);   // ADAPTATION
    }
    const vertexCount = positionsAttr.count;
    const verticesBuffer = storage(positionsAttr, 'vec3', vertexCount).toReadOnly();
    console.log('[fluid_grid] emitter:', vertexCount, 'points',
        o.emitterPoints == null ? '(raw vertex buffer, as the example)' : '(area-weighted surface samples)');

    const makeEmit = (dyeDst, name) => Fn(() => {
        const vertexPos = verticesBuffer.element(instanceIndex);
        const worldPos = uEmitterMatrix.mul(vec4(vertexPos, 1.0)).xyz;

        // Map world position to volume box UVW space [0..1]
        const uvw = worldPos.sub(vec3(0, VOLUME_WORLD_SIZE_Y / 2, 0)).div(uVolumeWorldSize).add(0.5);

        // Check boundary
        If(uvw.x.greaterThanEqual(0).and(uvw.x.lessThanEqual(1))
            .and(uvw.y.greaterThanEqual(0)).and(uvw.y.lessThanEqual(1))
            .and(uvw.z.greaterThanEqual(0)).and(uvw.z.lessThanEqual(1)), () => {

            const coord = uvec3(uvw.mul(vec3(GRID_SIZE_X, GRID_SIZE_Y, GRID_SIZE_Z)));

            // Add flicker / animated noise based on local vertex position
            const flicker = mx_noise_float(vertexPos.mul(9.0).add(vec3(0.0, uTime.negate().mul(2.5), uTime.mul(0.7)))).mul(0.5).add(0.5);

            // Baseline emission depends on temperature rate (0 if temperature is 0)
            const baseEmission = uEmitTemperature.greaterThan(0.0).select(float(1.0), float(0.0));

            // Movement-based emission (boost) scales with speed
            const movementEmission = uEmitterSpeed.mul(uMotionBoost);

            // Unified emission factor (includes movement boost)
            const emissionFactor = baseEmission.add(movementEmission);

            const densityVal = uEmitDensity.mul(float(1 / 120)).mul(flicker.mul(0.85).add(0.15)).mul(emissionFactor);

            If(densityVal.greaterThan(0.0), () => {
                const tempVal = uEmitTemperature.mul(float(1 / 120)).mul(flicker.mul(0.85).add(0.15)).mul(emissionFactor);

                // Read current dye and add emission
                const currentDye = dyeTexNode.sample(uvw).level(0);
                const newDensity = currentDye.r.add(densityVal);
                const newTemp = currentDye.g.add(tempVal).clamp(0.0, 12.0);

                const currentAge = currentDye.b;
                const newAge = mix(currentAge, float(0.0), densityVal.div(max(newDensity, 0.001)));

                textureStore(dyeDst, coord, vec4(newDensity, newTemp, newAge, 1.0)).toWriteOnly();
            });
        });
    })().compute(vertexCount).setName(name);

    const emitAB = makeEmit(dyeTexB, 'emitAB');
    const emitBA = makeEmit(dyeTexA, 'emitBA');

    // Precompute curl noise on the GPU
    await renderer.computeAsync(computeCurlNoisePass);

    // ---------------------------------------------------------------
    // Volumetric material - ray marches the simulated 3D texture (verbatim)
    // ---------------------------------------------------------------
    const volumetricMaterial = new FireVolumeMaterial();   // ⚠R184(1)
    volumetricMaterial.steps = o.steps;
    volumetricMaterial.transparent = true;
    volumetricMaterial.blending = THREE.AdditiveBlending;
    volumetricMaterial.depthWrite = false;

    // Dithering to reduce banding
    volumetricMaterial.offsetNode = fract(interleavedGradientNoise(screenCoordinate).add(float(frameId).mul(0.618033988749895)));

    // blackbody-style fire ramp: start color -> mid color -> end color
    const fireRamp = Fn(([t]) => {
        const color = vec3(0).toVar();
        color.assign(mix(vec3(0.0, 0.0, 0.0), uFireEndColor, smoothstep(0.05, 0.35, t)));
        color.assign(mix(color, uFireMidColor, smoothstep(0.35, 0.65, t)));
        color.assign(mix(color, uFireStartColor, smoothstep(0.65, 1.0, t)));
        return color;
    });

    const henyeyGreenstein = Fn(([cosTheta, g]) => {
        const g2 = g.mul(g);
        const denom = float(1.0).add(g2).sub(float(2.0).mul(g).mul(cosTheta));
        const oneMinusG2 = float(1.0).sub(g2);
        // Normalization constant 1 / (4 * PI) is approx 0.079577
        return oneMinusG2.div(denom.pow(1.5)).mul(0.079577);
    });

    const getVolumeSample = ({ positionRay }) => {
        // volume box is shifted up -> map ray position to uvw [0..1]
        const uvw = positionRay.sub(vec3(0, VOLUME_WORLD_SIZE_Y / 2, 0)).div(uVolumeWorldSize).add(0.5).toVar();

        // 1) Domain Warping: distort coordinates using velocity field
        const noiseDistortion = texture3D(velTexA, uvw, 0).xyz.div(uVolumeWorldSize).mul(0.15);
        const distortedUVW = uvw.add(noiseDistortion).clamp(0.0, 1.0).toVar();

        const sample = dyeTexNode.sample(distortedUVW).level(0);

        const density = sample.r;
        const age = sample.b;
        const temperature = sample.g;

        // 2) High-frequency detail noise modulation
        const detailNoise = snoise(positionRay.mul(5.5).add(vec3(0, age.mul(0.8).negate(), 0)));
        density.mulAssign(detailNoise.mul(0.35).add(0.85));

        // soften the box edges
        const edge = min(distortedUVW, vec3(1).sub(distortedUVW));
        density.mulAssign(smoothstep(0.0, 0.06, min(edge.x, min(edge.y, edge.z))));

        return { density, temperature, age, distortedUVW };
    };

    volumetricMaterial.scatteringNode = Fn(({ positionRay }) => {
        const { density } = getVolumeSample({ positionRay });

        // 3) Key-light Self-Shadowing: raymarch towards uKeyLightPos
        const lightDir = uKeyLightPos.sub(positionRay).normalize();
        const shadowDensitySum = float(0.0).toVar();
        const shadowStepSize = 0.35;

        for (let i = 0; i < 2; i++) { // default 5
            const stepDist = (i + 0.5) * shadowStepSize;
            const shadowPos = positionRay.add(lightDir.mul(stepDist));
            const shadowUVW = shadowPos.sub(vec3(0, VOLUME_WORLD_SIZE_Y / 2, 0)).div(uVolumeWorldSize).add(0.5);

            // Fade out shadow density near the volume borders
            const shadowEdge = min(shadowUVW, vec3(1).sub(shadowUVW));
            const shadowFade = smoothstep(0.0, 0.06, min(shadowEdge.x, min(shadowEdge.y, shadowEdge.z)));

            const shadowSample = texture3D(dyeTexA, shadowUVW, 0).r.mul(shadowFade);
            shadowDensitySum.addAssign(shadowSample);
        }

        // Calculate optical thickness (tau)
        const tau = shadowDensitySum.mul(shadowStepSize).mul(uShadowAbsorption);
        const beer = tau.negate().exp();

        // Multiple Scattering Approximation (Octave 2)
        const multiScatter = tau.mul(0.25).negate().exp().mul(0.5);

        // Blend between single and multiple scattering
        const baseTransmittance = mix(beer, beer.add(multiScatter), uMultiScattering);

        // Beer's Law Powder Effect: edge self-shadowing details
        const powder = float(1.0).sub(tau.mul(2.0).negate().exp());
        const finalTransmittance = mix(baseTransmittance, baseTransmittance.mul(powder), uPowderStrength);

        // Apply ambient light in shadowed regions
        const lightTransmittance = finalTransmittance.add(uShadowAmbient).clamp(0.0, 1.0);

        // Henyey-Greenstein Phase Function for directional scattering
        const viewDir = cameraPosition.sub(positionRay).normalize();
        const cosTheta = viewDir.dot(lightDir).clamp(-1.0, 1.0);
        const phase = henyeyGreenstein(cosTheta, uAsymmetry);

        // Multiply phase by 4 * PI (approx 12.56637) to keep standard scale
        const smokeScattering = vec3(density).mul(lightTransmittance).mul(phase.mul(12.56637));

        return smokeScattering;
    });

    volumetricMaterial.scatteringEmissiveNode = Fn(({ positionRay }) => {
        const { density, temperature } = getVolumeSample({ positionRay });

        // fire "emission" (boosted scattering tinted by temperature)
        // (inverted: higher spread = lower power)
        const firePower = float(6.0).sub(uFireGlowSpread);
        const fire = fireRamp(temperature.clamp(0, 1)).mul(temperature.pow(firePower)).mul(uFireIntensity);

        // Apply hue rotation to the fire color
        const fireColor = hue(fire, uFireHue);

        // Simulate the spotlight distance attenuation (constant intensity 400)
        const distance = positionRay.sub(uKeyLightPos).length();
        const attenuation = float(400.0).div(distance.pow(2.0));

        return fireColor.mul(density.add(0.15)).mul(attenuation);
    });

    const volumeMesh = new THREE.Mesh(
        new THREE.BoxGeometry(VOLUME_WORLD_SIZE_X, VOLUME_WORLD_SIZE_Y, VOLUME_WORLD_SIZE_Z),
        volumetricMaterial);
    volumeMesh.position.y = VOLUME_WORLD_SIZE_Y / 2 + 0.4;
    volumeMesh.receiveShadow = true;
    volumeMesh.frustumCulled = false;
    volumeMesh.layers.disableAll();
    volumeMesh.layers.enable(VOLUMETRIC_LAYER);

    // the volume casts a soft shadow on the floor (verbatim volumeCastShadow)
    const volumeCastShadow = Fn(() => {
        const startPos = positionWorld;
        const lightDir = positionWorld.sub(cameraPosition).normalize();

        const steps = uniform('int').onRenderUpdate(({ material, object }) =>
            material.steps || (object && object.material && object.material.steps) || volumetricMaterial.steps);
        const VOLUME_WORLD_SIZE_DIAGONAL = Math.sqrt(VOLUME_WORLD_SIZE_X ** 2 + VOLUME_WORLD_SIZE_Y ** 2 + VOLUME_WORLD_SIZE_Z ** 2);
        const maxDistance = float(VOLUME_WORLD_SIZE_DIAGONAL);
        const stepSize = maxDistance.div(steps).toVar();
        const rayDir = lightDir.toVar();

        const distTravelled = float(0.0).toVar();
        const transmittance = float(1.0).toVar();

        Loop(steps, () => {
            const positionRay = startPos.add(rayDir.mul(distTravelled));
            const { density } = getVolumeSample({ positionRay });
            const absorption = density.mul(uShadowAbsorption).mul(0.01);
            const falloff = absorption.negate().mul(stepSize).exp();
            transmittance.mulAssign(falloff);
            distTravelled.addAssign(stepSize);
        });

        // If the ray is completely transparent, discard the fragment
        transmittance.greaterThanEqual(0.99).discard();

        const shadowOpacity = transmittance.oneMinus();
        return vec4(vec3(0), shadowOpacity.mul(5));
    });

    // FireVolumeMaterial, not a bare VolumeNodeMaterial: this mesh only casts the volume's shadow (colorWrite
    // off), but it still runs the lit main pass, and three's own VolumetricLightingModel multiplies every light by
    // its shadowNode unguarded — for the fire's own point light (no shadow map) that compiles to `* null` and the
    // pipeline is invalid. The fire's model needs no shadow term (see VolumetricFireLightingModel.direct).
    const shadowMaterial = new FireVolumeMaterial();
    shadowMaterial.steps = volumetricMaterial.steps;
    shadowMaterial.offsetNode = volumetricMaterial.offsetNode;
    shadowMaterial.castShadowNode = volumeCastShadow();
    shadowMaterial.shadowSide = THREE.FrontSide;
    shadowMaterial.colorWrite = false;
    shadowMaterial.depthWrite = false;
    shadowMaterial.blending = THREE.CustomBlending;
    shadowMaterial.blendEquation = THREE.AddEquation;
    shadowMaterial.blendSrc = THREE.ZeroFactor;
    shadowMaterial.blendDst = THREE.OneMinusSrcAlphaFactor;
    shadowMaterial.blendEquationAlpha = THREE.AddEquation;
    shadowMaterial.blendSrcAlpha = THREE.OneFactor;
    shadowMaterial.blendDstAlpha = THREE.OneMinusSrcAlphaFactor;

    const shadowMesh = new THREE.Mesh(
        new THREE.BoxGeometry(VOLUME_WORLD_SIZE_X, VOLUME_WORLD_SIZE_Y, VOLUME_WORLD_SIZE_Z),
        shadowMaterial);
    shadowMesh.position.y = VOLUME_WORLD_SIZE_Y / 2 + 0.4;
    shadowMesh.castShadow = true;
    shadowMesh.frustumCulled = false;

    // ---------------------------------------------------------------
    // The fire's point light (verbatim pointLightColor, incl. sway/flicker/
    // colorNoise, isVolume split, near/far scale and floor projection noise)
    // ---------------------------------------------------------------
    const isVolume = Fn(({ material }) => {
        const isVolumeMaterial = material && material.isVolumeNodeMaterial;
        return float(isVolumeMaterial ? 1.0 : 0.0);
    })();

    const pointLightColor = Fn(() => {
        // Shading point position in world space
        const P = positionWorld;

        // Light source bottom position (the burning mesh's position)
        const A = uEmitterPosition;

        // 1. Flame column height
        const H = vec3(0.0, uFlameHeight, 0.0);

        // Closest point on vertical segment (displaced by sway)
        const V = P.sub(A);
        const t = V.dot(H).div(H.dot(H)).clamp(0.0, 1.0);
        const C = A.add(uSway).add(H.mul(t));
        const distToSegment = P.sub(C).length();

        // Soft cylindrical attenuation (flame thickness radius r = 1.2)
        const r = float(1.2);
        const softAttenuation = float(1.0).div(distToSegment.pow(2.0).add(r.pow(2.0)));

        // Recreate standard PointLight distance attenuation for cancellation
        const distToLight = P.sub(A).length();
        const decayExponent = float(2.0);
        const defaultAttenuation = distToLight.pow(decayExponent).max(0.01).reciprocal();

        // Cancel default attenuation only when shading the volume
        const attenuationCorrection = isVolume.equal(1.0).select(
            softAttenuation.div(defaultAttenuation),
            float(1.0));

        const currentIntensity = isVolume.equal(1.0).select(uPointLightVolumeIntensity, uPointLightSurfaceIntensity);

        // 4. Color temperature oscillation
        const colorT = uEmitTemperature.div(8.34).mul(0.5).add(0.20).add(uColorNoise).clamp(0.0, 1.0);
        const fireColor = fireRamp(colorT);
        const coloredFire = hue(saturation(fireColor, uSaturation), uFireHue);

        // 5. Projected fire light color on surfaces
        const relP = P.xz.sub(A.xz);
        const angle = atan(relP.y, relP.x);
        const distXZ = relP.length();

        // Radial ray/spoke noise that rotates/flickers over time
        const freqScale = uPointLightProjectionFrequency;
        const angleNoise = mx_noise_float(vec3(cos(angle).mul(float(1.5).mul(freqScale)), sin(angle).mul(float(1.5).mul(freqScale)), uTime.mul(0.6))).mul(0.5).add(0.5);

        // Fade the spoke noise near the center (atan(0,0) seam singularity)
        const centerFadeFactor = smoothstep(0.0, uPointLightProjectionCenterFade, distXZ);
        const cleanAngleNoise = mix(float(1.0), angleNoise, centerFadeFactor);

        // Spatial noise moving outwards/upwards (convective fire behavior)
        const noiseCoord1 = vec3(P.x.mul(float(0.6).mul(freqScale)), uTime.mul(1.2), P.z.mul(float(0.6).mul(freqScale)));
        const projN1 = mx_noise_float(noiseCoord1).mul(0.5).add(0.5);

        const noiseCoord2 = vec3(P.x.mul(float(1.5).mul(freqScale)), uTime.mul(2.5), P.z.mul(float(1.5).mul(freqScale)));
        const projN2 = mx_noise_float(noiseCoord2).mul(0.5).add(0.5);

        const projNoise = projN1.mul(0.65).add(projN2.mul(0.35));

        // Modulate by radial spoke pattern
        const projectionIntensity = projNoise.mul(cleanAngleNoise.mul(0.5).add(0.5));

        // Fade the noise over distance (blend to uniform 1.0)
        const noiseFadeFactor = distToSegment.div(uPointLightProjectionNoiseFade).clamp(0.0, 1.0);
        const finalIntensity = mix(projectionIntensity, float(1.0), noiseFadeFactor);

        // Radial temperature gradient from the fire center
        const radialTemp = float(1.0).sub(distToSegment.div(uPointLightProjectionRadius)).clamp(0.0, 1.0);

        const colorTProj = radialTemp.mul(finalIntensity).clamp(0.0, 1.0);
        const fireColorProj = fireRamp(colorTProj);
        const coloredFireProj = hue(saturation(fireColorProj, uSaturation), uFireHue);

        // Uniform fire color (volume) vs projected fire color (surface)
        const finalFireColor = isVolume.equal(1.0).select(coloredFire, coloredFireProj);

        // Stefan-Boltzmann: radiant energy proportional to T^4
        const tempScale = uEmitTemperature.div(8.34).max(0.0);
        const tempFactor = tempScale.pow(4.0);

        // Scale by uEmitDensity (relative to default 11.02)
        const densityScale = uEmitDensity.div(11.02).max(0.0);

        // Smooth fade-in of point light intensity over the first 3 seconds
        const fadeIn = smoothstep(0.0, 3.0, uTime);

        const baseColor = finalFireColor.mul(tempFactor).mul(densityScale).mul(uFireIntensity).mul(currentIntensity).mul(uFlicker).mul(fadeIn);

        // Blend between near and far light intensity scales
        const distRatio = distToSegment.div(uLightFarDistance).clamp(0.0, 1.0);
        const distanceScale = mix(uLightNearIntensity, uLightFarIntensity, smoothstep(0.0, 1.0, distRatio));

        // Distance-based scaling only when shading the volumetric smoke
        const finalScale = isVolume.equal(1.0).select(distanceScale, float(1.0));

        return baseColor.mul(attenuationCorrection).mul(finalScale);
    })();

    const pointLight = new THREE.PointLight(0xffffff, 1, 100, 2);
    pointLight.colorNode = pointLightColor;
    pointLight.position.set(0, 0, 0);
    pointLight.castShadow = false;
    mesh.add(pointLight);   // the example: teapot.add(pointLight)
    pointLight.layers.enable(VOLUMETRIC_LAYER);

    // Lava-crack emissive for the burning mesh (verbatim teapot emissiveNode)
    function makeLavaEmissive() {
        return Fn(() => {
            // Lava flow animation using local position for stability
            const p = positionLocal.mul(0.5);
            const flow = vec3(0.0, uTime.negate(), 0.0);

            const n1 = mx_noise_float(p.add(flow)).mul(0.5).add(0.5);
            const p2 = p.mul(2.0).sub(flow.mul(1.5));
            const n2 = mx_noise_float(p2.add(vec3(n1.mul(0.4)))).mul(0.5).add(0.5);
            const p3 = p.mul(4.0).add(flow.mul(2.5));
            const n3 = mx_noise_float(p3).mul(0.5).add(0.5);

            const noiseVal = n1.mul(0.50).add(n2.mul(0.35)).add(n3.mul(0.15));

            // Sharp glowing lava veins, wide dark crust regions
            const lavaT = noiseVal.pow(2.5).clamp(0.0, 1.0);

            const fireColor = fireRamp(lavaT.add(.1));
            const coloredFire = hue(saturation(fireColor, uSaturation), uFireHue);

            const tempScale = uEmitTemperature.div(8.34).max(0.0);
            const tempFactor = tempScale.pow(4.0);
            const densityScale = uEmitDensity.div(11.02).max(0.0);
            const fadeIn = smoothstep(0.0, 3.0, uTime);

            return coloredFire.mul(tempFactor).mul(densityScale).mul(uFireIntensity).mul(uFlicker).mul(fadeIn).mul(uMeshEmissiveIntensity);
        })();
    }

    // ---------------------------------------------------------------
    // Animation (verbatim animate() logic, minus rAF)
    // ---------------------------------------------------------------
    let simulationTime = 0;
    let simAccumulator = 0;

    function updateTemporalUniforms(time) {
        uTime.value = time % 1000;

        const heightNoise = cpuNoise.noise(0, time * 2.5, 0);
        uFlameHeight.value = o.flameHeight + heightNoise * 0.8;

        const swayX = cpuNoise.noise(time * 3.5, 0, 0) * 0.4;
        const swayZ = cpuNoise.noise(0, 0, time * 3.5) * 0.4;
        uSway.value.set(swayX, 0, swayZ);

        const slowNoise = cpuNoise.noise(0, time * 0.8, 0);
        const fastNoise = cpuNoise.noise(0, time * 15.0, 0);
        uFlicker.value = slowNoise * 0.12 + fastNoise * 0.06 + 0.82;

        const colorNoise = cpuNoise.noise(time * 5.0, time * 5.0, 0) * 0.08;
        uColorNoise.value = colorNoise;

        // the example rotates its teapot here (rotation.y = time * 0.25)
        if (o.onTemporal) o.onTemporal(time);

        mesh.updateMatrixWorld();
        uEmitterMatrix.value.copy(mesh.matrixWorld);
    }

    async function simSubStep() {
        await renderer.computeAsync(advectVelocityPass); // reads dyeTexNode, writes velTexB
        await renderer.computeAsync(divergencePass);     // velB -> div

        for (let i = 0; i < PRESSURE_ITERATIONS; i++) {
            await renderer.computeAsync((i % 2 === 0) ? jacobiPassAB : jacobiPassBA);
        }

        await renderer.computeAsync(projectPass);        // velB - grad(p) -> velA
        await renderer.computeAsync(dyeInA ? advectDyeAB : advectDyeBA);
        await renderer.computeAsync(dyeInA ? emitAB : emitBA);

        // ⚠R184(2): ping-pong = flip + repoint the READ node (the example
        // swaps dyeTexNode.value <-> dyeTexWriteNode.value)
        dyeInA = !dyeInA;
        dyeTexNode.value = dyeInA ? dyeTexA : dyeTexB;
    }

    async function step(delta = 1 / 60) {
        delta = Math.min(delta, 1 / 30);

        // Calculate mesh speed and velocity vector for wind effect
        const currentPos = mesh.position;
        const dist = currentPos.distanceTo(prevMeshPos);
        const speed = delta > 0 ? dist / delta : 0;

        const meshVel = new THREE.Vector3();
        if (delta > 0) meshVel.subVectors(currentPos, prevMeshPos).multiplyScalar(1 / delta);
        prevMeshPos.copy(currentPos);

        uEmitterSpeed.value = speed;
        uEmitterVelocity.value.copy(meshVel);
        uEmitterPosition.value.copy(currentPos);

        const dt = delta * o.simSpeed;
        simAccumulator += dt;

        const stepTime = 1 / 120;
        const simStep = stepTime * o.simSpeed;

        const maxAccumulator = simStep * 8;
        if (simAccumulator > maxAccumulator) simAccumulator = maxAccumulator;

        uDt.value = simStep;
        uTurbulence.value = o.simSpeed > 0 ? o.turbulence / Math.sqrt(o.simSpeed) : 0;

        if (o.smokeLifespan >= 100.0) uDissipation.value = 0.0;
        else uDissipation.value = 1.0 / o.smokeLifespan;
        uCooling.value = 1.0 / o.fireLifespan;

        while (simAccumulator >= simStep) {
            simulationTime += simStep;
            updateTemporalUniforms(simulationTime);
            await simSubStep();
            simAccumulator -= simStep;
        }

        // Update point light range from temperature/density/intensity (verbatim)
        const tempRatio = uEmitTemperature.value / 8.34;
        const densityRatio = uEmitDensity.value / 11.02;
        const intensityRatio = uFireIntensity.value / 5.63;
        const sizeFactor = Math.sqrt(tempRatio * densityRatio * intensityRatio);

        const t = Math.min(Math.max(simulationTime / 3.0, 0.0), 1.0);
        const fadeIn = t * t * (3.0 - 2.0 * t);

        pointLight.distance = Math.max(0.01, 40.0 * Math.max(0.2, sizeFactor) * fadeIn);
    }

    // Pre-roll so frame 0 shows the established fire (the example's point
    // light and mesh emissive fade in over the first 3s of sim time)
    async function warmup(seconds = o.warmupSeconds) {
        const simStep = (1 / 120) * o.simSpeed;
        uDt.value = simStep;
        uTurbulence.value = o.turbulence / Math.sqrt(o.simSpeed);
        uDissipation.value = o.smokeLifespan >= 100 ? 0 : 1 / o.smokeLifespan;
        uCooling.value = 1 / o.fireLifespan;
        mesh.updateMatrixWorld();
        prevMeshPos.copy(mesh.position);
        uEmitterPosition.value.copy(mesh.position);
        while (simulationTime < seconds) {
            simulationTime += simStep;
            updateTemporalUniforms(simulationTime);
            await simSubStep();
        }
        // settle the frame-level state (point light range, fade-in)
        await step(0);
        return api;
    }

    const api = {
        volumeMesh,
        shadowMesh,
        pointLight,
        volumetricMaterial,
        makeLavaEmissive,
        params: o,
        get simTime() { return simulationTime; },
        uniforms: {
            uBuoyancy, uWeight, uTurbulence, uTurbulenceDecay, uTurbFrequency,
            uVelDamping, uCooling, uDissipation, uEmitDensity, uEmitTemperature,
            uMotionBoost, uWindStrength, uFireIntensity, uMeshEmissiveIntensity,
            uFireGlowSpread, uShadowAbsorption, uShadowAmbient, uFireStartColor,
            uFireMidColor, uFireEndColor, uFireHue, uAsymmetry, uPowderStrength,
            uMultiScattering, uPointLightVolumeIntensity, uPointLightSurfaceIntensity,
            uLightNearIntensity, uLightFarIntensity, uLightFarDistance,
            uSaturation, uFlameHeight, uKeyLightPos,
        },
        step,
        warmup,
        dispose() {
            pointLight.removeFromParent();
            [velTexA, velTexB, dyeTexA, dyeTexB, divTex, pressTexA, pressTexB,
                curlNoiseTex].forEach(t => t.dispose?.());
            volumeMesh.geometry.dispose();
            shadowMesh.geometry.dispose();
            volumetricMaterial.dispose?.();
            shadowMaterial.dispose?.();
        },
    };
    return api;
}

// ════════════════════════════════════════════════════════════════════════
// Render pipeline (verbatim): scene pass + half-res volumetric pass →
// gaussian denoise → saturation → ×0.5 → max/add composite → bloom.
// This chain IS the example's look; rendering the volume mesh directly in
// the scene gives a harsher, brighter, noisier image.
// ════════════════════════════════════════════════════════════════════════
export function createFireCompose(renderer, scene, camera, fire, lights = [], opts = {}) {
    const o = {
        resolutionScale: 0.5,
        denoiseStrength: 0.5,
        saturationAmount: fire.params.saturationAmount ?? 1.1,
        bloomStrength: 0.1,
        bloomRadius: 1.0,
        bloomThreshold: 0.5,
        ...opts,
    };

    const volumetricLayer = new THREE.Layers();
    volumetricLayer.disableAll();
    volumetricLayer.enable(VOLUMETRIC_LAYER);

    for (const l of lights) l.layers.enable(VOLUMETRIC_LAYER);

    // Scene Pass (default layers — the volume mesh is layer 10 only)
    const scenePass = pass(scene, camera);
    scenePass.name = 'Scene Pass';

    // Volumetric Lighting Pass — half resolution
    const volumetricPass = pass(scene, camera);
    volumetricPass.name = 'Volumetric Lighting';
    volumetricPass.setLayers(volumetricLayer);
    volumetricPass.setResolutionScale(o.resolutionScale);

    // Compose and Denoise
    const denoiseStrength = uniform(o.denoiseStrength);
    const uSat = uniform(o.saturationAmount);

    // ⚠R184: read the passes via getTextureNode('output') explicitly — this
    // repo's proven pass-compositing pattern; dev's PassNode converts
    // implicitly when used in node expressions.
    const sceneTex = scenePass.getTextureNode('output');
    const volTex = volumetricPass.getTextureNode('output');

    const blurredVolumetricPass = gaussianBlur(volTex, denoiseStrength, 1);

    const volumetricRGB = blurredVolumetricPass.rgb;
    const adjustedVolumetricRGB = saturation(volumetricRGB, uSat);
    const adjustedVolumetric = vec4(adjustedVolumetricRGB, blurredVolumetricPass.a).mul(.5);

    const scenePassColor = sceneTex.max(adjustedVolumetric).add(adjustedVolumetric);

    const bloomPass = bloom(scenePassColor);
    bloomPass.threshold.value = o.bloomThreshold;
    bloomPass.strength.value = o.bloomStrength;
    bloomPass.radius.value = o.bloomRadius;

    const output = scenePassColor.add(bloomPass);

    // ⚠R184(3): PostProcessing (extends RenderPipeline) for renderAsync
    const post = new THREE.PostProcessing(renderer);
    post.outputNode = output;

    return {
        post,
        bloomPass,
        denoiseStrength,
        renderAsync: () => post.renderAsync(),
    };
}

export default createVolumeFire;
