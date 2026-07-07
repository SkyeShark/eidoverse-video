// sdf_raymarch_loader.js
//
// Loads pure-SDF raymarched objects into a three.js scene as regular
// Object3D's that composite correctly with render_scene.mjs's
// auto-enhance pipeline (GTAO, SSR, FXAA) and with every depth- or
// normal-based pass in custom_effects.js (fog, focus blur, edge
// outline, depth posterize, etc.). No marching cubes, no bake step,
// no anatomy library — the agent writes a creature's
// `map(p) -> {dist, mat}` and `shade(p, n, mat) -> vec3` as TSL node
// functions and this module builds the full raymarch (a NodeMaterial
// colorNode/depthNode pair) and wires it into the render pipeline.
//
// NOTE (2026-07-04): this file was migrated GLSL → TSL. The pipeline is
// WebGPURenderer + NodeMaterial-ONLY — a raw GLSL ShaderMaterial renders
// SOLID BLACK here. See the "TSL SDF ENGINE" section below for the full
// rationale, the current API, and which GLSL EXAMPLES still need porting.
//
// Agent API
// =========
//
//     // HELPER_MODULES injects this file already — but it only installs
//     // `window.SdfRaymarchLoader = { createSdfObject, registerSdfHelper,
//     // EXAMPLES, SDF_TSL, ... }`. Bare `EXAMPLES` / `SDF_TSL` are NOT
//     // globals from a scene script's point of view — they're top-level
//     // `const` inside THIS file's own indirect-eval call, which does not
//     // leak into a scene script's separate eval (verified — see
//     // work/unit_test/scene.js for the same documented gotcha). Always
//     // go through `globalThis.SdfRaymarchLoader.X` from a scene script:
//     const SDF = globalThis.SdfRaymarchLoader;
//
//     // ONCE per setup, before render_scene.mjs's auto-enhance runs:
//     SDF.registerSdfHelper(renderer, scene);
//
//     const creature = SDF.createSdfObject({
//         map(p) {                                 // p: vec3 TSL node, LOCAL space
//             const body = SDF.SDF_TSL.sdSphere(p, SDF.SDF_TSL.float(0.4));
//             const head = SDF.SDF_TSL.sdSphere(p.sub(SDF.SDF_TSL.vec3(0, 0.55, 0)), SDF.SDF_TSL.float(0.2));
//             return { dist: SDF.SDF_TSL.smin(body, head, SDF.SDF_TSL.float(0.1)), mat: SDF.SDF_TSL.float(1.0) };
//         },
//         shade(p, n /*, mat */) {                 // n: vec3 TSL node, LOCAL-space normal
//             const { vec3, normalize, max, dot, float } = SDF.SDF_TSL;
//             const L = normalize(vec3(0.5, 0.8, 0.3));
//             const diff = max(float(0.0), dot(n, L));
//             const amb = float(0.3).add(float(0.2).mul(n.y.mul(0.5).add(0.5)));
//             return vec3(0.7, 0.5, 0.3).mul(amb.add(diff.mul(0.8)));
//         },
//         bounds: { min: [-0.6, -0.6, -0.6], max: [0.6, 0.9, 0.6] },
//         quality: 'balanced',   // 'fast' | 'balanced' | 'high' | 'ultra'
//     });
//     // Do NOT scene.add(creature) — createSdfObject auto-registers it
//     // with the internal shadow scene (registerSdfHelper composites it
//     // over the main render). Position it like any Object3D:
//     creature.position.set(2, 0, -1);
//
// The available primitive library (SDF_TSL, import explicitly — there's
// no GLSL-style auto-concatenation on this backend) covers:
//     sdSphere, sdBox, sdRoundBox, sdCapsule, sdCap2 (tapered),
//     sdEllipsoid, sdTorus, sdCone, sdRoundCone, sdTriPrism
//     smin, smax, opU, opSmoothU, opSub, opSmoothSub, opInt
//     opRotateX, opRotateY, opRotateZ, opMirrorX, opMirrorZ
//     hash, vnoise, fbm, fbm6
// plus the common TSL builder functions (Fn, Loop, If, Discard, vec3,
// float, normalize, dot, mix, clamp, ...) re-exported for convenience.
//
// SDFs are far more capable than baked MC meshes for detail density:
// micro-relief, domain-warped skin, triplanar striping, subsurface
// glow, sharp creases, infinite fractal patterns, and self-shadowing
// crevices all fit inside the same map/shade with no bake hit.
// See the EXAMPLES export for representative quality tiers (currently
// every EXAMPLES entry is TSL — ported 2026-07-04/05, render-verified).

// THREE is loaded into the page as a global (via three_bundle.js script
// tag in render_common.mjs). Pick it up from there. ESM consumers can
// load this file as a script tag with the same effect — three.js just
// needs to be on `window.THREE` first. The depth-pipe internals
// (renderer.render interceptor, gl_FragDepth, uPassType branching,
// BackSide bounding-box raymarch) are NOT touched by this loader-shape
// choice.
const THREE = (typeof window !== 'undefined' && window.THREE) ? window.THREE : null;
if (!THREE) {
    throw new Error('sdf_raymarch_loader: window.THREE not found — load ' +
        'three.js (e.g. /opt/render3d/three_bundle.js) before this script.');
}

// =====================================================================
// QUALITY PRESETS — pick one per object based on screen size / role
// =====================================================================
//   fast      — hero object small on screen, many instances, dev preview
//   balanced  — default quality for a single on-screen character
//   high      — close-up hero character, tight crevices, small features
//   ultra     — still frames, extreme close-ups, fine micro-detail
//
// Each preset controls the raymarch loop's inner budget:
//   · maxSteps   — upper bound on ray iterations per pixel
//   · surfEps    — fraction of ray distance at which a hit is accepted
//   · stepScale  — how far to step each iteration (safer < 1.0 for
//                   approximate SDFs, 1.0 for exact SDFs)
//   · maxDist    — ray cutoff distance. Generous by default — agent
//                   tool, scenes vary in scale and we'd rather pay a
//                   few extra steps than have feature pop-out artifacts
//                   when an SDF object is placed off-center or seen
//                   from a wider establishing shot. Override on the
//                   spec if you actually need the budget back.
// =====================================================================
const QUALITY_PRESETS = {
    fast:     { maxSteps:  64, surfEps: 0.0020, stepScale: 0.90, maxDist:  60.0 },
    balanced: { maxSteps: 128, surfEps: 0.0010, stepScale: 0.85, maxDist: 100.0 },
    high:     { maxSteps: 192, surfEps: 0.0005, stepScale: 0.75, maxDist: 150.0 },
    ultra:    { maxSteps: 256, surfEps: 0.0003, stepScale: 0.70, maxDist: 200.0 },
};

// =====================================================================
// TSL SDF ENGINE — WebGPU / NodeMaterial raymarch core (THE ACTIVE PATH)
// =====================================================================
// createSdfObject() (further below) builds a MeshBasicNodeMaterial whose
// colorNode/depthNode do the sphere-trace — NOT a GLSL3 ShaderMaterial.
// This pipeline is WebGPURenderer + NodeMaterial-ONLY: a raw
// `THREE.ShaderMaterial` renders SOLID BLACK on this backend, silently
// (no shader-compile error — it just draws black). The GLSL sections
// below (SDF_PRIMITIVES_GLSL / VERTEX_SHADER / buildFragmentShader) and
// the GLSL EXAMPLES (stylizedBlob, detailedCoat, fractalCore, the 4 car/
// jet examples) are LEGACY — kept for reference and because
// createSdfObject() still accepts them, but only to print a loud warning
// and hand back a visible magenta placeholder instead of a silent black
// box. Porting one of those to TSL is future work (see the module's
// closing comment for the running list).
//
// AGENT API (current — map/shade are JS FUNCTIONS, not GLSL strings).
// From a SCENE SCRIPT, go through `globalThis.SdfRaymarchLoader` — bare
// `createSdfObject`/`SDF_TSL` are this file's OWN top-level bindings and
// don't leak across the eval boundary (see the file-header note above):
//
//     const SDF = globalThis.SdfRaymarchLoader;
//     const sdf = SDF.createSdfObject({
//         map(p) {                      // p: vec3 TSL node, LOCAL space
//             return {
//                 dist: SDF.SDF_TSL.sdSphere(p, SDF.SDF_TSL.float(0.4)),
//                 mat:  SDF.SDF_TSL.float(1.0),
//             };
//         },
//         shade(p, n, mat) {            // n: vec3 TSL node, LOCAL-space normal
//             const { vec3, normalize, dot, max, float } = SDF.SDF_TSL;
//             const L = normalize(vec3(0.5, 0.8, 0.3));
//             const diff = max(0.0, dot(n, L));
//             return vec3(0.7, 0.5, 0.3).mul(float(0.3).add(diff.mul(0.8)));
//         },
//         bounds: { min: [-0.5, -0.5, -0.5], max: [0.5, 0.5, 0.5] },
//         quality: 'balanced',
//     });
//     // Same contract as before: do NOT scene.add(sdf) — createSdfObject
//     // auto-registers it with the internal shadow scene; position it via
//     // sdf.position / .rotation / .scale like any Object3D, and call
//     // registerSdfHelper(renderer, scene) once per setup.
//
// `map(p)` returns a plain JS `{ dist, mat }` pair of TSL float nodes (NOT
// a GLSL vec2 — there's no preprocessor to concatenate GLSL text against
// on this backend). `shade(p, n, mat, ctx)` returns a vec3 TSL node; the
// optional 4th `ctx` arg carries `{ softShadow, calcNormal }` so shade()
// can self-shadow the same way the GLSL originals did with the built-in
// `softShadow(ro, rd, mint, maxt, k)`.
//
// SDF_TSL (also on window.SdfRaymarchLoader.SDF_TSL) is the ported
// primitive library (sdSphere, sdBox, sdRoundBox, sdCapsule, sdCap2,
// sdEllipsoid, sdTorus, sdCone, sdRoundCone, sdTriPrism, smin, smax, opU,
// opSmoothU, opSub, opSmoothSub, opInt, opRotateX/Y/Z, opMirrorX/Z, hash,
// vnoise, fbm, fbm6) PLUS the common TSL builder functions (Fn, Loop, If,
// Break, Discard, vec2/vec3/vec4, float, mix, clamp, normalize, dot,
// cameraPosition, modelWorldMatrix, ...) re-exported for convenience, so
// a custom SDF author doesn't have to destructure THREE a second time.
// Primitives here take an already-offset `p` (centered at origin) — the
// GLSL library's `sdSphere(p, center, r)`-style overloads don't exist in
// JS; translate yourself first: `sdSphere(p.sub(center), r)`.
//
// KNOWN GAPS vs the GLSL path (out of scope for this port — see the
// module's closing "remaining GLSL ports" note): no uEnvMap/HDRI
// reflection plumbing yet (sampleEnvMap/sdfReflectWorld have no TSL
// equivalent here), and GTAO/SSR auto-enhance pass-type branching
// (colorNode does branch on it — see `passType` below — but it has not
// been pixel-verified against the live auto-enhance composer).
const SDF_TSL = (function buildSdfTslEngine(THREE) {
    const {
        Fn, Loop, If, Break, Discard, varying, uniform, select,
        vec2, vec3, vec4, float,
        mix, clamp, abs, max: nmax, min: nmin, normalize, dot, length,
        sin, cos, floor, fract, sign, sqrt,
        smoothstep, pow, exp, log, acos, asin, atan, mod, step, cross, reflect,
        cameraPosition, cameraNear, cameraFar, cameraViewMatrix,
        modelWorldMatrix, modelWorldMatrixInverse, positionGeometry,
        viewZToPerspectiveDepth, time,
    } = THREE;

    // ---------------- primitives (ported from SDF_PRIMITIVES_GLSL) ----------------
    // Centered-at-origin only — GLSL's `sdSphere(p, center, r)`-style second
    // overload doesn't exist here; do `sdSphere(p.sub(center), r)` instead.
    const sdSphere = (p, r) => length(p).sub(r);
    const sdBox = (p, b) => {
        const q = abs(p).sub(b);
        return length(nmax(q, 0.0)).add(nmin(nmax(q.x, nmax(q.y, q.z)), 0.0));
    };
    const sdRoundBox = (p, b, r) => sdBox(p, b).sub(r);
    const sdCapsule = (p, a, b, r) => {
        const pa = p.sub(a), ba = b.sub(a);
        const h = clamp(dot(pa, ba).div(dot(ba, ba)), 0.0, 1.0);
        return length(pa.sub(ba.mul(h))).sub(r);
    };
    const sdCap2 = (p, a, b, r1, r2) => {
        const pa = p.sub(a), ba = b.sub(a);
        const h = clamp(dot(pa, ba).div(dot(ba, ba)), 0.0, 1.0);
        return length(pa.sub(ba.mul(h))).sub(mix(r1, r2, h));
    };
    const sdEllipsoid = (p, r) => {
        const d = p.div(r);
        const k0 = length(d);
        return k0.sub(1.0).mul(nmin(r.x, nmin(r.y, r.z)));
    };
    const sdTorus = (p, t) => {
        const q = vec2(length(p.xz).sub(t.x), p.y);
        return length(q).sub(t.y);
    };
    const sdCone = (p, c, h) => {
        const q = vec2(c.x.div(c.y), float(-1.0)).mul(h);
        const w = vec2(length(p.xz), p.y);
        const a = w.sub(q.mul(clamp(dot(w, q).div(dot(q, q)), 0.0, 1.0)));
        const b = w.sub(q.mul(vec2(clamp(w.x.div(q.x), 0.0, 1.0), 1.0)));
        const k = sign(q.y);
        const d = nmin(dot(a, a), dot(b, b));
        const s = nmax(k.mul(w.x.mul(q.y).sub(w.y.mul(q.x))), k.mul(w.y.sub(q.y)));
        return sqrt(d).mul(sign(s));
    };
    const sdTriPrism = (p, hx, hz) => {
        const q = abs(p);
        const inner = nmax(q.x.mul(0.866025).add(p.y.mul(0.5)), p.y.negate()).sub(float(hx).mul(0.5));
        return nmax(q.z.sub(hz), inner);
    };

    // --- ops ---
    const smin = (a, b, k) => {
        k = float(k);   // accept plain JS numbers
        const h = clamp(float(0.5).add(float(0.5).mul(b.sub(a)).div(k)), 0.0, 1.0);
        return mix(b, a, h).sub(k.mul(h).mul(float(1.0).sub(h)));
    };
    const smax = (a, b, k) => smin(a.negate(), b.negate(), k).negate();
    // opU/opSmoothU operate on { dist, mat } pairs (they pick a material,
    // like the GLSL vec2 overloads did); opSub/opSmoothSub/opInt operate on
    // plain distances, same as the GLSL library (the agent combines raw
    // distances before wrapping the result as { dist, mat } themselves).
    const opU = (a, b) => {
        const cond = a.dist.lessThan(b.dist);
        return { dist: select(cond, a.dist, b.dist), mat: select(cond, a.mat, b.mat) };
    };
    const opSmoothU = (a, b, k) => {
        k = float(k);   // accept plain JS numbers
        const h = clamp(float(0.5).add(float(0.5).mul(b.dist.sub(a.dist)).div(k)), 0.0, 1.0);
        const d = mix(b.dist, a.dist, h).sub(k.mul(h).mul(float(1.0).sub(h)));
        const cond = a.dist.lessThan(b.dist);
        return { dist: d, mat: select(cond, a.mat, b.mat) };
    };
    const opSub = (a, b) => nmax(a.negate(), b);
    const opSmoothSub = (a, b, k) => smax(a.negate(), b, k);
    const opInt = (a, b) => nmax(a, b);

    // --- transforms ---
    const opRotateY = (p, a) => {
        const c = cos(a), s = sin(a);
        return vec3(c.mul(p.x).add(s.mul(p.z)), p.y, s.negate().mul(p.x).add(c.mul(p.z)));
    };
    const opRotateX = (p, a) => {
        const c = cos(a), s = sin(a);
        return vec3(p.x, c.mul(p.y).sub(s.mul(p.z)), s.mul(p.y).add(c.mul(p.z)));
    };
    const opRotateZ = (p, a) => {
        const c = cos(a), s = sin(a);
        return vec3(c.mul(p.x).sub(s.mul(p.y)), s.mul(p.x).add(c.mul(p.y)), p.z);
    };
    const opMirrorX = (p) => vec3(abs(p.x), p.y, p.z);
    const opMirrorZ = (p) => vec3(p.x, p.y, abs(p.z));

    // --- noise / fbm (fixed small octave counts — JS-unrolled at build
    // time rather than a runtime Loop, the pipeline's usual manual-unroll
    // convention) ---
    const _hash = (p) => {
        const pp = fract(p.mul(0.3183099).add(vec3(0.71, 0.113, 0.419))).mul(17.0);
        return fract(pp.x.mul(pp.y).mul(pp.z).mul(pp.x.add(pp.y).add(pp.z)));
    };
    const vnoise = (x) => {
        const i = floor(x), f0 = fract(x);
        const f = f0.mul(f0).mul(float(3.0).sub(f0.mul(2.0)));
        const c000 = _hash(i.add(vec3(0, 0, 0))), c100 = _hash(i.add(vec3(1, 0, 0)));
        const c010 = _hash(i.add(vec3(0, 1, 0))), c110 = _hash(i.add(vec3(1, 1, 0)));
        const c001 = _hash(i.add(vec3(0, 0, 1))), c101 = _hash(i.add(vec3(1, 0, 1)));
        const c011 = _hash(i.add(vec3(0, 1, 1))), c111 = _hash(i.add(vec3(1, 1, 1)));
        return mix(
            mix(mix(c000, c100, f.x), mix(c010, c110, f.x), f.y),
            mix(mix(c001, c101, f.x), mix(c011, c111, f.x), f.y),
            f.z,
        );
    };
    const fbm = (p) => {
        let v = float(0.0), a = 0.5, pp = p;
        for (let i = 0; i < 4; i++) { v = v.add(vnoise(pp).mul(a)); pp = pp.mul(2.03); a *= 0.5; }
        return v;
    };
    const fbm6 = (p) => {
        let v = float(0.0), a = 0.5, pp = p;
        for (let i = 0; i < 6; i++) { v = v.add(vnoise(pp).mul(a)); pp = pp.mul(2.07); a *= 0.5; }
        return v;
    };

    // ---------------- raymarch material builder ----------------
    // Builds the MeshBasicNodeMaterial for one SDF object: colorNode does
    // the sphere-trace + shading + Discard-on-miss, depthNode repeats the
    // same trace to emit the correct per-fragment hit depth (so the SDF
    // occludes/is occluded by real scene geometry sharing the same depth
    // buffer). Yes, this means the march runs twice per fragment on a hit
    // — simplicity/correctness over performance for this first TSL port
    // (see the module's closing note); a shared-computation version is
    // future work.
    function _buildSdfNodeMaterial({ mapFn, shadeFn, bounds, q }) {
        const boxMin = vec3(bounds.min[0], bounds.min[1], bounds.min[2]);
        const boxMax = vec3(bounds.max[0], bounds.max[1], bounds.max[2]);

        // Ray/box entry+exit distances along the local-space ray — same
        // technique as three/addons/tsl/utils/Raymarching.js's hitBox,
        // generalized from a fixed ±0.5 unit cube to this SDF's own bounds
        // (createSdfObject bakes `bounds` directly into the box geometry's
        // vertex data via BoxGeometry+translate, so positionGeometry below
        // already ranges over bounds.min..bounds.max, not ±0.5).
        const hitBox = (orig, dir) => Fn(() => {
            const invDir = dir.reciprocal();
            const t0v = boxMin.sub(orig).mul(invDir);
            const t1v = boxMax.sub(orig).mul(invDir);
            const tn = nmin(t0v, t1v);
            const tx = nmax(t0v, t1v);
            const t0 = nmax(tn.x, nmax(tn.y, tn.z));
            const t1 = nmin(tx.x, nmin(tx.y, tx.z));
            return vec2(t0, t1);
        })();

        // Ray origin/direction reconstructed per-fragment in LOCAL (object)
        // space. modelWorldMatrixInverse / cameraPosition are TSL builtins
        // that three.js auto-updates per-object, per-frame — unlike the old
        // GLSL path, NO manual onBeforeRender uniform bookkeeping is needed.
        const localRay = () => {
            const ro = varying(vec3(modelWorldMatrixInverse.mul(vec4(cameraPosition, 1.0))));
            const rd = normalize(varying(positionGeometry.sub(ro)));
            return { ro, rd };
        };

        const calcNormal = (p) => {
            const e = 0.0004;
            const k1 = vec3(1, -1, -1), k2 = vec3(-1, -1, 1), k3 = vec3(-1, 1, -1), k4 = vec3(1, 1, 1);
            const d1 = mapFn(p.add(k1.mul(e))).dist;
            const d2 = mapFn(p.add(k2.mul(e))).dist;
            const d3 = mapFn(p.add(k3.mul(e))).dist;
            const d4 = mapFn(p.add(k4.mul(e))).dist;
            return normalize(k1.mul(d1).add(k2.mul(d2)).add(k3.mul(d3)).add(k4.mul(d4)));
        };

        // Sphere-traced soft shadow, same falloff heuristic as the GLSL
        // original. Passed to shade() via ctx.softShadow.
        const softShadow = (ro, rd, mint, maxt, k) => Fn(() => {
            k = float(k);   // accept plain JS numbers
            const res = float(1.0).toVar();
            const t = float(mint).toVar();
            Loop({ start: 0, end: 48, type: 'int' }, () => {
                const h = mapFn(ro.add(rd.mul(t))).dist;
                If(h.lessThan(0.0005), () => { res.assign(0.0); Break(); });
                res.assign(nmin(res, k.mul(h).div(t)));
                t.addAssign(h);
                If(t.greaterThanEqual(maxt), () => { Break(); });
            });
            return clamp(res, 0.0, 1.0);
        })();

        // The march. Returns vec4(hitLocalPos.xyz, matIdOrMiss) — matId < 0
        // means the ray exited the bounds (or step budget) without a hit.
        const march = (ro, rd) => Fn(() => {
            const b = hitBox(ro, rd).toVar();
            const t = nmax(b.x, 0.0).toVar();
            const tExit = b.y;
            const matId = float(-1.0).toVar();
            Loop({ start: 0, end: q.maxSteps, type: 'int' }, () => {
                If(t.greaterThan(tExit).or(t.greaterThan(q.maxDist)), () => { Break(); });
                const p = ro.add(rd.mul(t));
                const res = mapFn(p);
                If(abs(res.dist).lessThan(float(q.surfEps).mul(nmax(t, 1.0))), () => {
                    matId.assign(res.mat);
                    Break();
                });
                t.addAssign(res.dist.mul(q.stepScale));
            });
            return vec4(ro.add(rd.mul(t)), matId);
        })();

        const material = new THREE.MeshBasicNodeMaterial({ side: THREE.DoubleSide });
        material.transparent = false;
        material.depthWrite = true;
        material.depthTest = true;

        // GTAO/SSR auto-enhance pass-type parity with the GLSL path's
        // uPassType (0=beauty, 1=view-normal, 2=depth-only). Updated per-
        // frame by registerSdfHelper. NOT pixel-verified against the live
        // auto-enhance composer — see the module's closing note.
        const passType = uniform(0);

        material.colorNode = Fn(() => {
            const { ro, rd } = localRay();
            const hit = march(ro, rd).toVar();
            const hitLocal = hit.xyz;
            const matId = hit.w;
            If(matId.lessThan(0.0), () => { Discard(); });

            // ctx.ro = LOCAL-space camera position (ray origin) — use
            // normalize(ctx.ro.sub(p)) for the view direction in fresnel /
            // reflection terms (cameraPosition is WORLD space; p is LOCAL).
            const n = calcNormal(hitLocal);
            const out = shadeFn(hitLocal, n, matId, { softShadow, calcNormal, ro, rd }).toVar();

            If(passType.equal(1), () => {
                const nWorld = normalize(modelWorldMatrix.mul(vec4(n, 0.0)).xyz);
                const nView = normalize(cameraViewMatrix.mul(vec4(nWorld, 0.0)).xyz);
                out.assign(nView.mul(0.5).add(0.5));
            });
            If(passType.equal(2), () => { out.assign(vec3(0.0)); });

            return out;
        })();

        material.depthNode = Fn(() => {
            const { ro, rd } = localRay();
            const hit = march(ro, rd).toVar();
            const hitWorld = modelWorldMatrix.mul(vec4(hit.xyz, 1.0)).xyz;
            const viewZ = cameraViewMatrix.mul(vec4(hitWorld, 1.0)).z;
            return viewZToPerspectiveDepth(viewZ, cameraNear, cameraFar);
        })();

        // MRT parity: under the auto-enhance PostProcessing chain the scene
        // pass renders color+normal+metalrough in ONE shot via
        // `setMRT(mrt({ output, normal: directionToColor(normalView),
        // metalrough }))`. A MeshBasicNodeMaterial contributes its proxy
        // BOX's normals to that `normal` channel while depthNode writes the
        // MARCHED depth — GTAO then reads a mismatched G-buffer and computes
        // near-total occlusion, turning every SDF near-black under
        // auto-enhance. Material-level mrtNode MERGES per-channel over the
        // pass MRT (three: `mrt.merge(materialMRT)`), so override just what
        // the SDF must own: the marched surface normal (dedicated march —
        // own sub-build, as everywhere on this stack) and a rough/non-metal
        // metalrough so SSR doesn't hallucinate reflections on SDF pixels.
        if (THREE.mrt && THREE.directionToColor) {
            const marchedViewNormal = Fn(() => {
                const { ro, rd } = localRay();
                const hit = march(ro, rd).toVar();
                const n = calcNormal(hit.xyz);
                const nWorld = normalize(modelWorldMatrix.mul(vec4(n, 0.0)).xyz);
                return normalize(cameraViewMatrix.mul(vec4(nWorld, 0.0)).xyz);
            })();
            material.mrtNode = THREE.mrt({
                normal: THREE.directionToColor(marchedViewNormal),
                metalrough: vec2(0.0, 1.0),
            });
        }

        material.userData.sdfPassType = passType;
        return material;
    }

    // ---------------- volumetric material builder ----------------
    // Front-to-back premultiplied density accumulation through the bounds
    // box — for participating media (smoke, fire, explosions) where the
    // surface march's hit+shade model doesn't apply. sampleFn(p) returns
    // { color: vec3 node, alpha: float node (per-sample opacity, already
    // scaled for its own step length), step: float node/number (march
    // advance) }. Optional postFn(sum) reshapes the final vec4.
    // The material is TRANSPARENT (no depth write, no relief depth): scene
    // geometry in front occludes it; the camera should stay outside the
    // bounds box (a v1 limitation, same as most impostor volumes).
    function _buildSdfVolumeMaterial({ sampleFn, postFn, bounds, steps }) {
        const bmin = vec3(bounds.min[0], bounds.min[1], bounds.min[2]);
        const bmax = vec3(bounds.max[0], bounds.max[1], bounds.max[2]);

        const hitBox = (ro, rd) => {
            const invR = vec3(1.0).div(rd);
            const t0v = bmin.sub(ro).mul(invR);
            const t1v = bmax.sub(ro).mul(invR);
            const tn = nmin(t0v, t1v);
            const tx = nmax(t0v, t1v);
            const t0 = nmax(tn.x, nmax(tn.y, tn.z));
            const t1 = nmin(tx.x, nmin(tx.y, tx.z));
            return vec2(t0, t1);
        };
        const localRay = () => {
            const ro = varying(vec3(modelWorldMatrixInverse.mul(vec4(cameraPosition, 1.0))));
            const rd = normalize(varying(positionGeometry.sub(ro)));
            return { ro, rd };
        };

        const material = new THREE.MeshBasicNodeMaterial();
        material.transparent = true;
        material.depthWrite = false;
        material.depthTest = true;
        material.premultipliedAlpha = true;   // we accumulate premultiplied

        material.colorNode = Fn(() => {
            const { ro, rd } = localRay();
            const b = hitBox(ro, rd).toVar();
            const t0 = nmax(b.x, 0.0);
            const t1 = b.y;
            If(t1.lessThanEqual(t0), () => { Discard(); });

            const sum = vec4(0.0).toVar();
            const t = float(t0).toVar();
            Loop({ start: 0, end: steps, type: 'int' }, () => {
                If(t.greaterThan(t1).or(sum.w.greaterThanEqual(0.99)), () => { Break(); });
                const p = ro.add(rd.mul(t));
                const smp = sampleFn(p);
                const a = clamp(smp.alpha, 0.0, 1.0);
                const contrib = a.mul(float(1.0).sub(sum.w));
                sum.assign(vec4(sum.xyz.add(smp.color.mul(contrib)), sum.w.add(contrib)));
                t.addAssign(nmax(float(smp.step), 1e-4));
            });
            // Sub-threshold accumulation reads as a faint milky BOX (the
            // proxy geometry's silhouette) — discard rather than composite it.
            If(sum.w.lessThan(0.01), () => { Discard(); });
            return postFn ? postFn(sum) : sum;
        })();

        return material;
    }

    // Legacy (pre-migration) GLSL-string spec was passed — render something
    // visible and obviously-wrong instead of a silent black box.
    function _createUnsupportedGlslPlaceholder(bounds) {
        const [nx, ny, nz] = bounds.min;
        const [xx, xy, xz] = bounds.max;
        const sx = Math.max(xx - nx, 0.001), sy = Math.max(xy - ny, 0.001), sz = Math.max(xz - nz, 0.001);
        const cx = (nx + xx) * 0.5, cy = (ny + xy) * 0.5, cz = (nz + xz) * 0.5;
        const geo = new THREE.BoxGeometry(sx, sy, sz);
        geo.translate(cx, cy, cz);
        const mat = new THREE.MeshBasicNodeMaterial({ color: 0xff00ff, wireframe: true });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.frustumCulled = false;
        mesh.userData.isSdfRaymarch = true;
        mesh.userData.sdfUnsupportedGlsl = true;
        SDF_SHADOW_SCENE.add(mesh);
        return mesh;
    }

    return {
        sdSphere, sdBox, sdRoundBox, sdCapsule, sdCap2, sdEllipsoid, sdTorus,
        sdCone, sdRoundCone: sdCap2, sdTriPrism,
        smin, smax, opU, opSmoothU, opSub, opSmoothSub, opInt,
        opRotateX, opRotateY, opRotateZ, opMirrorX, opMirrorZ,
        hash: _hash, vnoise, fbm, fbm6,
        // TSL passthrough for custom SDF authors.
        Fn, Loop, If, Break, Discard, varying, uniform, select, time,
        vec2, vec3, vec4, float,
        mix, clamp, abs, max: nmax, min: nmin, normalize, dot, length,
        sin, cos, floor, fract, sign, sqrt,
        smoothstep, pow, exp, log, acos, asin, atan, mod, step, cross, reflect,
        cameraPosition, cameraNear, cameraFar, cameraViewMatrix,
        modelWorldMatrix, modelWorldMatrixInverse, positionGeometry,
        viewZToPerspectiveDepth,
        // engine internals used by createSdfObject()
        _buildSdfNodeMaterial, _buildSdfVolumeMaterial, _createUnsupportedGlslPlaceholder,
    };
})(THREE);

// =====================================================================
// CANONICAL SDF PRIMITIVES (GLSL, LEGACY) — agent's map() can call any of these
// =====================================================================
const SDF_PRIMITIVES_GLSL = /* glsl */ `
// --- distances ---
float sdSphere(vec3 p, float r) { return length(p) - r; }
float sdSphere(vec3 p, vec3 c, float r) { return length(p - c) - r; }

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sdRoundBox(vec3 p, vec3 b, float r) { return sdBox(p, b) - r; }

float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}
// Tapered capsule: radius r1 at A, r2 at B
float sdCap2(vec3 p, vec3 a, vec3 b, float r1, float r2) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - mix(r1, r2, h);
}

float sdEllipsoid(vec3 p, vec3 r) {
    vec3 d = p / r;
    float k0 = length(d);
    return (k0 - 1.0) * min(r.x, min(r.y, r.z));
}
float sdEllipsoid(vec3 p, vec3 c, vec3 r) { return sdEllipsoid(p - c, r); }

float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

float sdCone(vec3 p, vec2 c, float h) {
    vec2 q = h * vec2(c.x / c.y, -1.0);
    vec2 w = vec2(length(p.xz), p.y);
    vec2 a = w - q * clamp(dot(w, q) / dot(q, q), 0.0, 1.0);
    vec2 b = w - q * vec2(clamp(w.x / q.x, 0.0, 1.0), 1.0);
    float k = sign(q.y);
    float d = min(dot(a, a), dot(b, b));
    float s = max(k * (w.x * q.y - w.y * q.x), k * (w.y - q.y));
    return sqrt(d) * sign(s);
}

float sdRoundCone(vec3 p, vec3 a, vec3 b, float r1, float r2) {
    return sdCap2(p, a, b, r1, r2);
}

// Triangular prism, apex +Y, extruded along Z. Negate p.y for inverted.
float sdTriPrism(vec3 p, float hx, float hz) {
    vec3 q = abs(p);
    return max(q.z - hz, max(q.x * 0.866025 + p.y * 0.5, -p.y) - hx * 0.5);
}

// --- ops ---
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}
float smax(float a, float b, float k) { return -smin(-a, -b, k); }

vec2 opU(vec2 a, vec2 b) { return a.x < b.x ? a : b; }
vec2 opSmoothU(vec2 a, vec2 b, float k) {
    float h = clamp(0.5 + 0.5 * (b.x - a.x) / k, 0.0, 1.0);
    float d = mix(b.x, a.x, h) - k * h * (1.0 - h);
    return vec2(d, a.x < b.x ? a.y : b.y);
}
float opSub(float a, float b) { return max(-a, b); }
float opSmoothSub(float a, float b, float k) { return smax(-a, b, k); }
float opInt(float a, float b) { return max(a, b); }

// --- transforms (use in map() to rotate/mirror local coords) ---
vec3 opRotateY(vec3 p, float a) {
    float c = cos(a), s = sin(a);
    return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}
vec3 opRotateX(vec3 p, float a) {
    float c = cos(a), s = sin(a);
    return vec3(p.x, c * p.y - s * p.z, s * p.y + c * p.z);
}
vec3 opRotateZ(vec3 p, float a) {
    float c = cos(a), s = sin(a);
    return vec3(c * p.x - s * p.y, s * p.x + c * p.y, p.z);
}
vec3 opMirrorX(vec3 p) { return vec3(abs(p.x), p.y, p.z); }
vec3 opMirrorZ(vec3 p) { return vec3(p.x, p.y, abs(p.z)); }

// --- noise / fbm ---
float _hash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float vnoise(vec3 x) {
    vec3 i = floor(x), f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(_hash(i + vec3(0,0,0)), _hash(i + vec3(1,0,0)), f.x),
                   mix(_hash(i + vec3(0,1,0)), _hash(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(_hash(i + vec3(0,0,1)), _hash(i + vec3(1,0,1)), f.x),
                   mix(_hash(i + vec3(0,1,1)), _hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * vnoise(p); p *= 2.03; a *= 0.5; }
    return v;
}
// 6-octave for high-quality surface detail
float fbm6(vec3 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 6; i++) { v += a * vnoise(p); p *= 2.07; a *= 0.5; }
    return v;
}
`;

// =====================================================================
// SHADERS
// =====================================================================
const VERTEX_SHADER = /* glsl */ `
// Explicit uniforms set from JS in onBeforeRender — see comment in
// createSdfObject for why we don't rely on three.js auto-injection.
uniform mat4 uModelMatrix;
uniform mat4 uViewMatrix;
uniform mat4 uProjectionMatrix;
out vec3 vWorldPos;
void main() {
    vec4 wp = uModelMatrix * vec4(position, 1.0);
    vWorldPos = wp.xyz;
    gl_Position = uProjectionMatrix * uViewMatrix * wp;
}
`;

function buildFragmentShader(mapGLSL, shadeGLSL, extraGLSL) {
    return /* glsl */ `
precision highp float;

in vec3 vWorldPos;
out vec4 pc_FragColor;

uniform mat4  uInvModelMatrix;
uniform mat4  uModelMatrix;
uniform mat4  uViewMatrix;
uniform mat4  uProjectionMatrix;
uniform float uTime;
uniform int   uPassType;      // 0=beauty, 1=view-normal, 2=depth/metalness
uniform int   uMaxSteps;
uniform float uMaxDist;
uniform float uStepScale;
uniform float uSurfEps;
// HDRI environment reflection — registerSdfHelper copies scene.environment
// into uEnvMap each frame. Examples sample it via sampleEnvMap(worldDir);
// when no HDRI is set the sampler returns a neutral mid-gray so chrome /
// glass / reflective materials degrade gracefully. This makes SDF
// reflections match what three.js's MeshStandardMaterial sees from the
// same scene.environment, so SDF objects render with the same lighting
// the rest of the scene uses (HDRIs, IBL, studio panels, daylight, etc.)
// instead of being locked to a hardcoded procedural sky inside each
// example's shade function.
uniform sampler2D uEnvMap;
uniform float     uEnvMapStrength;

// Three.js auto-injects cameraPosition reliably; we still need it for
// the shader's view vector and (in beauty pass) the SDF ray origin.
// Everything else (model/view/projection) comes from our explicit
// uniforms above so depth and screen-space output are exact.

// Equirectangular HDRI sampler. scene.environment in our pipeline is
// always set up with EquirectangularReflectionMapping (a 2D HDR/EXR
// texture, not a cubemap). Three.js's standard materials use the
// engine's PMREM cube_uv lookup; custom ShaderMaterials have to do
// the equirectangular projection themselves. Returns linear RGB at
// the worldspace reflection direction. When uEnvMapStrength is 0
// (no scene.environment set), returns mid-gray so chrome materials
// still read sensibly without a stylized hardcoded fallback.
vec3 sampleEnvMap(vec3 worldDir) {
    if (uEnvMapStrength <= 0.0) return vec3(0.5);
    vec3 d = normalize(worldDir);
    vec2 uv = vec2(
        atan(d.z, d.x) * 0.15915494 + 0.5,                  // 1 / (2π)
        asin(clamp(d.y, -1.0, 1.0)) * 0.31830989 + 0.5     // 1 / π
    );
    return texture(uEnvMap, uv).rgb * uEnvMapStrength;
}

// Local-to-world reflection helper for SDF shade functions. The shade
// callback receives p and n in the SDF's LOCAL coordinate frame, but
// the env map is in WORLD space (the same frame three.js's other
// scene meshes sample). Without this transform, env reflections rotate
// with the SDF mesh's parent (wrong) instead of staying pinned to the
// scene HDRI (right). Use whenever sampling sampleEnvMap from a shade
// function — pass the local hit point and local normal, get back the
// correct worldspace reflection direction.
vec3 sdfReflectWorld(vec3 pLocal, vec3 nLocal) {
    vec3 pWorld = (uModelMatrix * vec4(pLocal, 1.0)).xyz;
    vec3 nWorld = normalize(mat3(uModelMatrix) * nLocal);
    vec3 viewWorld = normalize(cameraPosition - pWorld);
    return reflect(-viewWorld, nWorld);
}

${SDF_PRIMITIVES_GLSL}

${extraGLSL || ''}

// --- AGENT MAP ---
${mapGLSL}

vec3 calcNormal(vec3 p) {
    const vec2 k = vec2(1.0, -1.0);
    const float h = 0.0004;
    return normalize(
        k.xyy * map(p + k.xyy * h).x +
        k.yyx * map(p + k.yyx * h).x +
        k.yxy * map(p + k.yxy * h).x +
        k.xxx * map(p + k.xxx * h).x
    );
}

float softShadow(vec3 ro, vec3 rd, float mint, float maxt, float k) {
    float res = 1.0;
    float t = mint;
    for (int i = 0; i < 48; i++) {
        float h = map(ro + rd * t).x;
        if (h < 0.0005) return 0.0;
        res = min(res, k * h / t);
        t += h;
        if (t >= maxt) break;
    }
    return clamp(res, 0.0, 1.0);
}

// --- AGENT SHADE ---
${shadeGLSL}

void main() {
    vec3 roWorld = cameraPosition;
    vec3 rdWorld = normalize(vWorldPos - cameraPosition);
    vec3 roLocal = (uInvModelMatrix * vec4(roWorld, 1.0)).xyz;
    vec3 rdLocal = normalize((uInvModelMatrix * vec4(rdWorld, 0.0)).xyz);

    float t = 0.001;
    vec2 res = vec2(9999.0, 0.0);
    bool hit = false;
    for (int i = 0; i < 512; i++) {
        if (i >= uMaxSteps) break;
        vec3 p = roLocal + rdLocal * t;
        res = map(p);
        if (abs(res.x) < uSurfEps * max(t, 1.0)) { hit = true; break; }
        t += res.x * uStepScale;
        if (t > uMaxDist) break;
    }
    if (!hit) discard;

    vec3 hitLocal = roLocal + rdLocal * t;
    vec3 nLocal = calcNormal(hitLocal);
    vec3 hitWorld = (uModelMatrix * vec4(hitLocal, 1.0)).xyz;
    vec3 nWorld = normalize(mat3(uModelMatrix) * nLocal);

    // Write proper screen-space depth so the SDF surface participates
    // in the depth buffer alongside scene meshes — opaque chair/VRM
    // geometry occludes SDF pixels behind them, and the auto-enhance
    // composer's depth-based passes (GTAO, custom_effects underwater
    // caustics, depth_fog, focus_blur, etc.) read SDF surfaces too.
    vec4 clip = uProjectionMatrix * uViewMatrix * vec4(hitWorld, 1.0);
    gl_FragDepth = clip.z / clip.w * 0.5 + 0.5;

    if (uPassType == 1) {
        vec3 vn = normalize((uViewMatrix * vec4(nWorld, 0.0)).xyz);
        pc_FragColor = vec4(vn * 0.5 + 0.5, 1.0);
        return;
    } else if (uPassType == 2) {
        pc_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    vec3 col = shade(hitLocal, nLocal, res.y);
    pc_FragColor = vec4(col, 1.0);
}
`;
}

// =====================================================================
// OBJECT FACTORY
// =====================================================================
function createSdfObject(spec) {
    const {
        map,
        shade,
        bounds = { min: [-1, -1, -1], max: [1, 1, 1] },
        quality = 'balanced',
        maxSteps,
        maxDist,
        stepScale,
        surfEps,
        uniforms: userUniforms = {},
    } = spec;

    if (!map)   throw new Error('createSdfObject: spec.map is required (a JS function (p) => {dist, mat} — see the "TSL SDF ENGINE" header comment)');
    if (!shade) throw new Error('createSdfObject: spec.shade is required (a JS function (p, n, mat) => vec3 node)');

    // Pre-migration agent API passed GLSL source strings (see the LEGACY
    // GLSL section above). This pipeline is WebGPURenderer + NodeMaterial-
    // ONLY — a raw GLSL3 ShaderMaterial renders SOLID BLACK here, with no
    // compile error to flag it. Fail loud-and-visible instead of silently
    // handing back a black box.
    if (typeof map === 'string' || typeof shade === 'string') {
        console.warn(
            '[sdf_raymarch_loader] createSdfObject received GLSL-string map/shade ' +
            '(the pre-migration agent API). This renders SOLID BLACK on the current ' +
            'WebGPURenderer + NodeMaterial-ONLY pipeline — GLSL ShaderMaterial is not ' +
            'supported. map/shade must be JS functions returning TSL nodes now (see ' +
            'the "TSL SDF ENGINE" header comment and EXAMPLES.basicSphere for a working ' +
            'reference). Returning a magenta wireframe placeholder instead of a silent ' +
            'black box so the gap is obvious. Every EXAMPLES entry is TSL now — ' +
            'use those as porting references. Still-GLSL (broken) subsystems: ' +
            'makeSdfTexture / SDF_TEX_RECIPES.'
        );
        return SDF_TSL._createUnsupportedGlslPlaceholder(bounds);
    }

    const preset = QUALITY_PRESETS[quality] || QUALITY_PRESETS.balanced;
    const q = {
        maxSteps:  maxSteps  ?? preset.maxSteps,
        maxDist:   maxDist   ?? preset.maxDist,
        stepScale: stepScale ?? preset.stepScale,
        surfEps:   surfEps   ?? preset.surfEps,
    };

    const [nx, ny, nz] = bounds.min;
    const [xx, xy, xz] = bounds.max;
    const sx = Math.max(xx - nx, 0.001);
    const sy = Math.max(xy - ny, 0.001);
    const sz = Math.max(xz - nz, 0.001);
    const cx = (nx + xx) * 0.5;
    const cy = (ny + xy) * 0.5;
    const cz = (nz + xz) * 0.5;

    const geo = new THREE.BoxGeometry(sx, sy, sz);
    geo.translate(cx, cy, cz);

    const material = SDF_TSL._buildSdfNodeMaterial({ mapFn: map, shadeFn: shade, bounds, q });

    const mesh = new THREE.Mesh(geo, material);
    mesh.frustumCulled = false;
    mesh.userData.isSdfRaymarch = true;
    mesh.userData.sdfQuality = quality;
    // Same slot registerSdfHelper syncs uPassType into, GTAO/SSR parity
    // with the GLSL path (see _buildSdfNodeMaterial).
    mesh.userData.sdfPassType = material.userData.sdfPassType;
    if (userUniforms && Object.keys(userUniforms).length) {
        mesh.userData.sdfUniforms = userUniforms;
    }

    // Auto-register with the helper's shadow scene so the agent doesn't
    // need to call scene.add() — the patched render hook composites it
    // over each main-scene render. Agent positions via mesh.position etc.
    SDF_SHADOW_SCENE.add(mesh);

    return mesh;
}

// Placeable VOLUMETRIC SDF object (participating media — smoke, fire,
// explosions). Same lifecycle as createSdfObject (auto-registered with the
// helper's shadow scene; position via mesh.position etc.; registerSdfHelper
// once per setup), but the material is a transparent front-to-back density
// accumulation instead of a hit+shade surface march.
//   spec: { sample(p) -> {color, alpha, step},  bounds,  steps = 96,
//           post(sum) -> vec4  (optional final reshape) }
function createSdfVolume(spec) {
    const {
        sample,
        post = null,
        bounds = { min: [-1, -1, -1], max: [1, 1, 1] },
        steps = 96,
    } = spec;
    if (typeof sample !== 'function') {
        throw new Error('createSdfVolume: spec.sample is required — a JS function (p) => ({ color, alpha, step }) of TSL nodes');
    }

    const [nx, ny, nz] = bounds.min;
    const [xx, xy, xz] = bounds.max;
    const geo = new THREE.BoxGeometry(
        Math.max(xx - nx, 0.001), Math.max(xy - ny, 0.001), Math.max(xz - nz, 0.001));
    geo.translate((nx + xx) * 0.5, (ny + xy) * 0.5, (nz + xz) * 0.5);

    const material = SDF_TSL._buildSdfVolumeMaterial({ sampleFn: sample, postFn: post, bounds, steps });
    const mesh = new THREE.Mesh(geo, material);
    mesh.frustumCulled = false;
    mesh.userData.isSdfRaymarch = true;
    mesh.userData.isSdfVolume = true;
    mesh.renderOrder = 1;   // after opaque SDF surfaces in the overlay
    SDF_SHADOW_SCENE.add(mesh);
    return mesh;
}

// =====================================================================
// RENDERER INTEGRATION — SDF meshes live in a helper-owned SHADOW scene
// (not in the user's main scene). The patched renderer.render renders
// the shadow scene over each main-scene render with uPassType flipped
// to match the current pass's expected output format.
//
// Agent contract — what the loader gives every SDF for free:
//
//   POSITIONING & SCENE INTEGRATION
//   · createSdfObject() returns a Mesh that's auto-registered with the
//     shadow scene. Position via standard Object3D transforms
//     (mesh.position / mesh.rotation / mesh.scale).
//   · DO NOT call scene.add(mesh) on the returned mesh — the helper
//     handles all rendering internally. Adding it to the main scene
//     causes the bounding-box geometry to be rasterised by GTAO's
//     normal pre-pass, producing a soft halo around the SDF.
//   · Call registerSdfHelper(renderer, mainScene) once per setup,
//     BEFORE render_scene.mjs's auto-enhance runs. Pass the user's
//     main scene as the second arg so the helper composites SDFs only
//     over that scene (skipping post-pass quad scenes).
//
//   DEPTH INTEGRATION (automatic)
//   · The SDF writes per-pixel gl_FragDepth from the worldspace hit
//     point, so it participates correctly in the depth buffer. Other
//     scene meshes occlude it as expected, GTAO/SSR/depth-fog/etc.
//     read SDF surfaces alongside scene meshes, and post-process
//     depth-aware passes (underwater caustics, focus blur, depth
//     posterise, etc.) treat SDFs the same as any other geometry.
//
//   HDRI ENVIRONMENT REFLECTIONS (automatic)
//   · Every SDF inherits uEnvMap and uEnvMapStrength uniforms.
//     The render hook copies scene.environment into uEnvMap each
//     frame, so chrome/glass/metal materials reflect the same HDRI
//     three.js's MeshStandardMaterial sees in the same scene.
//   · In your shade() function, use:
//       sampleEnvMap(worldDir)        — returns linear RGB at world
//                                       direction. Returns vec3(0.5)
//                                       (mid-grey) when no HDRI is
//                                       set, so chrome stays sane.
//       sdfReflectWorld(p, n)         — converts the local hit point
//                                       and local normal you receive
//                                       in shade() to a worldspace
//                                       reflection direction suitable
//                                       for sampleEnvMap. Required
//                                       any time you want to reflect
//                                       the scene HDRI; reflect(rd,n)
//                                       gives a LOCAL direction which
//                                       rotates with the SDF mesh.
//     Common pattern:
//       vec3 envR = sampleEnvMap(sdfReflectWorld(p, n));
//       vec3 sky  = sampleEnvMap(vec3(0.0, 1.0, 0.0));   // world up
//
//   SHADING UTILITIES (already present in main shader)
//   · softShadow(ro, rd, mint, maxt, k)  — sphere-traced shadow.
//   · calcNormal(p)                       — finite-diff normal.
//   · cameraPosition (auto-injected)      — worldspace camera.
//   · uModelMatrix, uViewMatrix,
//     uProjectionMatrix, uInvModelMatrix  — explicit transform
//                                            uniforms (not auto-
//                                            injected, written each
//                                            frame in onBeforeRender).
// =====================================================================
const PATCHED_MARKER = '__sdfRaymarchHelperPatched';
const REENTRY_GUARD  = '__sdfRaymarchInHelper';

// One process-wide shadow scene. createSdfObject() adds returned meshes
// to this scene; the patched render hook draws this scene over each
// main render with the matching uPassType.
const SDF_SHADOW_SCENE = new THREE.Scene();

// Internal: identify a fullscreen post-pass quad scene (RenderPass / FXAA /
// OutputPass / underwater / etc. — whatever the EffectComposer wires up).
// These scenes contain a single quad mesh whose material has `tDiffuse`
// (the previous pass's color attachment). If we re-rendered SDFs over them
// the SDF would composite ON TOP of the final post-process output —
// no depth test against the original scene geometry, no caustics from the
// underwater pass, etc. Skip SDF injection for these scenes.
function _isPostPassQuadScene(scene) {
    if (!scene || !scene.isScene) return false;
    if (scene.children.length !== 1) return false;
    const child = scene.children[0];
    if (!child || !child.isMesh) return false;
    const mat = child.material;
    if (!mat || !mat.uniforms) return false;
    return 'tDiffuse' in mat.uniforms;
}

// `mainScene` is optional — when supplied, the patched render only injects
// SDFs when called with that exact scene reference (matches the truck-SDF
// reference pattern). Without it, we fall back to a quad-scene heuristic so
// agents that don't explicitly register the main scene still get correct
// depth integration.
function registerSdfHelper(renderer, mainScene) {
    if (!renderer || renderer[PATCHED_MARKER]) {
        // Already patched — allow late binding of mainScene if the agent
        // wants to upgrade from heuristic to exact match.
        if (renderer && mainScene) renderer.__sdfMainScene = mainScene;
        return;
    }
    renderer[PATCHED_MARKER] = true;
    if (mainScene) renderer.__sdfMainScene = mainScene;

    // The renderer's PRISTINE default context node, captured at register
    // time (scene setup — before any PostProcessing pass installs a custom
    // context like builtinAOContext). Swapped in for the overlay draw; a
    // raw null is NOT valid here (three hashes contextNode.id unguarded).
    const defaultContextNode = renderer.contextNode;

    const originalRender = renderer.render.bind(renderer);

    renderer.render = function patchedRender(scene, camera) {
        if (renderer[REENTRY_GUARD]) {
            return originalRender(scene, camera);
        }
        if (!scene || !scene.isScene) {
            return originalRender(scene, camera);
        }
        // Skip SDF injection for non-main scenes. Without correct gating,
        // the SDF would draw on top of every EffectComposer pass output
        // (FXAA, OutputPass, underwater, etc.), losing depth test and
        // any post-process tint — visually: SDFs render ABOVE everything
        // and post-effects never paint on them.
        const sceneIsMain = renderer.__sdfMainScene
            ? scene === renderer.__sdfMainScene
            : !_isPostPassQuadScene(scene);
        if (!sceneIsMain) {
            return originalRender(scene, camera);
        }

        // 1. Render the user's main scene as-is, including any
        //    overrideMaterial GTAO / SSR / normal pass set on it.
        originalRender(scene, camera);

        // 2. Nothing to overlay if no SDF meshes have been created.
        if (SDF_SHADOW_SCENE.children.length === 0) return;

        // 3. Detect pass type from main scene's overrideMaterial.
        let passType = 0;
        const om = scene.overrideMaterial;
        if (om) {
            if (om.isMeshNormalMaterial ||
                om.name === 'GTAONormalMaterial' ||
                /normal/i.test(om.name || '')) {
                passType = 1;
            } else {
                passType = 2;
            }
        }
        // Detect scene.environment (HDRI) and propagate to any SDF
        // example that opts-in via a uEnvMap / uEnvMapStrength uniform.
        // Examples that want to reflect the actual scene HDRI declare
        // these uniforms; we update them per-frame here so the SDF's
        // chrome/glass/etc. samples the same HDRI three.js's own
        // standard materials are sampling. If no scene.environment is
        // set we drop strength to 0 and the example's shader falls
        // back to whatever neutral value it chooses.
        const envTex = (scene.environment && scene.environment.isTexture)
            ? scene.environment
            : null;
        for (const m of SDF_SHADOW_SCENE.children) {
            const u = m.material && m.material.uniforms;
            if (u) {
                if (u.uPassType) u.uPassType.value = passType;
                if (u.uEnvMap) {
                    u.uEnvMap.value = envTex;
                    if (u.uEnvMapStrength) {
                        u.uEnvMapStrength.value = envTex ? 1.0 : 0.0;
                    }
                }
            }
            // TSL/NodeMaterial SDF meshes (createSdfObject's current path)
            // don't have a generic material.uniforms dict — the pass-type
            // uniform lives on mesh.userData.sdfPassType instead (see
            // _buildSdfNodeMaterial in the "TSL SDF ENGINE" section).
            if (m.userData && m.userData.sdfPassType) {
                m.userData.sdfPassType.value = passType;
            }
        }

        // 4. Render shadow scene (no overrideMaterial) over the
        //    framebuffer with autoClear disabled so we don't wipe the
        //    main scene we just rendered.
        //
        //    contextNode: when a PostProcessing scenePass drives this frame
        //    (auto-enhance), the pass carries a lighting context on
        //    renderer.contextNode — e.g. builtinAOContext, which multiplies
        //    every material's output by an AO texture sample. Our overlay is
        //    a nested render the frame graph doesn't know about: that AO
        //    texture is not bound for it, the sample reads 0, and every SDF
        //    pixel multiplies to BLACK. The overlay must render context-free
        //    (SDF self-shadowing already lives in shade()) — save/null/
        //    restore the context around the draw.
        const saveAutoClear = renderer.autoClear;
        const saveContext = renderer.contextNode;
        renderer.autoClear = false;
        renderer.contextNode = defaultContextNode;
        renderer[REENTRY_GUARD] = true;
        try {
            originalRender(SDF_SHADOW_SCENE, camera);
            // Stamp the composite so the renderAsync twin (below) knows the
            // overlay already landed INSIDE the active pass chain this call.
            renderer.__sdfCompositeStamp = (renderer.__sdfCompositeStamp || 0) + 1;
        } finally {
            renderer[REENTRY_GUARD] = false;
            renderer.autoClear = saveAutoClear;
            renderer.contextNode = saveContext;
        }
    };

    // The engine's frame loop calls renderAsync (render() is legacy on this
    // stack) — without this twin hook the composite never runs and the SDF
    // proxies draw as raw black boxes in the main pass.
    const originalRenderAsync = renderer.renderAsync ? renderer.renderAsync.bind(renderer) : null;
    if (originalRenderAsync) {
        renderer.renderAsync = async function patchedRenderAsync(scene, camera) {
            if (renderer[REENTRY_GUARD] || !scene || !scene.isScene) {
                return originalRenderAsync(scene, camera);
            }
            const sceneIsMain = renderer.__sdfMainScene
                ? scene === renderer.__sdfMainScene
                : !_isPostPassQuadScene(scene);
            if (!sceneIsMain) return originalRenderAsync(scene, camera);
            const stampBefore = renderer.__sdfCompositeStamp || 0;
            await originalRenderAsync(scene, camera);
            if (SDF_SHADOW_SCENE.children.length === 0) return;
            // If a postprocessing chain drove this frame, the main scene
            // rendered through renderer.render() INSIDE that call and the
            // render() patch already composited the overlay into the pass
            // target (where it gets tone-mapped/encoded with everything
            // else). Drawing it AGAIN here would stamp a raw linear-space
            // copy over the finished, display-encoded canvas — the SDFs
            // then read near-black. Skip the direct overlay in that case.
            if ((renderer.__sdfCompositeStamp || 0) > stampBefore) return;
            let passType = 0;
            const om = scene.overrideMaterial;
            if (om) {
                passType = (om.isMeshNormalMaterial || om.name === 'GTAONormalMaterial'
                    || /normal/i.test(om.name || '')) ? 1 : 2;
            }
            const envTex = (scene.environment && scene.environment.isTexture) ? scene.environment : null;
            for (const m of SDF_SHADOW_SCENE.children) {
                const u = m.material && m.material.uniforms;
                if (u) {
                    if (u.uPassType) u.uPassType.value = passType;
                    if (u.uEnvMap) {
                        u.uEnvMap.value = envTex;
                        if (u.uEnvMapStrength) u.uEnvMapStrength.value = envTex ? 1.0 : 0.0;
                    }
                }
                if (m.userData && m.userData.sdfPassType) {
                    m.userData.sdfPassType.value = passType;
                }
            }
            const saveAutoClear = renderer.autoClear;
            renderer.autoClear = false;
            renderer[REENTRY_GUARD] = true;
            try {
                await originalRenderAsync(SDF_SHADOW_SCENE, camera);
            } finally {
                renderer[REENTRY_GUARD] = false;
                renderer.autoClear = saveAutoClear;
            }
        };
    }
}


// =====================================================================
// EXAMPLES — representative map/shade pairs covering quality tiers.
// Import and pass directly to createSdfObject, or copy into your
// own scene script and tune.
//
//   basicSphere   — 'fast' tier smoke test (single sphere, flat shading)
//   stylizedBlob  — 'balanced' tier morphing blob (domain warp, simple
//                    diffuse + fresnel, no micro-detail)
//   detailedCoat  — 'high' tier creature-surface shader: mackerel
//                    stripes over multi-octave fbm, soft shadow,
//                    subsurface-tinted rim, dorsal/belly separation
//   fractalCore   — 'ultra' tier mandelbulb-style infinite detail
//                    (slowest; use only for hero close-ups)
// =====================================================================
const EXAMPLES = {
    // TSL (WebGPU) — ported 2026-07-04, the reference example for the
    // current createSdfObject JS-function map/shade contract. See the
    // "TSL SDF ENGINE" header comment near the top of this file.
    basicSphere: {
        bounds: { min: [-1, -1, -1], max: [1, 1, 1] },
        quality: 'fast',
        map(p) {
            return { dist: SDF_TSL.sdSphere(p, SDF_TSL.float(0.6)), mat: SDF_TSL.float(1.0) };
        },
        shade(p, n /*, mat */) {
            const { vec3, float, normalize, max, dot } = SDF_TSL;
            const L = normalize(vec3(0.5, 0.9, 0.4));
            const d = max(float(0.0), dot(n, L));
            const a = float(0.35).add(float(0.25).mul(n.y.mul(0.5).add(0.5)));
            return vec3(0.85, 0.45, 0.25).mul(a.add(d.mul(0.8)));
        },
        make(opts) {
            return createSdfObject({ ...EXAMPLES.basicSphere, ...(opts || {}) });
        },
    },

    // TSL — ported 2026-07-05 from the GLSL original (domain-warped
    // ellipsoid with smooth-subtracted dimples; animated by `time`).
    stylizedBlob: {
        bounds: { min: [-1.1, -1.1, -1.1], max: [1.1, 1.1, 1.1] },
        quality: 'balanced',
        map(p) {
            const T = SDF_TSL;
            const { vec3, float } = T;
            // Domain warp for irregular blob silhouette
            const w = vec3(
                T.fbm(p.mul(2.0).add(T.time.mul(0.3))),
                T.fbm(p.mul(2.0).add(5.2)),
                T.fbm(p.mul(2.0).add(1.3)),
            ).mul(0.20);
            let d = T.sdEllipsoid(p.add(w), vec3(0.80, 0.62, 0.80));
            // Subtract a few dimples for texture
            d = T.opSmoothSub(T.sdSphere(p.sub(vec3(0.4, 0.2, 0.5)), float(0.10)), d, float(0.05));
            d = T.opSmoothSub(T.sdSphere(p.sub(vec3(-0.3, 0.3, 0.5)), float(0.08)), d, float(0.05));
            return { dist: d, mat: float(1.0) };
        },
        shade(p, n, mat, ctx) {
            const T = SDF_TSL;
            const { vec3, float } = T;
            const L = T.normalize(vec3(0.5, 0.9, 0.4));
            const diff = T.max(float(0.0), T.dot(n, L));
            const amb = float(0.25).add(float(0.30).mul(n.y.mul(0.5).add(0.5)));
            const viewDir = T.normalize(ctx.ro.sub(p));   // LOCAL-space view dir
            const fres = T.pow(float(1.0).sub(T.max(float(0.0), T.dot(n, viewDir))), 3.0);
            const base = T.mix(vec3(0.30, 0.55, 0.85), vec3(0.85, 0.50, 0.70),
                T.fbm(p.mul(3.0)).mul(0.5).add(0.5));
            return base.mul(amb.add(diff.mul(0.85))).add(fres.mul(vec3(0.9, 0.8, 1.0)).mul(0.3));
        },
        make(opts) {
            return createSdfObject({ ...EXAMPLES.stylizedBlob, ...(opts || {}) });
        },
    },

    // A good reference for creature coat shading. Uses multi-octave fbm
    // for domain warp AND for micro-relief, a dorsal/ventral split, and
    // a soft-shadow term so crevices self-darken. Demonstrates the kind
    // of detail density that's trivial in SDF and expensive in MC.
    // TSL — ported 2026-07-05. Reversed-edge GLSL smoothstep(hi, lo, x)
    // calls are rewritten as 1-smoothstep(lo, hi, x): same math, defined
    // behavior in WGSL (reversed edges are formally indeterminate there).
    detailedCoat: {
        bounds: { min: [-0.25, -0.05, -0.30], max: [0.25, 0.55, 0.35] },
        quality: 'high',
        map(p) {
            const T = SDF_TSL;
            const { vec3, float } = T;
            // Stylized torso — multi-part capsule chain
            let body = T.sdCap2(p,
                vec3(0.0, 0.22, 0.15),
                vec3(0.0, 0.22, -0.05),
                float(0.09), float(0.07));
            body = T.smin(body,
                T.sdSphere(p.sub(vec3(0.0, 0.34, 0.20)), float(0.08)), float(0.05));
            // Micro-relief from fbm (lumpy, organic skin)
            const micro = T.fbm(p.mul(18.0)).sub(0.5).mul(0.008);
            return { dist: body.add(micro), mat: float(1.0) };
        },
        shade(p, n, mat, ctx) {
            const T = SDF_TSL;
            const { vec3, float } = T;
            // Mackerel tabby palette
            const dark = vec3(0.22, 0.12, 0.06);
            const warm = vec3(0.55, 0.32, 0.14);
            const black = vec3(0.02, 0.01, 0.01);
            const belly = vec3(0.82, 0.52, 0.24);

            // Warp for organic fur variation
            const w = vec3(T.fbm(p.mul(8.0)), T.fbm(p.mul(8.0).add(5.2)), T.fbm(p.mul(8.0).add(1.3))).mul(0.04);
            const pw = p.add(w);

            // Base color
            let coat = T.mix(dark, warm, T.fbm6(pw.mul(4.0)));

            // Stripes perpendicular to spine (z-axis) + spot breakup
            let stripe = T.smoothstep(0.40, 0.75, T.sin(pw.z.mul(70.0).add(T.fbm(pw.mul(6.0)).mul(4.0))));
            stripe = stripe.mul(T.smoothstep(0.35, 0.55, T.fbm(pw.mul(14.0))));
            stripe = stripe.mul(T.smoothstep(-0.3, 0.4, n.y));
            coat = T.mix(coat, black, stripe.mul(0.9));

            // Dorsal spine line
            const spine = float(1.0).sub(T.smoothstep(0.0, 0.015, T.abs(p.x)))
                .mul(T.smoothstep(0.3, 0.8, n.y));
            coat = T.mix(coat, black, spine.mul(0.7));

            // Orangish belly (both factors were reversed-edge in the GLSL)
            const b = float(1.0).sub(T.smoothstep(0.16, 0.22, p.y))
                .mul(float(1.0).sub(T.smoothstep(-0.6, -0.2, n.y)));
            coat = T.mix(coat, belly, b);

            // Light + soft self-shadow
            const L = T.normalize(vec3(0.6, 1.2, 0.4));
            const diff = T.max(float(0.0), T.dot(n, L));
            const sh = ctx.softShadow(p.add(n.mul(0.002)), L, 0.01, 1.5, float(12.0));
            const amb = float(0.28).add(float(0.22).mul(n.y.mul(0.5).add(0.5)));
            // Subsurface-tinted rim
            const viewDir = T.normalize(ctx.ro.sub(p));
            const fres = T.pow(float(1.0).sub(T.max(float(0.0), T.dot(n, viewDir))), 4.0);
            return coat.mul(amb.add(diff.mul(0.85).mul(sh)))
                .add(fres.mul(vec3(0.45, 0.22, 0.10)).mul(0.35));
        },
        make(opts) {
            return createSdfObject({ ...EXAMPLES.detailedCoat, ...(opts || {}) });
        },
    },

    // Infinite-detail reference — a mandelbulb-style escape-time
    // fractal. VERY expensive, intended for single hero stills. Shows
    // that SDF detail can scale arbitrarily without a polygon budget.
    // TSL — ported 2026-07-05. Escape-time mandelbulb (POWER=8) with the
    // loop as TSL Loop/If/Break over toVar() accumulators. r is clamped
    // away from 0 before log() so the distance never goes -inf/NaN.
    fractalCore: {
        bounds: { min: [-1.5, -1.5, -1.5], max: [1.5, 1.5, 1.5] },
        quality: 'ultra',
        map(p) {
            const T = SDF_TSL;
            const { vec3, float } = T;
            const POWER = 8.0;
            const z = vec3(p).toVar();
            const dr = float(1.0).toVar();
            const r = float(0.0).toVar();
            T.Loop({ start: 0, end: 8, type: 'int' }, () => {
                r.assign(T.length(z));
                T.If(r.greaterThan(2.0), () => { T.Break(); });
                const theta = T.acos(z.z.div(r.max(1e-6))).mul(POWER);
                const phi = T.atan(z.y, z.x).mul(POWER);
                dr.assign(T.pow(r, POWER - 1.0).mul(POWER).mul(dr).add(1.0));
                const zr = T.pow(r, POWER);
                z.assign(vec3(
                    T.sin(theta).mul(T.cos(phi)),
                    T.sin(theta).mul(T.sin(phi)),
                    T.cos(theta),
                ).mul(zr).add(p));
            });
            const dist = T.log(r.max(1e-6)).mul(0.5).mul(r).div(dr);
            return { dist, mat: float(1.0) };
        },
        shade(p, n, mat, ctx) {
            const T = SDF_TSL;
            const { vec3, float } = T;
            const L = T.normalize(vec3(0.5, 0.9, 0.4));
            const diff = T.max(float(0.0), T.dot(n, L));
            const amb = float(0.20).add(float(0.25).mul(n.y.mul(0.5).add(0.5)));
            // Iterate-count-like tint from normal variance
            const t = T.fbm(p.mul(3.0));
            const base = T.mix(vec3(0.15, 0.35, 0.75), vec3(0.95, 0.55, 0.20), t);
            const viewDir = T.normalize(ctx.ro.sub(p));
            const fres = T.pow(float(1.0).sub(T.max(float(0.0), T.dot(n, viewDir))), 5.0);
            return base.mul(amb.add(diff.mul(0.8))).add(fres.mul(vec3(1.0, 0.7, 0.4)).mul(0.4));
        },
        make(opts) {
            return createSdfObject({ ...EXAMPLES.fractalCore, ...(opts || {}) });
        },
    },
};

// =====================================================================
// Stylized Modern Sedan — a contemporary 4-door car SDF assembled from
// rounded boxes, rounded capped cylinders for wheels, and CSG cuts for
// door / hood / trunk shut-lines, side-window cutouts (notchback), and
// wheel arches. 8 materials: body paint (clearcoat metallic), tinted
// glass, rubber tires, machined-alloy rims, chrome trim/caps, emissive
// headlights, emissive red tail-lights, and matte black plastic for
// the grille and intakes.
//
// Body paint colour and roughness are exposed as live uniforms — call
// EXAMPLES.stylizedModernSedan.make({ paintColor, paintRoughness }) for
// the common case, or pass them via createSdfObject({ ...spec, uniforms })
// for full control. Reading the spec source teaches the SDF construction
// (CSG carving, plane-cutting for window glass, mirror-x for symmetry).
// For a more aggressive, accent-lit variant, see EXAMPLES.stylizedCyberpunkSedan.
//
// Bounds (TIGHT to the actual geometry — no padding):
//   x ±1.05  (mirror housing at pm.x = 0.99 + 0.025 round bevel)
//   y  0.05..1.55
//     The tire is sdRCapCylX(p, h=0.115, r=0.36, rnd=0.05). In that
//     primitive, outer radius equals r (0.31) NOT r+rnd — rnd is a bevel
//     subtracted from the inner core, not added to the outer extent.
//     Tire centered at pm.y=0.36 with outer radius 0.31 → bottom at
//     pm.y = 0.36 - 0.31 = 0.05. (The source comment "outer eff radius
//     0.36" was off by rnd; verified against the formula.)
//   z ±2.4   (front/rear cap rounded edges)
//
// Placement contract — every example in this loader follows this rule:
// `bounds.min` MUST be the actual lowest geometry point, not author
// intent or sloppy padding. To ground an SDF on a plane at world Y:
//
//     mesh.position.y = groundY - bounds.min.y * mesh.scale.y
//
// If bounds are too loose below the geometry, the SDF hovers; too
// tight, the geometry clips into the floor. Always verify bounds by
// evaluating the SDF at the candidate boundary, not by reading
// "intent" comments in the source.
//
// Quality default 'high'. The wheel hub has fine boolean detail —
// the dish-carve smooth radius (k=0.01) and the air gap between the
// chrome cap's outboard face and the carved rim's outboard face (~5mm
// at scale 1.0) are both right at the edge of a 'balanced' raymarch's
// surface epsilon. With 'balanced' the marcher fuses those surfaces
// and the rim/cap z-fight, erasing the boolean detail. 'high' gives
// surfEps=0.0005 / maxSteps=192 / stepScale=0.75 — fine enough that
// the cap stays distinct from the dish-carved rim.
EXAMPLES.stylizedModernSedan = {
    // TSL — ported 2026-07-04 from the GLSL original. Body paint colour
    // and roughness are exposed as LIVE uniform nodes (`_u`, built once
    // at module-eval time — see the header comment above this block for
    // bounds/placement notes, which still apply unchanged). All custom
    // CSG helpers (rounded box, capped X-cylinder, quadratic smooth ops)
    // that used to live in the GLSL `extra` string are ported below as
    // plain JS helper methods (`_sdRBox`/`_sdCapCylX`/`_sdRCapCylX`/
    // `_opSU`/`_opSS`/`_opSI`) — there is no `extra`-string hoisting slot
    // in the TSL agent contract, so map()/shade() reach them via the
    // `EXAMPLES.stylizedModernSedan` self-reference (safe: those method
    // bodies only run later, after this whole assignment has completed —
    // createSdfObject destructures `map`/`shade` off this spec object as
    // bare functions, so `this` is NOT bound inside them; every helper
    // call below goes through the explicit `M`/`EXAMPLES...` reference,
    // never `this`).
    bounds: { min: [-1.05, 0.0, -2.4], max: [1.05, 1.55, 2.4] },
    quality: 'high',

    // Live uniforms. Pewter silver / matte-ish default; override per-
    // instance via make({ paintColor, paintRoughness }), or reach in
    // directly via EXAMPLES.stylizedModernSedan._u.uPaint.value = ...
    // NOTE (flagged): unlike the old GLSL path's per-material-instance
    // `uniforms` dict, these nodes are shared on this ONE spec object —
    // every mesh built from EXAMPLES.stylizedModernSedan.make() reads
    // the SAME uPaint/uRough nodes, so multiple simultaneous sedans with
    // different paint colours would all repaint to whichever call ran
    // last. Fine for the single-hero-car case this example targets; a
    // true multi-instance version would need per-call uniform nodes and
    // per-call map/shade closures instead of static object properties.
    _u: {
        uPaint: SDF_TSL.uniform(new THREE.Color(0xc8c8d2)),
        // 0 = mirror, 1 = matte. 0.45 ≈ matte single-stage paint — soft
        // sheen, no clearcoat depth. Reads as a real sedan in matte
        // finish, not a showroom mirror.
        uRough: SDF_TSL.uniform(0.45),
    },

    // Material IDs — match the per-material branches in shade(). Kept
    // as plain numbers (id 7 intentionally unused, matching the GLSL
    // original's numbering so it stays cross-referenceable with the
    // sibling stylizedCyberpunkSedan example).
    _MAT: {
        PAINT: 0.0, GLASS: 1.0, TIRE: 2.0, RIM: 3.0,
        CHROME: 4.0, HEAD: 5.0, TAIL: 6.0, PLASTIC: 8.0,
    },

    // Rounded box that shrinks the half-extents by r before adding the
    // round bevel — produces a tighter, more accurate rounded box than
    // the simple "sdBox(p, b) - r" form. p is already offset by the
    // caller (centered at origin), b/r as in the GLSL original.
    _sdRBox(p, b, r) {
        const T = SDF_TSL;
        const q = T.abs(p).sub(b).add(r);
        return T.length(T.max(q, 0.0)).add(T.min(T.max(q.x, T.max(q.y, q.z)), 0.0)).sub(r);
    },
    // Capped cylinder along the X axis, half-height h, radius r.
    _sdCapCylX(p, h, r) {
        const T = SDF_TSL;
        const d = T.vec2(T.length(p.yz), T.abs(p.x)).sub(T.vec2(r, h));
        return T.min(T.max(d.x, d.y), 0.0).add(T.length(T.max(d, 0.0)));
    },
    // Same as _sdCapCylX with a rounded edge bevel — used for tires and
    // rim discs so the silhouette catches a highlight.
    _sdRCapCylX(p, h, r, rnd) {
        const T = SDF_TSL;
        const d = T.vec2(T.length(p.yz), T.abs(p.x)).sub(T.vec2(r - rnd, h - rnd));
        return T.min(T.max(d.x, d.y), 0.0).add(T.length(T.max(d, 0.0))).sub(rnd);
    },
    // Quadratic smooth ops. Tighter falloff than the engine's boilerplate
    // cubic smin — preserves the car's crisp paneled silhouette. a/b are
    // TSL float nodes (raw distances); k is always a plain JS number at
    // every call site below.
    _opSU(a, b, k) {
        const T = SDF_TSL;
        const h = T.max(T.float(k).sub(T.abs(a.sub(b))), 0.0).div(k);
        return T.min(a, b).sub(h.mul(h).mul(k).mul(0.25));
    },
    _opSS(a, b, k) {
        const T = SDF_TSL;
        const h = T.max(T.float(k).sub(T.abs(a.negate().sub(b))), 0.0).div(k);
        return T.max(a.negate(), b).add(h.mul(h).mul(k).mul(0.25));
    },
    _opSI(a, b, k) {
        const T = SDF_TSL;
        const h = T.max(T.float(k).sub(T.abs(a.sub(b))), 0.0).div(k);
        return T.max(a, b).add(h.mul(h).mul(k).mul(0.25));
    },

    // The whole car — ported 1:1 from the GLSL sdCar(vec3 p). Returns
    // { dist, mat } like every other map() in this file.
    _sdCar(p) {
        const T = SDF_TSL;
        const { vec3 } = T;
        const M = EXAMPLES.stylizedModernSedan;

        // Mirror across X for left/right symmetry — every primitive
        // below is built once and reflects automatically.
        const pm = vec3(T.abs(p.x), p.y, p.z);

        // === LOWER BODY ===
        let body = M._sdRBox(p.sub(vec3(0.0, 0.60, 0.0)), vec3(0.86, 0.40, 2.15), 0.18);
        const fCap = M._sdRBox(p.sub(vec3(0.0, 0.60, 2.10)), vec3(0.78, 0.38, 0.08), 0.28);
        const rCap = M._sdRBox(p.sub(vec3(0.0, 0.60, -2.10)), vec3(0.80, 0.39, 0.08), 0.26);
        body = M._opSU(body, fCap, 0.10);
        body = M._opSU(body, rCap, 0.10);
        // Hood crease — subtle raise along the centerline.
        const hoodCrease = M._sdRBox(p.sub(vec3(0.0, 0.97, 1.45)), vec3(0.35, 0.02, 0.65), 0.02);
        body = M._opSU(body, hoodCrease, 0.18);

        // === CABIN (greenhouse) ===
        // Notchback profile: A-pillar rakes ~42° from horizontal,
        // C-pillar tips FORWARD as it rises (real sedan geometry).
        let cabin = M._sdRBox(p.sub(vec3(0.0, 1.20, -0.40)), vec3(0.83, 0.20, 1.00), 0.14);
        const aPillarN = T.normalize(vec3(0.0, 1.11, 1.0));
        const aPillarP0 = vec3(0.0, 1.04, 0.60);
        const aPillar = T.dot(p.sub(aPillarP0), aPillarN);
        cabin = M._opSI(cabin, aPillar, 0.04);
        const cPillarN = T.normalize(vec3(0.0, 1.25, -1.0));
        const cPillarP0 = vec3(0.0, 1.04, -1.40);
        const cPillar = T.dot(p.sub(cPillarP0), cPillarN);
        cabin = M._opSI(cabin, cPillar, 0.04);

        let shell = M._opSU(body, cabin, 0.10);

        // === SIDE WINDOW CUTOUTS ===
        // Notchback rear cut at z=-0.72; B-pillar restored at z=-0.05.
        let winCut = M._sdRBox(p.sub(vec3(0.0, 1.20, -0.06)), vec3(0.96, 0.16, 0.76), 0.06);
        winCut = T.max(winCut, aPillar.add(0.03));
        winCut = T.max(winCut, p.z.add(0.72).negate().add(0.03));
        const bPillar = T.sdBox(p.sub(vec3(0.0, 1.20, -0.05)), vec3(0.96, 0.20, 0.030));
        winCut = T.max(winCut, bPillar.negate());
        shell = M._opSS(winCut, shell, 0.02);

        // === WHEEL ARCHES (subtract outer wheel-well wall) ===
        const archInner = T.float(0.45).sub(pm.x);
        const wfC = T.max(T.length(pm.yz.sub(T.vec2(0.36, 1.40))).sub(0.46), archInner);
        const wrC = T.max(T.length(pm.yz.sub(T.vec2(0.36, -1.40))).sub(0.46), archInner);
        shell = M._opSS(wfC, shell, 0.025);
        shell = M._opSS(wrC, shell, 0.025);

        // === DOOR / HOOD / TRUNK SHUT-LINES (thin grooves) ===
        const d1 = T.sdBox(p.sub(vec3(0.0, 0.62, 0.60)), vec3(0.96, 0.38, 0.006));
        const d2 = T.sdBox(p.sub(vec3(0.0, 0.62, -0.05)), vec3(0.96, 0.38, 0.006));
        const d3 = T.sdBox(p.sub(vec3(0.0, 0.62, -0.72)), vec3(0.96, 0.38, 0.006));
        const hoodCut = T.sdBox(p.sub(vec3(0.0, 0.97, 0.65)), vec3(0.96, 0.06, 0.006));
        const trunkCut = T.sdBox(p.sub(vec3(0.0, 0.97, -1.45)), vec3(0.96, 0.06, 0.006));
        let cuts = T.min(T.min(T.min(d1, d2), d3), T.min(hoodCut, trunkCut));
        cuts = T.max(cuts, p.y.sub(1.00));   // only below roof
        cuts = T.max(cuts, T.float(0.20).sub(p.y));   // don't cut into rocker
        shell = T.max(shell, cuts.negate());

        let res = { dist: shell, mat: T.float(M._MAT.PAINT) };

        // === GLASS ===
        let glassBox = M._sdRBox(p.sub(vec3(0.0, 1.20, -0.06)), vec3(0.83, 0.15, 0.76), 0.06);
        glassBox = T.max(glassBox, aPillar.add(0.03));
        glassBox = T.max(glassBox, p.z.add(0.72).negate().add(0.03));
        glassBox = T.max(glassBox, bPillar.negate());
        // Windshield slab on the A-pillar plane.
        const wsP = T.abs(T.dot(p.sub(aPillarP0), aPillarN)).sub(0.012);
        const wsB = T.sdBox(p.sub(vec3(0.0, 1.22, 0.40)), vec3(0.72, 0.18, 0.25));
        const windshield = T.max(wsP, wsB);
        // Rear window slab on the C-pillar plane.
        const rwP = T.abs(T.dot(p.sub(cPillarP0), cPillarN)).sub(0.012);
        const rwB = T.sdBox(p.sub(vec3(0.0, 1.22, -1.175)), vec3(0.72, 0.18, 0.28));
        const rearGlass = T.max(rwP, rwB);
        const glass = T.min(T.min(glassBox, windshield), rearGlass);
        res = T.opU(res, { dist: glass, mat: T.float(M._MAT.GLASS) });

        // === WHEELS ===
        // Tires are annular cylinders so the rim disc is visible through
        // the centre hole.
        const pWF = pm.sub(vec3(0.70, 0.36, 1.40));
        const pWR = pm.sub(vec3(0.70, 0.36, -1.40));
        const tireOutF = M._sdRCapCylX(pWF, 0.115, 0.36, 0.05);
        const tireOutR = M._sdRCapCylX(pWR, 0.115, 0.36, 0.05);
        const tireHoleF = M._sdCapCylX(pWF, 0.13, 0.20);
        const tireHoleR = M._sdCapCylX(pWR, 0.13, 0.20);
        const tireF = T.max(tireOutF, tireHoleF.negate());
        const tireRe = T.max(tireOutR, tireHoleR.negate());
        res = T.opU(res, { dist: T.min(tireF, tireRe), mat: T.float(M._MAT.TIRE) });

        // Rim disc with recessed dish + chrome cap. The rim assembly
        // (rim + dish + cap) is shifted +27mm outboard from a "flush
        // with tire face" position so the rim's flat outboard face sits
        // ~15mm IN FRONT of the tire's outboard face. Up close this
        // reads as a deep-dish wheel where the rim lip protrudes
        // slightly past the tire sidewall before the dish indent
        // recesses inward to the chrome cap. At LOD distance the
        // dish-carve detail collapses but the rim's solid flat face
        // remains decisively in front of the tire's flat face — opU
        // picks rim metal across the entire wheel-centre radial zone,
        // giving a clean silver disc inside the tire annulus instead of
        // a rim/tire material flicker.
        const rimRad = 0.205;
        const rimHalfW = 0.085;
        const rimOffset = vec3(0.045, 0.0, 0.0);
        const rimF = M._sdRCapCylX(pWF.sub(rimOffset), rimHalfW, rimRad, 0.012);
        const rimRe = M._sdRCapCylX(pWR.sub(rimOffset), rimHalfW, rimRad, 0.012);
        const dishF = M._sdRCapCylX(pWF.sub(vec3(0.087, 0.0, 0.0)), 0.05, rimRad - 0.04, 0.01);
        const dishR = M._sdRCapCylX(pWR.sub(vec3(0.087, 0.0, 0.0)), 0.05, rimRad - 0.04, 0.01);
        const rimFv = M._opSS(dishF, rimF, 0.01);
        const rimRev = M._opSS(dishR, rimRe, 0.01);
        res = T.opU(res, { dist: T.min(rimFv, rimRev), mat: T.float(M._MAT.RIM) });

        // Chrome centre cap (also +27mm outboard with the rim assembly).
        const capF = M._sdRCapCylX(pWF.sub(vec3(0.072, 0.0, 0.0)), 0.04, 0.05, 0.012);
        const capR = M._sdRCapCylX(pWR.sub(vec3(0.072, 0.0, 0.0)), 0.04, 0.05, 0.012);
        res = T.opU(res, { dist: T.min(capF, capR), mat: T.float(M._MAT.CHROME) });

        // === HEADLIGHTS / TAILLIGHTS ===
        const hlP = pm.sub(vec3(0.58, 0.68, 2.18));
        const hl = M._sdRBox(hlP, vec3(0.22, 0.07, 0.05), 0.04);
        res = T.opU(res, { dist: hl, mat: T.float(M._MAT.HEAD) });
        const tlP = pm.sub(vec3(0.58, 0.68, -2.18));
        const tl = M._sdRBox(tlP, vec3(0.26, 0.07, 0.04), 0.03);
        res = T.opU(res, { dist: tl, mat: T.float(M._MAT.TAIL) });

        // === GRILLE / LOWER INTAKE ===
        const grille = M._sdRBox(p.sub(vec3(0.0, 0.55, 2.24)), vec3(0.46, 0.08, 0.02), 0.03);
        const lowIntake = M._sdRBox(p.sub(vec3(0.0, 0.33, 2.22)), vec3(0.62, 0.07, 0.02), 0.03);
        res = T.opU(res, { dist: T.min(grille, lowIntake), mat: T.float(M._MAT.PLASTIC) });

        // === SIDE MIRRORS ===
        const smP = pm.sub(vec3(0.94, 1.07, 0.42));
        const mir = M._sdRBox(smP, vec3(0.05, 0.04, 0.075), 0.025);
        const arm = M._sdRBox(pm.sub(vec3(0.83, 1.05, 0.42)), vec3(0.045, 0.014, 0.025), 0.012);
        const mirror = M._opSU(mir, arm, 0.04);
        res = T.opU(res, { dist: mirror, mat: T.float(M._MAT.PAINT) });

        // === DOOR HANDLES (chrome) ===
        const h1 = M._sdRBox(pm.sub(vec3(0.85, 0.80, 0.30)), vec3(0.015, 0.015, 0.09), 0.01);
        const h2 = M._sdRBox(pm.sub(vec3(0.85, 0.80, -0.40)), vec3(0.015, 0.015, 0.09), 0.01);
        res = T.opU(res, { dist: T.min(h1, h2), mat: T.float(M._MAT.CHROME) });

        // === WINDOW BELT TRIM (thin chrome strip) ===
        let trim = M._sdRBox(p.sub(vec3(0.0, 0.99, -0.06)), vec3(0.81, 0.008, 0.78), 0.004);
        trim = T.max(trim, aPillar.add(0.02));
        trim = T.max(trim, p.z.add(0.72).negate().add(0.02));
        res = T.opU(res, { dist: trim, mat: T.float(M._MAT.CHROME) });

        return res;
    },

    map(p) {
        return EXAMPLES.stylizedModernSedan._sdCar(p);
    },

    // Procedural studio sky used as the chrome / glass / paint
    // environment lookup. Self-contained — doesn't read scene textures,
    // so the SDF still composites correctly into the user's actual
    // scene through the depth buffer. (In the GLSL original this helper
    // existed but was unused — shading called sampleEnvMap/sdfReflectWorld
    // instead. Neither has a TSL equivalent yet — see the file's "TSL SDF
    // ENGINE" KNOWN GAPS note — so this port promotes _sedanSky into the
    // actual env lookup used by shade() below. Flagged in the port report.)
    _sedanSky(rd) {
        const T = SDF_TSL;
        const { vec3 } = T;
        const t = T.clamp(rd.y.mul(0.5).add(0.5), 0.0, 1.0);
        const zen = vec3(0.02, 0.025, 0.035);
        const hor = vec3(0.22, 0.20, 0.18);
        const col = T.mix(hor, zen, T.pow(t, 0.6)).toVar();
        const keyDir = T.normalize(vec3(0.4, 0.55, 0.25));
        col.addAssign(vec3(1.1, 0.95, 0.75).mul(T.pow(T.max(T.dot(rd, keyDir), 0.0), 6.0)).mul(0.6));
        const fillDir = T.normalize(vec3(-0.55, 0.35, -0.5));
        col.addAssign(vec3(0.35, 0.45, 0.6).mul(T.pow(T.max(T.dot(rd, fillDir), 0.0), 3.0)).mul(0.25));
        col.addAssign(vec3(0.9, 0.6, 0.3).mul(0.08).mul(T.exp(T.abs(rd.y).mul(-18.0))));
        return col;
    },

    // Cheap AO from a few sphere-trace samples along the surface normal.
    // Keeps wheel-well shadowing and panel-corner contact shading even
    // when the agent doesn't enable GTAO. Fixed 5-sample unroll (JS for-
    // loop, same convention as the engine's own fbm/fbm6 — compile-time
    // known iteration count, not a runtime T.Loop) — calls the FULL car
    // SDF 5 times per shaded fragment, same cost as the GLSL original.
    _sedanAO(p, n) {
        const T = SDF_TSL;
        const M = EXAMPLES.stylizedModernSedan;
        let occ = T.float(0.0);
        let sca = 1.0;
        for (let i = 0; i < 5; i++) {
            const hr = 0.01 + 0.14 * i / 4.0;
            const dd = M._sdCar(p.add(n.mul(hr))).dist;
            occ = occ.add(T.float(hr).sub(dd).mul(sca));
            sca *= 0.92;
        }
        return T.clamp(T.float(1.0).sub(occ.mul(2.5)), 0.0, 1.0);
    },

    shade(p, n, mat, ctx) {
        const T = SDF_TSL;
        const { vec3 } = T;
        const M = EXAMPLES.stylizedModernSedan;

        const SUN_DIR = T.normalize(vec3(0.45, 0.78, 0.30));
        // LOCAL-space view dir per the agent contract (ctx.ro is the
        // LOCAL-space camera; never cameraPosition directly here).
        const V = T.normalize(ctx.ro.sub(p));
        const rd = V.negate();
        const H = T.normalize(SUN_DIR.add(V));
        const NdL = T.max(T.dot(n, SUN_DIR), 0.0);
        const NdV = T.max(T.dot(n, V), 0.0);
        const NdH = T.max(T.dot(n, H), 0.0);

        const sh = ctx.softShadow(p.add(n.mul(0.004)), SUN_DIR, 0.01, 12.0, T.float(24.0));
        const ao = M._sedanAO(p, n);
        const fres = T.pow(T.float(1.0).sub(NdV), 5.0);

        // KNOWN GAP (flagged): sampleEnvMap/sdfReflectWorld have no TSL
        // equivalent on this engine yet. Approximated with the
        // procedural _sedanSky dome above, sampled along a WORLD-space
        // reflection vector (modelWorldMatrix-transformed n/rd) so a
        // rotated car still reflects a stable, world-oriented sky
        // instead of one that spins with the mesh.
        const nWorld = T.normalize(T.modelWorldMatrix.mul(T.vec4(n, 0.0)).xyz);
        const rdWorld = T.normalize(T.modelWorldMatrix.mul(T.vec4(rd, 0.0)).xyz);
        const envR = M._sedanSky(T.reflect(rdWorld, nWorld));
        const sun = vec3(1.15, 1.05, 0.85);
        const sky = M._sedanSky(vec3(0.0, 1.0, 0.0));

        const col = vec3(0.0).toVar();

        T.If(mat.equal(M._MAT.PAINT), () => {
            // Matte metallic paint — picks up the env dome softly (rough
            // surface scatters reflections), with a per-position
            // metallic-fleck speckle. No clearcoat pop. Reads as a real
            // sedan finish, not a showroom mirror.
            const base = M._u.uPaint;
            const rough = T.max(M._u.uRough, 0.35);
            const metallic = 0.55;
            // Two-scale fleck noise — coarse + fine — so the body reads
            // as metallic paint rather than flat colour.
            const fleckHi = T.fract(T.sin(T.dot(T.floor(p.mul(320.0)), vec3(12.9, 78.2, 37.7))).mul(43758.5));
            const fleckLo = T.fract(T.sin(T.dot(T.floor(p.mul(80.0)), vec3(45.3, 19.7, 91.1))).mul(24831.7));
            const fleck = T.mix(fleckLo, fleckHi, 0.6);
            const fleckTint = base.add(fleck.sub(0.5).mul(0.08));
            const diffuse = fleckTint.mul(NdL.mul(sh).mul(sun).mul(0.6).add(sky.mul(ao).mul(0.30)));
            const a = rough.mul(rough);
            const D = a.div(T.float(3.14159).mul(T.pow(NdH.mul(NdH).mul(a.sub(1.0)).add(1.0), 2.0)));
            const F = T.mix(vec3(0.04), base, metallic);
            const sunSpec = sun.mul(D).mul(F).mul(sh).mul(0.7);
            // Keep meaningful env reflection scaled by roughness — matte
            // but still picks up the sky dome.
            const envCol = envR.mul(F).mul(T.float(1.0).sub(rough.mul(0.6)));
            col.assign(diffuse.add(envCol).add(sunSpec));
            col.mulAssign(T.mix(0.65, 1.0, ao));
        }).Else(() => {
            T.If(mat.equal(M._MAT.GLASS), () => {
                const tint = vec3(0.01, 0.012, 0.018);
                col.assign(tint.add(envR.mul(fres.mul(0.9).add(0.08))));
                col.addAssign(sky.mul(0.02));
                col.addAssign(sun.mul(T.pow(NdH, 80.0)).mul(sh).mul(0.6));
            }).Else(() => {
                T.If(mat.equal(M._MAT.TIRE), () => {
                    const base = vec3(0.025, 0.025, 0.028);
                    col.assign(base.mul(NdL.mul(sh).mul(sun).add(sky.mul(ao)).add(0.04)));
                    col.addAssign(envR.mul(0.03).mul(fres));
                }).Else(() => {
                    T.If(mat.equal(M._MAT.RIM), () => {
                        // Polished alloy. Dropped roughness so the carved
                        // dish and rim lip pick up the sky dome clearly —
                        // chrome cap and rim metal read in the same
                        // family rather than rim-as-painted-grey +
                        // cap-as-mirror.
                        const base = vec3(0.62, 0.62, 0.66);
                        const F = T.mix(vec3(0.04), base, 0.85);
                        col.assign(base.mul(NdL.mul(sh).mul(sun).mul(0.25).add(sky.mul(ao).mul(0.4))));
                        col.addAssign(envR.mul(F).mul(fres.mul(0.5).add(0.6)));
                        col.addAssign(sun.mul(T.pow(NdH, 200.0)).mul(sh).mul(1.2));
                    }).Else(() => {
                        T.If(mat.equal(M._MAT.CHROME), () => {
                            col.assign(envR.mul(fres.mul(0.85).add(0.5)));
                            col.addAssign(sun.mul(T.pow(NdH, 200.0)).mul(sh).mul(2.0));
                            col.mulAssign(0.95);
                        }).Else(() => {
                            T.If(mat.equal(M._MAT.HEAD), () => {
                                const emit = vec3(1.6, 1.55, 1.35);
                                const core = T.pow(T.float(1.0).sub(fres), 3.0);
                                col.assign(emit.mul(core.mul(1.4).add(0.55)));
                                col.addAssign(envR.mul(fres).mul(0.5));
                                col.addAssign(sun.mul(T.pow(NdH, 200.0)).mul(sh).mul(1.2));
                            }).Else(() => {
                                T.If(mat.equal(M._MAT.TAIL), () => {
                                    const redEmit = vec3(1.9, 0.10, 0.05);
                                    const core = T.mix(0.7, 1.2, T.pow(T.float(1.0).sub(fres), 2.0));
                                    col.assign(redEmit.mul(core));
                                    col.addAssign(envR.mul(fres).mul(0.25));
                                    col.addAssign(vec3(1.0, 0.4, 0.3).mul(T.pow(NdH, 80.0)).mul(sh).mul(0.4));
                                }).Else(() => {
                                    // MAT_PLASTIC — matte black grille / lower intake.
                                    const base = vec3(0.02, 0.02, 0.022);
                                    col.assign(base.mul(NdL.mul(sh).mul(sun).mul(0.5).add(sky.mul(ao))).add(envR.mul(fres).mul(0.1)));
                                    col.addAssign(sun.mul(T.pow(NdH, 12.0)).mul(sh).mul(0.15));
                                });
                            });
                        });
                    });
                });
            });
        });

        return col;
    },

    /**
     * Direct-call factory. Returns a configured SDF mesh ready to be
     * positioned / scaled / rotated.
     *
     * Options:
     *   paintColor:     hex (0xff2d95) / THREE.Color / [r,g,b] (0..1)
     *                   Default: pewter silver.
     *   paintRoughness: 0..1. 0 = mirror-smooth show-car wax,
     *                   ~0.18 = factory semi-gloss, ~0.4 = matte / wrap
     *                   finish (default ~0.45).
     */
    make(opts) {
        opts = opts || {};
        const M = EXAMPLES.stylizedModernSedan;
        const sdf = createSdfObject({ ...M });
        if (opts.paintColor !== undefined) {
            M._u.uPaint.value = new THREE.Color(opts.paintColor);
        }
        if (opts.paintRoughness !== undefined) {
            M._u.uRough.value = opts.paintRoughness;
        }
        sdf.userData.sdfLiveUniforms = M._u;
        return sdf;
    },
};

// =====================================================================
// Stylized Cyberpunk Sedan — same notchback proportions as the modern
// sedan but with accent-lit body geometry: full-width LED headlight bar,
// stacked round taillights (3 per side), 3 roof pods with slanted faces,
// gill vents behind rear wheel, hood louvers flanking the centre crease,
// trunk chevron seams, hex grille, rocker underglow, front+rear accent
// strips, and a procedural BADGE PLATE rendered via CanvasTexture decal.
//
// The body itself stays near-black; uPaint drives the FRESNEL RIM accent,
// underglow strip, accent strips, and hex grille glow — different
// semantic from the modern sedan where uPaint IS the body colour.
// Asymmetric racing stripes are baked into the paint shader (right side:
// hood diagonal + door tape + rocker tape + speed comb + number block +
// trunk diagonal + dual roof; left side: rear-door diagonal + vertical
// fender comb + triangle wedge + parallel trunk lines + single roof +
// rocker line). Different visual vocabulary per side, same designer's
// hand — teaches procedural surface decoration via shader masks.
//
// The badge plate samples uDecal (a CanvasTexture built at module-eval
// time from a 5x7 pixel-font atlas — see _buildBadgeDecal). This is the
// teaching example for "how do I put procedurally-drawn text onto an
// SDF surface": draw glyphs onto a 2D canvas, wrap with CanvasTexture,
// pass as a sampler2D uniform, sample in the shade branch by UV-
// unwrapping the local surface coordinates onto the plate face.
//
// Bounds match the modern sedan (same body geometry):
//   x ±1.05, y 0.05..1.55, z ±2.4 — see modern sedan docs for derivation.
//
// Quality default 'high' (same boolean-detail concerns as modern sedan).
//
// Tunables via make({ paintColor, paintRoughness, decalText }).
// =====================================================================

// 5x7 pixel font for the badge decal. '#' is a filled cell, '.' is empty.
// Add more glyphs here (and update _BADGE_GLYPHS_NOTE if you want to
// declare the supported alphabet). Reading the patterns is the cheapest
// way to learn block-segment letterforms — the sci-fi HUD-font aesthetic
// without any external font dependency.
const _BADGE_GLYPH_ATLAS = {
    'A': ['.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'L': ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
    'E': ['#####', '#....', '#....', '####.', '#....', '#....', '#####'],
    'T': ['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..'],
    'H': ['#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    '8': ['.###.', '#...#', '#...#', '.###.', '#...#', '#...#', '.###.'],
    'P': ['####.', '#...#', '#...#', '####.', '#....', '#....', '#....'],
    'O': ['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
};

// Builds a CanvasTexture by drawing `text` onto a 1024x256 canvas via
// the 5x7 glyph atlas above. Glyphs not in the atlas are skipped silently
// (extend _BADGE_GLYPH_ATLAS to support more characters). Returns null
// in headless contexts where `document` is unavailable, so the loader
// stays importable in non-browser environments — though in practice the
// loader runs inside puppeteer/chromium where `document` is always
// present.
function _buildBadgeDecal(text) {
    if (typeof document === 'undefined') return null;
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, 1024, 256);
    ctx.fillStyle = '#ffffff';

    const cellW = 14, cellH = 14, cols = 5, rows = 7;
    const gap = cellW;                 // 1-cell gap between glyphs
    const glyphPxW = cols * cellW;
    const totalW = text.length * glyphPxW + (text.length - 1) * gap;
    const startX = (canvas.width  - totalW) / 2;
    const startY = (canvas.height - rows * cellH) / 2;

    for (let i = 0; i < text.length; i++) {
        const pat = _BADGE_GLYPH_ATLAS[text[i]];
        if (!pat) continue;
        const gx = startX + i * (glyphPxW + gap);
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                if (pat[r][c] === '#') {
                    ctx.fillRect(
                        gx + c * cellW,
                        startY + r * cellH,
                        cellW - 2,
                        cellH - 2,
                    );
                }
            }
        }
    }

    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    tex.needsUpdate = true;
    return tex;
}

// Lazy default. Built on first access so module evaluation in headless
// contexts (where `document` may not exist) doesn't throw — and so that
// callers who never use the cyberpunk sedan don't pay the canvas-draw
// cost.
let _defaultBadgeDecal = null;
function _getDefaultBadgeDecal() {
    if (_defaultBadgeDecal === null) {
        _defaultBadgeDecal = _buildBadgeDecal('ALETH8APO');
    }
    return _defaultBadgeDecal;
}

EXAMPLES.stylizedCyberpunkSedan = {
    bounds: { min: [-1.05, 0.0, -2.4], max: [1.05, 1.55, 2.4] },
    quality: 'high',

    // Live TSL uniforms (see the "TSL SDF ENGINE" header comment's
    // uniform-porting rule). uPaint drives the fresnel rim + underglow
    // + accent strips + hex grille glow — NOT the body base colour
    // (that stays near-black for the cyberpunk look, same semantic as
    // the old GLSL uPaint/uRough uniforms). uRough is floored at 0.20
    // inside shade() so even make({ paintRoughness: 0 }) keeps a hint
    // of texture on the body.
    //
    // NOTE: `_u` (and `_decalTex` below) live once on this spec object
    // and are mutated in place by make() — matching the porting rule's
    // documented pattern. Unlike the old GLSL path (where every
    // make() call built an independent ShaderMaterial with its own
    // `uniforms` dict), TSL `uniform()` nodes referenced from a shared
    // `_u` are LIVE and shared: two simultaneous cyberpunk sedans made
    // via back-to-back make({ paintColor }) calls will both end up
    // showing whichever paintColor/paintRoughness was set LAST, since
    // both materials' compiled graphs reference the same uniform node
    // instances. Flagged as a known behavior change from the GLSL
    // original — fine for the common single-hero-car case this loader
    // targets, but not safe for a multi-sedan lineup with different
    // liveries without further work (per-instance `_u`/`_decalTex`
    // would require map/shade to be built as per-call factories).
    _u: {
        uPaint: SDF_TSL.uniform(new THREE.Color(0x00e7ff)),
        uRough: SDF_TSL.uniform(0.18),
    },
    // Plain captured CanvasTexture reference (NOT a TSL uniform() node
    // — textures are sampled by direct reference via THREE.textureLevel
    // in the MAT_BADGE shade branch, per the porting rule). Overridden
    // in place by make({ decalText }).
    _decalTex: _getDefaultBadgeDecal(),

    // =================================================================
    // SDF primitives — kept INLINE and NESTED inside _sdCar (mirrors
    // the old GLSL `extra` string's "kept inline so this example reads
    // end-to-end without cross-referencing the modern sedan" design
    // intent). IMPORTANT: sdRBox here uses a DIFFERENT rounded-box
    // convention than the shared SDF_TSL.sdRoundBox — here `b` is the
    // OUTER half-extent and `r` only rounds the corners (the box
    // occupies exactly [-b,b] regardless of r), whereas
    // SDF_TSL.sdRoundBox treats `b` as the core box size and bloats it
    // outward by `r`. These are NOT interchangeable — reusing the
    // shared library's sdRoundBox here would shrink/grow every panel
    // in this model and break the bounds math documented at the top of
    // the GLSL original. So sdRBox/sdCapCylX/sdRCapCylX/opSU/opSS/opSI
    // stay local, exactly like the GLSL source declared them locally.
    // =================================================================
    _sdCar(p) {
        const T = SDF_TSL;
        const { vec2, vec3, float } = T;

        function sdRBox(pp, b, r) {
            const q = T.abs(pp).sub(b).add(r);
            return T.min(T.max(q.x, T.max(q.y, q.z)), 0.0).add(T.length(T.max(q, 0.0))).sub(r);
        }
        function sdCapCylX(pp, h, r) {
            const d = vec2(T.length(pp.yz), T.abs(pp.x)).sub(vec2(r, h));
            return T.min(T.max(d.x, d.y), 0.0).add(T.length(T.max(d, 0.0)));
        }
        function sdRCapCylX(pp, h, r, rnd) {
            const d = vec2(T.length(pp.yz), T.abs(pp.x)).sub(vec2(r - rnd, h - rnd));
            return T.min(T.max(d.x, d.y), 0.0).add(T.length(T.max(d, 0.0))).sub(rnd);
        }
        // Smooth union / subtraction / intersection — quadratic-polynomial
        // smoothing (Inigo Quilez's opSU/opSS/opSI), same formulas as the
        // GLSL local versions (distinct from the shared library's
        // exponential smin/smax).
        function opSU(a, b, k) {
            const h = T.max(float(k).sub(T.abs(a.sub(b))), 0.0).div(k);
            return T.min(a, b).sub(h.mul(h).mul(k).mul(0.25));
        }
        function opSS(a, b, k) {
            const h = T.max(float(k).sub(T.abs(a.negate().sub(b))), 0.0).div(k);
            return T.max(a.negate(), b).add(h.mul(h).mul(k).mul(0.25));
        }
        function opSI(a, b, k) {
            const h = T.max(float(k).sub(T.abs(a.sub(b))), 0.0).div(k);
            return T.max(a, b).add(h.mul(h).mul(k).mul(0.25));
        }
        // Shared "flat slot" shape used by both the hood louvers and the
        // trunk chevron seams: distance to a line segment a->b, rounded
        // by r in the local XZ plane and clipped to a half-height hh in
        // Y (a rounded-XZ / hard-Y capsule-like slab). Factored out of
        // the GLSL's 5x-repeated dl1..dl5 / ts1/ts2 inline math — same
        // formula, DRY'd into one helper (not a dropped feature: every
        // call site below reproduces the exact same math the GLSL wrote
        // out longhand).
        function sdSlotSeg(pp, a, b, r, hh) {
            const ba = b.sub(a);
            const pa = pp.sub(a);
            const h = T.clamp(T.dot(pa, ba).div(T.dot(ba, ba)), 0.0, 1.0);
            const d = pa.sub(ba.mul(h));
            return T.max(T.length(d.xz).sub(r), T.abs(d.y).sub(hh));
        }

        // Material IDs — matches the GLSL #define block exactly (RIM is
        // defined but never assigned below, same as the GLSL original —
        // it's dead code inherited from the modern-sedan shade function
        // this example's shade() was adapted from; ported faithfully
        // rather than silently dropped).
        const MAT = {
            PAINT: 0.0, GLASS: 1.0, TIRE: 2.0, RIM: 3.0, CHROME: 4.0,
            HEAD: 5.0, TAIL: 6.0, PLASTIC: 8.0, UNDERGLOW: 9.0,
            ACCENT: 10.0, GRILLE: 11.0, BADGE: 12.0,
        };

        const pm = vec3(T.abs(p.x), p.y, p.z);

        // === LOWER BODY ===
        let body = sdRBox(p.sub(vec3(0.0, 0.60, 0.0)), vec3(0.86, 0.40, 2.15), 0.18);
        const fCap = sdRBox(p.sub(vec3(0.0, 0.60, 2.10)), vec3(0.78, 0.38, 0.08), 0.28);
        const rCap = sdRBox(p.sub(vec3(0.0, 0.60, -2.10)), vec3(0.80, 0.39, 0.08), 0.26);
        body = opSU(body, fCap, 0.10);
        body = opSU(body, rCap, 0.10);
        const hoodCrease = sdRBox(p.sub(vec3(0.0, 0.97, 1.50)), vec3(0.35, 0.02, 0.55), 0.02);
        body = opSU(body, hoodCrease, 0.18);

        // === CABIN (notchback profile, A/C-pillars) ===
        let cabin = sdRBox(p.sub(vec3(0.0, 1.20, -0.40)), vec3(0.83, 0.20, 1.00), 0.14);
        const aPillarN = T.normalize(vec3(0.0, 1.11, 1.0));
        const aPillarP0 = vec3(0.0, 1.04, 0.60);
        const aPillar = T.dot(p.sub(aPillarP0), aPillarN);
        cabin = opSI(cabin, aPillar, 0.04);
        const cPillarN = T.normalize(vec3(0.0, 1.25, -1.0));
        const cPillarP0 = vec3(0.0, 1.04, -1.40);
        const cPillar = T.dot(p.sub(cPillarP0), cPillarN);
        cabin = opSI(cabin, cPillar, 0.04);

        let shell = opSU(body, cabin, 0.10);

        // === SIDE WINDOW CUTOUTS (notchback rear cut + B-pillar) ===
        let winCut = sdRBox(p.sub(vec3(0.0, 1.20, -0.06)), vec3(0.96, 0.16, 0.76), 0.06);
        winCut = T.max(winCut, aPillar.add(0.03));
        winCut = T.max(winCut, p.z.add(0.72).negate().add(0.03));
        const bPillar = T.sdBox(p.sub(vec3(0.0, 1.20, -0.05)), vec3(0.96, 0.20, 0.030));
        winCut = T.max(winCut, bPillar.negate());
        shell = opSS(winCut, shell, 0.02);

        // === WHEEL ARCHES ===
        const archInner = float(0.45).sub(pm.x);
        const wfC = T.max(T.length(pm.yz.sub(vec2(0.36, 1.40))).sub(0.46), archInner);
        const wrC = T.max(T.length(pm.yz.sub(vec2(0.36, -1.40))).sub(0.46), archInner);
        shell = opSS(wfC, shell, 0.025);
        shell = opSS(wrC, shell, 0.025);

        // === DOOR / HOOD / TRUNK SHUT-LINES ===
        const d1 = T.sdBox(p.sub(vec3(0.0, 0.62, 0.60)), vec3(0.96, 0.38, 0.006));
        const d2 = T.sdBox(p.sub(vec3(0.0, 0.62, -0.05)), vec3(0.96, 0.38, 0.006));
        const d3 = T.sdBox(p.sub(vec3(0.0, 0.62, -0.72)), vec3(0.96, 0.38, 0.006));
        const hoodCut = T.sdBox(p.sub(vec3(0.0, 0.97, 0.65)), vec3(0.96, 0.06, 0.006));
        const trunkCut = T.sdBox(p.sub(vec3(0.0, 0.97, -1.45)), vec3(0.96, 0.06, 0.006));
        let cuts = T.min(T.min(T.min(d1, d2), d3), T.min(hoodCut, trunkCut));
        cuts = T.max(cuts, p.y.sub(1.00));
        cuts = T.max(cuts, float(0.20).sub(p.y));
        shell = T.max(shell, cuts.negate());

        let res = { dist: shell, mat: float(MAT.PAINT) };

        // === GLASS ===
        let glassBox = sdRBox(p.sub(vec3(0.0, 1.20, -0.06)), vec3(0.83, 0.15, 0.76), 0.06);
        glassBox = T.max(glassBox, aPillar.add(0.03));
        glassBox = T.max(glassBox, p.z.add(0.72).negate().add(0.03));
        glassBox = T.max(glassBox, bPillar.negate());
        const wsP = T.abs(T.dot(p.sub(aPillarP0), aPillarN)).sub(0.012);
        const wsB = T.sdBox(p.sub(vec3(0.0, 1.22, 0.40)), vec3(0.72, 0.18, 0.25));
        const windshield = T.max(wsP, wsB);
        const rwP = T.abs(T.dot(p.sub(cPillarP0), cPillarN)).sub(0.012);
        const rwB = T.sdBox(p.sub(vec3(0.0, 1.22, -1.175)), vec3(0.72, 0.18, 0.28));
        const rearGlass = T.max(rwP, rwB);
        const glass = T.min(T.min(glassBox, windshield), rearGlass);
        res = T.opU(res, { dist: glass, mat: float(MAT.GLASS) });

        // === WHEELS (annular tires + dished rims + chrome caps) ===
        const pWF = pm.sub(vec3(0.70, 0.36, 1.40));
        const pWR = pm.sub(vec3(0.70, 0.36, -1.40));
        const tireOutF = sdRCapCylX(pWF, 0.115, 0.36, 0.05);
        const tireOutR = sdRCapCylX(pWR, 0.115, 0.36, 0.05);
        const tireHoleF = sdCapCylX(pWF, 0.13, 0.20);
        const tireHoleR = sdCapCylX(pWR, 0.13, 0.20);
        const tireF = T.max(tireOutF, tireHoleF.negate());
        const tireRe = T.max(tireOutR, tireHoleR.negate());
        res = T.opU(res, { dist: T.min(tireF, tireRe), mat: float(MAT.TIRE) });

        // === CHROME DOME HUBCAP (cyberpunk-only) ===
        // Non-uniformly-scaled sphere (oblate ellipsoid) — see the GLSL
        // original's long derivation comment for why this reads as a
        // genuinely-curved dome rather than a flat disc with a rounded
        // edge (X-axis squashed 6.7x by the (0.15,1,1) scale divisor).
        const domeFP = pWF.sub(vec3(0.135, 0.0, 0.0)).div(vec3(0.15, 1.0, 1.0));
        const domeRP = pWR.sub(vec3(0.135, 0.0, 0.0)).div(vec3(0.15, 1.0, 1.0));
        const domeF = T.length(domeFP).sub(0.24).mul(0.15);
        const domeR = T.length(domeRP).sub(0.24).mul(0.15);
        res = T.opU(res, { dist: T.min(domeF, domeR), mat: float(MAT.CHROME) });

        // === HEADLIGHT BAR (full width, thin LED strip) ===
        const hlBar = sdRBox(p.sub(vec3(0.0, 0.74, 2.20)), vec3(0.66, 0.025, 0.04), 0.012);
        res = T.opU(res, { dist: hlBar, mat: float(MAT.HEAD) });

        // === TAILLIGHTS (3 stacked round disc lenses per side) ===
        const tl1P = pm.sub(vec3(0.66, 0.86, -2.18));
        const tl2P = pm.sub(vec3(0.66, 0.74, -2.18));
        const tl3P = pm.sub(vec3(0.66, 0.62, -2.18));
        const tl1 = T.max(T.length(tl1P.xy).sub(0.045), T.abs(tl1P.z).sub(0.025));
        const tl2 = T.max(T.length(tl2P.xy).sub(0.045), T.abs(tl2P.z).sub(0.025));
        const tl3 = T.max(T.length(tl3P.xy).sub(0.045), T.abs(tl3P.z).sub(0.025));
        const tlStack = T.min(T.min(tl1, tl2), tl3);
        res = T.opU(res, { dist: tlStack, mat: float(MAT.TAIL) });

        // === ROOF PODS (3 paint-material pods, slanted faces) ===
        const pfN = T.normalize(vec3(0.0, 0.6, 0.8));
        const pf_box = sdRBox(p.sub(vec3(0.0, 1.416, 0.18)), vec3(0.10, 0.030, 0.07), 0.014);
        const pf_slant = T.dot(p.sub(vec3(0.0, 1.43, 0.20)), pfN);
        const pod1 = T.max(pf_box, pf_slant);
        const pmid_box = sdRBox(pm.sub(vec3(0.55, 1.416, 0.05)), vec3(0.06, 0.025, 0.07), 0.012);
        const pmid_slant = T.dot(p.sub(vec3(0.0, 1.43, 0.07)), pfN);
        const pod2 = T.max(pmid_box, pmid_slant);
        const prN = T.normalize(vec3(0.0, 0.6, -0.8));
        const pr_box = sdRBox(p.sub(vec3(0.0, 1.416, -0.55)), vec3(0.11, 0.028, 0.07), 0.014);
        const pr_slant = T.dot(p.sub(vec3(0.0, 1.43, -0.57)), prN);
        const pod3 = T.max(pr_box, pr_slant);
        const pods = T.min(T.min(pod1, pod2), pod3);
        res = T.opU(res, { dist: pods, mat: float(MAT.PAINT) });

        // === SUBTRACTIVE SURFACE DETAILS ===
        // gathered here; applied to the body shell further below.

        // GILL VENT (3 vertical slots BEHIND the rear wheel)
        const gillPm = pm.sub(vec3(0.86, 0.78, -2.00));
        const g1 = T.sdBox(gillPm.sub(vec3(0.0, 0.0, 0.05)), vec3(0.014, 0.10, 0.012));
        const g2 = T.sdBox(gillPm.sub(vec3(0.0, 0.0, 0.00)), vec3(0.014, 0.10, 0.012));
        const g3 = T.sdBox(gillPm.sub(vec3(0.0, 0.0, -0.05)), vec3(0.014, 0.10, 0.012));
        const gill = T.min(T.min(g1, g2), g3);

        // HOOD LOUVERS (5 diagonal slats flanking the centre crease)
        let louvers = sdSlotSeg(pm, vec3(0.42, 1.00, 0.85), vec3(0.62, 1.00, 1.05), 0.008, 0.025);
        louvers = T.min(louvers, sdSlotSeg(pm, vec3(0.42, 1.00, 1.10), vec3(0.62, 1.00, 1.30), 0.008, 0.025));
        louvers = T.min(louvers, sdSlotSeg(pm, vec3(0.42, 1.00, 1.35), vec3(0.62, 1.00, 1.55), 0.008, 0.025));
        louvers = T.min(louvers, sdSlotSeg(pm, vec3(0.42, 1.00, 1.60), vec3(0.62, 1.00, 1.80), 0.008, 0.025));
        louvers = T.min(louvers, sdSlotSeg(pm, vec3(0.42, 1.00, 1.85), vec3(0.60, 1.00, 2.00), 0.008, 0.025));
        const hs3 = T.sdBox(p.sub(vec3(0.0, 1.04, 0.78)), vec3(0.18, 0.025, 0.10));
        const hoodSeams = T.min(louvers, hs3);

        // DOOR PANEL DIAGONAL SEAMS (mirrored, rotated capsule slabs).
        // caD/saD are compile-time constants (angle 0.61 rad is a JS
        // literal, never a per-fragment value) — precomputed with plain
        // Math.cos/sin rather than TSL nodes, then used as JS-number
        // coefficients in the node arithmetic below (equivalent to the
        // GLSL's inline `cos(0.61)`/`sin(0.61)` locals).
        const dsP1 = pm.sub(vec3(0.86, 0.60, 0.275));
        const caD = Math.cos(0.61), saD = Math.sin(0.61);
        const dsP1r = vec3(dsP1.x, dsP1.y.mul(caD).add(dsP1.z.mul(saD)), dsP1.y.mul(-saD).add(dsP1.z.mul(caD)));
        const ds1 = T.sdBox(dsP1r, vec3(0.010, 0.005, 0.32));
        const dsP2 = pm.sub(vec3(0.86, 0.60, -0.40));
        const dsP2r = vec3(dsP2.x, dsP2.y.mul(caD).sub(dsP2.z.mul(saD)), dsP2.y.mul(saD).add(dsP2.z.mul(caD)));
        const ds2 = T.sdBox(dsP2r, vec3(0.010, 0.005, 0.32));
        const doorSeams = T.min(ds1, ds2);

        // TRUNK CHEVRON SEAMS (two diagonals + centre inset panel) —
        // same sdSlotSeg shape as the hood louvers, on `p` (not
        // mirrored) since ts1/ts2 are each other's asymmetric pair.
        const ts1 = sdSlotSeg(p, vec3(0.0, 1.00, -1.45), vec3(0.42, 1.00, -2.10), 0.008, 0.025);
        const ts2 = sdSlotSeg(p, vec3(0.0, 1.00, -1.45), vec3(-0.42, 1.00, -2.10), 0.008, 0.025);
        const ts3 = T.sdBox(p.sub(vec3(0.0, 1.00, -1.65)), vec3(0.18, 0.025, 0.05));
        const trunkSeams = T.min(T.min(ts1, ts2), ts3);

        // REAR QUARTER ACCENT LINE (thin horizontal seam)
        const rqLine = T.sdBox(pm.sub(vec3(0.86, 0.55, -1.55)), vec3(0.012, 0.005, 0.55));

        // REAR + FRONT BUMPER PANEL CUTS (two small horizontal panels)
        const rbP1 = T.sdBox(p.sub(vec3(-0.30, 0.30, -2.20)), vec3(0.18, 0.04, 0.012));
        const rbP2 = T.sdBox(p.sub(vec3(0.30, 0.30, -2.20)), vec3(0.18, 0.04, 0.012));
        const rearBumperPanels = T.min(rbP1, rbP2);
        const fbP1 = T.sdBox(p.sub(vec3(-0.30, 0.30, 2.20)), vec3(0.18, 0.04, 0.012));
        const fbP2 = T.sdBox(p.sub(vec3(0.30, 0.30, 2.20)), vec3(0.18, 0.04, 0.012));
        const frontBumperPanels = T.min(fbP1, fbP2);

        // Apply all subtractive cuts to the body shell only (mat==PAINT
        // and not yet replaced by glass — the only two materials res
        // can hold at this point). GLSL used `if (res.y < 0.5)`; TSL has
        // no JS-time branch on a per-fragment node, so select() picks
        // between the cut and uncut distance per the mat comparison.
        let bs = res.dist;
        bs = T.max(bs, gill.negate());
        bs = T.max(bs, hoodSeams.negate());
        bs = T.max(bs, doorSeams.negate());
        bs = T.max(bs, trunkSeams.negate());
        bs = T.max(bs, rqLine.negate());
        bs = T.max(bs, rearBumperPanels.negate());
        bs = T.max(bs, frontBumperPanels.negate());
        res = { dist: T.select(res.mat.lessThan(0.5), bs, res.dist), mat: res.mat };

        // === REAR QUARTER BADGE PLATE (samples uDecal in shade) ===
        const badge = sdRBox(pm.sub(vec3(0.834, 1.15, -0.95)), vec3(0.008, 0.045, 0.16), 0.005);
        res = T.opU(res, { dist: badge, mat: float(MAT.BADGE) });

        // === ACCENT STRIPS (front + rear, emissive uPaint) ===
        const accF = sdRBox(p.sub(vec3(0.0, 0.46, 2.22)), vec3(0.56, 0.010, 0.018), 0.005);
        const accR = sdRBox(p.sub(vec3(0.0, 0.46, -2.22)), vec3(0.56, 0.010, 0.018), 0.005);
        res = T.opU(res, { dist: T.min(accF, accR), mat: float(MAT.ACCENT) });

        // === UNDERGLOW (rocker emissive sliver, between wheels) ===
        const ugStrip = sdRBox(pm.sub(vec3(0.55, 0.21, 0.0)), vec3(0.020, 0.012, 0.95), 0.005);
        res = T.opU(res, { dist: ugStrip, mat: float(MAT.UNDERGLOW) });

        // === HEX GRILLE (procedural cells in shade) ===
        const grille = sdRBox(p.sub(vec3(0.0, 0.55, 2.24)), vec3(0.46, 0.08, 0.02), 0.03);
        res = T.opU(res, { dist: grille, mat: float(MAT.GRILLE) });

        // === LOWER BUMPER INTAKE (matte plastic) ===
        const lowIntake = sdRBox(p.sub(vec3(0.0, 0.33, 2.22)), vec3(0.62, 0.07, 0.02), 0.03);
        res = T.opU(res, { dist: lowIntake, mat: float(MAT.PLASTIC) });

        // === SIDE MIRRORS ===
        const smP = pm.sub(vec3(0.94, 1.07, 0.42));
        const mir = sdRBox(smP, vec3(0.05, 0.04, 0.075), 0.025);
        const arm = sdRBox(pm.sub(vec3(0.83, 1.05, 0.42)), vec3(0.045, 0.014, 0.025), 0.012);
        const mirror = opSU(mir, arm, 0.04);
        res = T.opU(res, { dist: mirror, mat: float(MAT.PAINT) });

        // === DOOR HANDLES (chrome) ===
        const h1 = sdRBox(pm.sub(vec3(0.85, 0.80, 0.30)), vec3(0.015, 0.015, 0.09), 0.01);
        const h2 = sdRBox(pm.sub(vec3(0.85, 0.80, -0.40)), vec3(0.015, 0.015, 0.09), 0.01);
        res = T.opU(res, { dist: T.min(h1, h2), mat: float(MAT.CHROME) });

        // === WINDOW BELT TRIM (chrome strip along cabin belt-line) ===
        let trim = sdRBox(p.sub(vec3(0.0, 0.99, -0.06)), vec3(0.81, 0.008, 0.78), 0.004);
        trim = T.max(trim, aPillar.add(0.02));
        trim = T.max(trim, p.z.add(0.72).negate().add(0.02));
        res = T.opU(res, { dist: trim, mat: float(MAT.CHROME) });

        return res;
    },

    map(p) {
        return EXAMPLES.stylizedCyberpunkSedan._sdCar(p);
    },

    shade(p, n, mat, ctx) {
        const T = SDF_TSL;
        const { vec2, vec3, float } = T;
        const S = EXAMPLES.stylizedCyberpunkSedan;
        const U = S._u;

        // Material IDs — local copy of the same constants used inside
        // _sdCar (kept as a second small literal object rather than a
        // shared closure, since map() and shade() are separate JS
        // functions on this spec; the 12 values never change).
        const MAT = {
            PAINT: 0.0, GLASS: 1.0, TIRE: 2.0, RIM: 3.0, CHROME: 4.0,
            HEAD: 5.0, TAIL: 6.0, PLASTIC: 8.0, UNDERGLOW: 9.0,
            ACCENT: 10.0, GRILLE: 11.0, BADGE: 12.0,
        };

        // GLSL smoothstep(hi, lo, x) with hi > lo is a reversed-edge
        // call (formally indeterminate in WGSL). Every smoothstep in
        // this shader's stripe-mask logic uses that reversed-order
        // "soft mask, 1 near the center fading to 0 at the outer edge"
        // idiom — rewritten here as 1 - smoothstep(lo, hi, x), same
        // math, well-defined on this backend.
        function rstep(hi, lo, x) {
            return float(1.0).sub(T.smoothstep(lo, hi, x));
        }

        // Neutral procedural env reflection — light-gray dome with a
        // slightly brighter sky and slightly darker ground. This is the
        // GLSL original's cyberpunkSky(vec3 rd) helper, which was
        // defined but never actually called there (sampleEnvMap was
        // used instead). This backend has no sampleEnvMap/
        // sdfReflectWorld equivalent yet (see the "TSL SDF ENGINE"
        // header's KNOWN GAPS note), so cyberpunkSky is promoted here
        // to stand in for both `envR` and `sky` below — the intended
        // TSL-era fallback, not a stylized replacement invented for
        // this port.
        function cyberpunkSky(rd) {
            const t = T.clamp(rd.y.mul(0.5).add(0.5), 0.0, 1.0);
            const ground = vec3(0.40, 0.40, 0.42);
            const skyCol = vec3(0.78, 0.80, 0.82);
            return T.mix(ground, skyCol, T.pow(t, 0.7));
        }

        // Per-fragment ambient occlusion via 5 short SDF probes along
        // the normal. Calls S._sdCar directly (shade() has no access to
        // the raw mapFn closure the engine keeps internal — only
        // ctx.softShadow/ctx.calcNormal are exposed — so this reaches
        // the map function via the same EXAMPLES.stylizedCyberpunkSedan
        // self-reference already used by map() above).
        function cyberpunkAO(pp, nn) {
            const occ = float(0.0).toVar();
            const sca = float(1.0).toVar();
            T.Loop({ start: 0, end: 5, type: 'int' }, ({ i }) => {
                const hr = float(0.01).add(float(0.14).mul(i.toFloat()).div(4.0));
                const dd = S._sdCar(pp.add(nn.mul(hr))).dist;
                occ.addAssign(hr.sub(dd).mul(sca));
                sca.mulAssign(0.92);
            });
            return T.clamp(float(1.0).sub(occ.mul(2.5)), 0.0, 1.0);
        }

        // Asymmetric racing-stripe paint mask. RIGHT side (p.x > 0.05)
        // uses diagonal/dual-tape vocabulary; LEFT side (p.x < -0.05)
        // uses wedge/vertical-comb/parallel vocabulary. Returns a 0..1
        // factor used to blend in an off-white decal layer over the
        // dark body. Suppressed inside wheel arches (curved interior
        // reads wrong with stripes designed for flat panels).
        function stripeMaskFn(pp, nn) {
            const m = float(0.0).toVar();
            const pmA = vec3(T.abs(pp.x), pp.y, pp.z);
            const aF = T.length(pmA.yz.sub(vec2(0.36, 1.40))).sub(0.48);
            const aR = T.length(pmA.yz.sub(vec2(0.36, -1.40))).sub(0.48);
            const inArch = pmA.x.greaterThan(0.45).and(T.min(aF, aR).lessThan(0.0));
            const pxz = vec2(pp.x, pp.z);

            T.If(pp.x.greaterThan(0.05), () => {
                // (R1) HOOD DIAGONAL — primary thick + parallel thin.
                const hA = vec2(0.18, 1.05), hB = vec2(0.62, 1.95);
                const dirH = T.normalize(hB.sub(hA));
                const nrmH = vec2(dirH.y.negate(), dirH.x);
                const alongH = T.dot(pxz.sub(hA), dirH);
                const perpH = T.dot(pxz.sub(hA), nrmH);
                const lenH = T.length(hB.sub(hA));
                T.If(nn.y.greaterThan(0.6).and(alongH.greaterThan(0.0)).and(alongH.lessThan(lenH)), () => {
                    m.assign(T.max(m, rstep(0.06, 0.045, T.abs(perpH))));
                    m.assign(T.max(m, rstep(0.012, 0.008, T.abs(perpH.sub(0.10)))));
                });

                // (R2) DOOR TAPE — vertical primary + parallel thin.
                T.If(nn.x.greaterThan(0.6), () => {
                    const dzMain = T.abs(pp.z.sub(0.42));
                    T.If(dzMain.lessThan(0.06).and(pp.y.greaterThan(0.30)).and(pp.y.lessThan(0.95)), () => {
                        m.assign(T.max(m, rstep(0.06, 0.045, dzMain)));
                    });
                    const dzThin = T.abs(pp.z.sub(0.28));
                    T.If(dzThin.lessThan(0.012).and(pp.y.greaterThan(0.30)).and(pp.y.lessThan(0.95)), () => {
                        m.assign(T.max(m, rstep(0.012, 0.008, dzThin)));
                    });
                });

                // (R3) ROCKER TAPE — dual horizontal lines along lower side.
                T.If(nn.x.greaterThan(0.6), () => {
                    const dyA = T.abs(pp.y.sub(0.42));
                    T.If(dyA.lessThan(0.012).and(pp.z.greaterThan(-2.00)).and(pp.z.lessThan(2.00)), () => {
                        m.assign(T.max(m, rstep(0.012, 0.008, dyA)));
                    });
                    const dyB = T.abs(pp.y.sub(0.46));
                    T.If(dyB.lessThan(0.006).and(pp.z.greaterThan(-2.00)).and(pp.z.lessThan(2.00)), () => {
                        m.assign(T.max(m, rstep(0.006, 0.004, dyB)));
                    });
                });

                // (R4) REAR QUARTER SPEED COMB — 6 short vertical ticks.
                T.If(nn.x.greaterThan(0.6).and(pp.y.greaterThan(0.55)).and(pp.y.lessThan(0.85)), () => {
                    T.Loop({ start: 0, end: 6, type: 'int' }, ({ i }) => {
                        const zc = float(-1.10).sub(i.toFloat().mul(0.06));
                        const dz = T.abs(pp.z.sub(zc));
                        T.If(dz.lessThan(0.012), () => {
                            m.assign(T.max(m, rstep(0.012, 0.008, dz)));
                        });
                    });
                });

                // (R5) NUMBER BLOCK — solid plate above the comb.
                T.If(nn.x.greaterThan(0.6), () => {
                    const dzB = T.abs(pp.z.add(1.55));
                    const dyB2 = T.abs(pp.y.sub(0.95));
                    T.If(dzB.lessThan(0.10).and(dyB2.lessThan(0.045)), () => {
                        const k = rstep(0.10, 0.085, dzB).mul(rstep(0.045, 0.038, dyB2));
                        m.assign(T.max(m, k));
                    });
                });

                // (R6) TRUNK DIAGONAL — mirror of hood, on trunk top.
                const tA = vec2(0.18, -1.55), tB = vec2(0.62, -2.05);
                const dirT = T.normalize(tB.sub(tA));
                const nrmT = vec2(dirT.y.negate(), dirT.x);
                const alongT = T.dot(pxz.sub(tA), dirT);
                const perpT = T.dot(pxz.sub(tA), nrmT);
                const lenT = T.length(tB.sub(tA));
                T.If(nn.y.greaterThan(0.6).and(alongT.greaterThan(0.0)).and(alongT.lessThan(lenT)), () => {
                    m.assign(T.max(m, rstep(0.05, 0.04, T.abs(perpT))));
                    m.assign(T.max(m, rstep(0.012, 0.008, T.abs(perpT.sub(0.085)))));
                });

                // (R7) ROOF RACING STRIPES — dual fore-aft on right side.
                T.If(nn.y.greaterThan(0.6).and(pp.y.greaterThan(1.35)).and(pp.z.greaterThan(-1.30)).and(pp.z.lessThan(0.40)), () => {
                    const dxA = T.abs(pp.x.sub(0.30));
                    T.If(dxA.lessThan(0.04), () => { m.assign(T.max(m, rstep(0.04, 0.03, dxA))); });
                    const dxB = T.abs(pp.x.sub(0.40));
                    T.If(dxB.lessThan(0.010), () => { m.assign(T.max(m, rstep(0.010, 0.007, dxB))); });
                });
            });

            T.If(pp.x.lessThan(-0.05), () => {
                // (L2) REAR DOOR DIAGONAL — single bold angled band.
                T.If(nn.x.lessThan(-0.6), () => {
                    const dA = vec2(-0.55, 0.85), dB = vec2(-0.10, 0.40);
                    const dirD = T.normalize(dB.sub(dA));
                    const nrmD = vec2(dirD.y.negate(), dirD.x);
                    const pyz = vec2(pp.z, pp.y);
                    const alongD = T.dot(pyz.sub(dA), dirD);
                    const perpD = T.abs(T.dot(pyz.sub(dA), nrmD));
                    const lenD = T.length(dB.sub(dA));
                    T.If(alongD.greaterThan(0.0).and(alongD.lessThan(lenD)).and(perpD.lessThan(0.05)), () => {
                        m.assign(T.max(m, rstep(0.05, 0.04, perpD)));
                    });
                });

                // (L3) FRONT-FENDER VERTICAL COMB — 5 horizontal ticks.
                T.If(nn.x.lessThan(-0.6).and(pp.z.greaterThan(1.50)).and(pp.z.lessThan(1.85)), () => {
                    T.Loop({ start: 0, end: 5, type: 'int' }, ({ i }) => {
                        const yc = float(0.45).add(i.toFloat().mul(0.07));
                        const dy = T.abs(pp.y.sub(yc));
                        T.If(dy.lessThan(0.010), () => {
                            m.assign(T.max(m, rstep(0.010, 0.007, dy)));
                        });
                    });
                });

                // (L4) WEDGE BLOCK — triangle test on rear quarter.
                T.If(nn.x.lessThan(-0.6), () => {
                    const v0 = vec2(-1.30, 0.95), v1 = vec2(-1.70, 0.95), v2 = vec2(-1.50, 0.65);
                    const pp2 = vec2(pp.z, pp.y);
                    const s0 = pp2.x.sub(v0.x).mul(v1.y.sub(v0.y)).sub(pp2.y.sub(v0.y).mul(v1.x.sub(v0.x)));
                    const s1 = pp2.x.sub(v1.x).mul(v2.y.sub(v1.y)).sub(pp2.y.sub(v1.y).mul(v2.x.sub(v1.x)));
                    const s2 = pp2.x.sub(v2.x).mul(v0.y.sub(v2.y)).sub(pp2.y.sub(v2.y).mul(v0.x.sub(v2.x)));
                    const allPos = s0.greaterThanEqual(0.0).and(s1.greaterThanEqual(0.0)).and(s2.greaterThanEqual(0.0));
                    const allNeg = s0.lessThanEqual(0.0).and(s1.lessThanEqual(0.0)).and(s2.lessThanEqual(0.0));
                    T.If(allPos.or(allNeg), () => {
                        m.assign(T.max(m, 1.0));
                    });
                });

                // (L5) TRUNK PARALLELS — 3 thin lines on left trunk top.
                T.If(nn.y.greaterThan(0.6).and(pp.x.lessThan(-0.10)).and(pp.x.greaterThan(-0.70)).and(pp.z.greaterThan(-2.05)).and(pp.z.lessThan(-1.40)), () => {
                    T.Loop({ start: 0, end: 3, type: 'int' }, ({ i }) => {
                        const xc = float(-0.20).sub(i.toFloat().mul(0.16));
                        const dx = T.abs(pp.x.sub(xc));
                        T.If(dx.lessThan(0.008), () => {
                            m.assign(T.max(m, rstep(0.008, 0.005, dx)));
                        });
                    });
                });

                // (L6) ROOF — single thin stripe on left side.
                T.If(nn.y.greaterThan(0.6).and(pp.y.greaterThan(1.35)).and(pp.z.greaterThan(-1.30)).and(pp.z.lessThan(0.40)), () => {
                    const dxL = T.abs(pp.x.add(0.35));
                    T.If(dxL.lessThan(0.012), () => {
                        m.assign(T.max(m, rstep(0.012, 0.008, dxL)));
                    });
                });

                // (L7) ROCKER LINE — single horizontal on lower left.
                T.If(nn.x.lessThan(-0.6), () => {
                    const dyL = T.abs(pp.y.sub(0.42));
                    T.If(dyL.lessThan(0.010).and(pp.z.greaterThan(-2.00)).and(pp.z.lessThan(2.00)), () => {
                        m.assign(T.max(m, rstep(0.010, 0.007, dyL)));
                    });
                });
            });

            T.If(inArch, () => { m.assign(0.0); });

            return m;
        }

        const SUN_DIR = T.normalize(vec3(0.45, 0.78, 0.30));
        // View/ray direction: per the porting rules, never use
        // cameraPosition (WORLD space) directly against a LOCAL-space
        // p — use ctx.ro (LOCAL camera) instead. ctx.rd is already the
        // local-space incoming ray direction, replacing the GLSL's
        // `rd = -V`.
        const V = T.normalize(ctx.ro.sub(p));
        const rd = ctx.rd;
        const H = T.normalize(SUN_DIR.add(V));
        const NdL = T.max(T.dot(n, SUN_DIR), 0.0);
        const NdV = T.max(T.dot(n, V), 0.0);
        const NdH = T.max(T.dot(n, H), 0.0);

        const sh = ctx.softShadow(p.add(n.mul(0.004)), SUN_DIR, 0.01, 12.0, float(24.0));
        const ao = cyberpunkAO(p, n);
        const fres = T.pow(float(1.0).sub(NdV), 5.0);
        // KNOWN GAP (see the "TSL SDF ENGINE" header's KNOWN GAPS note):
        // no sampleEnvMap/sdfReflectWorld equivalent on this backend.
        // envR substitutes a LOCAL-space reflect(rd, n) fed into
        // cyberpunkSky (an approximation of the true world-space HDRI
        // reflection direction sdfReflectWorld computed) — flagged in
        // the porting report as an approximation, not a silent drop.
        const envR = cyberpunkSky(T.reflect(rd, n));
        const sun = vec3(1.15, 1.05, 0.85);
        const sky = cyberpunkSky(vec3(0.0, 1.0, 0.0));
        const col = vec3(0.0, 0.0, 0.0).toVar();

        // NOTE: the GLSL `int matID = int(mat + 0.5)` rounding guard is
        // dropped — every mat value here is produced by opU/select
        // picking between exact MAT.* constants (never blended), so
        // direct float equality against those same constants is safe.
        T.If(mat.equal(MAT.PAINT), () => {
            // Body stays near-black; uPaint shows on the silhouette via
            // fresnel rim. Stripes are off-white racing decals baked on
            // top via stripeMaskFn — non-emissive but self-illuminated
            // so they read on shadowed faces.
            const stripeCol = vec3(0.92, 0.90, 0.85);
            const sm = stripeMaskFn(p, n);
            const base = T.mix(vec3(0.018, 0.018, 0.022), stripeCol, sm);
            const rough = T.mix(T.max(U.uRough, 0.20), 0.55, sm);
            const metallic = T.mix(0.7, 0.0, sm);

            const diffuse = sun.mul(NdL).mul(sh).mul(0.5).add(sky.mul(ao).mul(0.40)).mul(base);
            const a = T.max(rough, 0.06).mul(T.max(rough, 0.06));
            const D = a.div(float(3.14159).mul(T.pow(NdH.mul(NdH).mul(a.sub(1.0)).add(1.0), 2.0)));
            const F = T.mix(vec3(0.04, 0.04, 0.04), vec3(0.5, 0.5, 0.5), metallic);
            const sunSpec = sun.mul(D).mul(F).mul(sh);
            const envCol = envR.mul(F).mul(float(1.0).sub(rough.mul(0.8))).mul(0.7);

            // Accent fresnel rim — uPaint glows on silhouette edges,
            // suppressed where the stripe is painted.
            const rim = T.pow(float(1.0).sub(NdV), 4.0);
            const rimGlow = U.uPaint.mul(rim).mul(0.55).mul(float(1.0).sub(sm));

            col.assign(diffuse.add(envCol).add(sunSpec).add(rimGlow));
            col.assign(col.mul(T.mix(0.55, 1.0, ao)));
            col.assign(col.add(stripeCol.mul(sm).mul(0.45)));
        }).ElseIf(mat.equal(MAT.GLASS), () => {
            const tint = vec3(0.01, 0.012, 0.018);
            col.assign(tint.add(envR.mul(fres.mul(0.9).add(0.08))));
            col.assign(col.add(sky.mul(0.02)));
            col.assign(col.add(sun.mul(T.pow(NdH, 80.0)).mul(sh).mul(0.6)));
        }).ElseIf(mat.equal(MAT.TIRE), () => {
            const base = vec3(0.025, 0.025, 0.028);
            col.assign(sun.mul(NdL).mul(sh).add(sky.mul(ao)).add(0.04).mul(base));
            col.assign(col.add(envR.mul(0.03).mul(fres)));
        }).ElseIf(mat.equal(MAT.RIM), () => {
            // Dead code in the GLSL original too — sdCar() never
            // assigns MAT_RIM in this example (it did in the modern
            // sedan this shade() was adapted from). Ported faithfully
            // rather than dropped in case a future map() variant emits
            // it.
            const base = vec3(0.55, 0.55, 0.58);
            col.assign(sun.mul(NdL).mul(sh).mul(0.5).add(sky.mul(ao)).mul(base));
            col.assign(col.add(envR.mul(fres.mul(0.7).add(0.25)).mul(0.9)));
            col.assign(col.add(sun.mul(T.pow(NdH, 40.0)).mul(sh)));
        }).ElseIf(mat.equal(MAT.CHROME), () => {
            // PBR-style chrome — metalness=1.0, roughness=0.0 (pure
            // mirror finish). Both are JS-time constants in the GLSL
            // original (`const float`), so specExp folds to a literal
            // 4096.0 here rather than a per-fragment mix() node — same
            // numeric result, computed once instead of every pixel.
            const metalness = 1.0;
            const roughness = 0.0;
            const specExp = 64.0 + (4096.0 - 64.0) * (1.0 - roughness); // = 4096
            col.assign(envR.mul(metalness));
            col.assign(col.add(sun.mul(T.pow(NdH, specExp)).mul(sh).mul(16.0)));
        }).ElseIf(mat.equal(MAT.HEAD), () => {
            const emit = vec3(1.6, 1.55, 1.35);
            const core = T.pow(float(1.0).sub(fres), 3.0);
            col.assign(emit.mul(float(0.55).add(core.mul(1.4))));
            col.assign(col.add(envR.mul(fres).mul(0.5)));
            col.assign(col.add(sun.mul(T.pow(NdH, 200.0)).mul(sh).mul(1.2)));
        }).ElseIf(mat.equal(MAT.TAIL), () => {
            const redEmit = vec3(1.9, 0.10, 0.05);
            const core = T.mix(0.7, 1.2, T.pow(float(1.0).sub(fres), 2.0));
            col.assign(redEmit.mul(core));
            col.assign(col.add(envR.mul(fres).mul(0.25)));
            col.assign(col.add(vec3(1.0, 0.4, 0.3).mul(T.pow(NdH, 80.0)).mul(sh).mul(0.4)));
        }).ElseIf(mat.equal(MAT.UNDERGLOW), () => {
            col.assign(U.uPaint.mul(2.2));
            col.assign(col.add(U.uPaint.mul(T.pow(float(1.0).sub(fres), 2.0)).mul(0.6)));
        }).ElseIf(mat.equal(MAT.ACCENT), () => {
            col.assign(U.uPaint.mul(1.5));
            col.assign(col.add(U.uPaint.mul(T.pow(float(1.0).sub(fres), 2.0)).mul(0.4)));
        }).ElseIf(mat.equal(MAT.GRILLE), () => {
            // Procedural hex tiling on the grille plate face. Two
            // candidate hex-cell centres per fragment (offset rows);
            // distance to nearest gives wallEdge. Cells glow uPaint;
            // edges read as a dark mesh. (Normal-order smoothstep here
            // — 0.55 < 0.78 — so no rstep() rewrite needed.)
            const gp = vec2(p.x, p.y.sub(0.55)).mul(22.0);
            const s = vec2(1.0, 1.7320508);
            const hC = T.floor(gp.div(s)).add(0.5).mul(s);
            const hC2 = T.floor(gp.sub(s.mul(0.5)).div(s)).add(0.5).mul(s).add(s.mul(0.5));
            const hexD = T.min(T.length(gp.sub(hC)), T.length(gp.sub(hC2)));
            const wallEdge = T.smoothstep(0.55, 0.78, hexD);
            const dark = vec3(0.005, 0.005, 0.005);
            const glow = U.uPaint.mul(0.85);
            col.assign(T.mix(glow, dark, wallEdge));
            col.assign(col.mul(NdL.mul(sh).mul(0.4).add(0.6)));
            col.assign(col.add(envR.mul(fres).mul(0.15)));
        }).ElseIf(mat.equal(MAT.BADGE), () => {
            // UV unwrap from the local surface position. The plate
            // bounds (model space) are pm.x ~ 0.834, y in [1.105,
            // 1.195], z in [-1.11,-0.79]. v maps the y-extent; u walks
            // the z-extent (reversed on the right side so the text
            // reads left-to-right from outside on both sides).
            const v = p.y.sub(1.105).div(0.09);
            const uRight = float(-0.79).sub(p.z).div(0.32);
            const uLeft = p.z.add(1.11).div(0.32);
            const u = T.select(p.x.greaterThan(0.0), uRight, uLeft);
            const txt = THREE.textureLevel(S._decalTex, vec2(u, v), 0);
            const plateBase = vec3(0.012, 0.012, 0.015);
            let plateLit = sun.mul(NdL).mul(sh).mul(0.5).add(sky.mul(ao)).mul(plateBase);
            plateLit = plateLit.add(envR.mul(fres).mul(0.08));
            plateLit = plateLit.add(sun.mul(T.pow(NdH, 16.0)).mul(sh).mul(0.15));
            const glyphCol = vec3(1.4, 1.4, 1.4);
            // Limit the decal to outward-facing sides of the plate so
            // it doesn't bleed onto edges or the rear face.
            const faceMask = T.step(0.7, T.abs(n.x));
            let ink = txt.a.mul(faceMask);
            const outOfRange = u.lessThan(0.0).or(u.greaterThan(1.0)).or(v.lessThan(0.0)).or(v.greaterThan(1.0));
            ink = T.select(outOfRange, float(0.0), ink);
            col.assign(T.mix(plateLit, glyphCol, ink));
        }).Else(() => {
            // MAT_PLASTIC — matte black grille intake / lower bumper.
            const base = vec3(0.012, 0.012, 0.015);
            col.assign(sun.mul(NdL).mul(sh).mul(0.5).add(sky.mul(ao)).mul(base).add(envR.mul(fres).mul(0.08)));
            col.assign(col.add(sun.mul(T.pow(NdH, 16.0)).mul(sh).mul(0.15)));
        });

        return col;
    },

    /**
     * Direct-call factory. Returns a configured SDF mesh ready to be
     * positioned / scaled / rotated.
     *
     * Options:
     *   paintColor:     hex (0x00e7ff) / THREE.Color / [r,g,b] (0..1).
     *                   Drives fresnel rim, underglow, accent strips,
     *                   and hex grille glow. NOT the body base colour
     *                   (that stays near-black for the cyberpunk look).
     *                   Default 0x00e7ff (electric cyan).
     *   paintRoughness: 0..1. 0 = mirror, 1 = matte. Default 0.18
     *                   (floored at 0.20 inside shade()).
     *   decalText:      string drawn onto the rear-quarter badge plate
     *                   via CanvasTexture. Default 'ALETH8APO'. Reading
     *                   _buildBadgeDecal teaches the canvas -> texture
     *                   pattern for procedural decals on SDF surfaces.
     *                   Glyphs not in _BADGE_GLYPH_ATLAS are skipped.
     *
     * NOTE: paintColor/paintRoughness/decalText mutate the LIVE, SHARED
     * `_u`/`_decalTex` on this spec object (see the comment above `_u`)
     * — simultaneous multi-instance liveries are not independent.
     */
    make(opts) {
        opts = opts || {};
        const spec = EXAMPLES.stylizedCyberpunkSedan;
        if (opts.paintColor !== undefined) {
            spec._u.uPaint.value = new THREE.Color(opts.paintColor);
        }
        if (opts.paintRoughness !== undefined) {
            spec._u.uRough.value = opts.paintRoughness;
        }
        if (opts.decalText !== undefined) {
            spec._decalTex = _buildBadgeDecal(opts.decalText);
        }
        const sdf = createSdfObject({ ...spec });
        sdf.userData.sdfLiveUniforms = spec._u;
        return sdf;
    },
};

// =====================================================================
// Stylized Sci-Fi Sleek Car — a streamlined sci-fi compact built from
// CYLINDER SECTIONS rather than rounded boxes. The body's smooth
// roof-to-side arc comes from a single cylinder whose axis sits
// above the car (length(p.yz) where p is shifted up); the visible
// part is the lower half of that cylinder.
//
// The body is METAL — uMetalColor is treated as F0 (specular tint)
// rather than as a diffuse paint colour. Pass silver / gold / copper
// / anodized blue / etc. and the entire body picks up that metallic
// character: silver mirror, brushed gold, polished copper, etc.
// uRough controls the brushed-vs-mirror finish.
//
// Bounds (TIGHT, with internal scale S=1.5):
//   x ±1.10  (fender bulges at pre-scale x ≈ 0.72 → 1.08 world)
//   y -0.63..1.10  (tire bottom at pre-scale -0.42 → -0.63 world)
//   z ±2.10  (length 4.2m, slightly shorter than the sedans)
// =====================================================================
EXAMPLES.stylizedSciFiSleekCar = {
    // =================================================================
    // Stylized Sci-Fi Sleek Car — a streamlined sci-fi compact built
    // from CYLINDER SECTIONS rather than rounded boxes. The body's
    // smooth roof-to-side arc comes from a single cylinder whose axis
    // sits above the car (length(p.yz) where p is shifted up); the
    // visible part is the lower half of that cylinder.
    //
    // The body is METAL — uMetalColor is treated as F0 (specular tint)
    // rather than as a diffuse paint colour. Pass silver / gold / copper
    // / anodized blue / etc. and the entire body picks up that metallic
    // character: silver mirror, brushed gold, polished copper, etc.
    // uRough controls the brushed-vs-mirror finish.
    //
    // Bounds (TIGHT, with internal scale S=1.5):
    //   x ±1.10  (fender bulges at pre-scale x ≈ 0.72 → 1.08 world)
    //   y -0.63..1.10  (tire bottom at pre-scale -0.42 → -0.63 world)
    //   z ±2.10  (length 4.2m, slightly shorter than the sedans)
    //
    // TSL — ported 2026-07-04 from the GLSL original (`const T =
    // SDF_TSL;` / `{ dist, mat }` map contract, same style as
    // EXAMPLES.basicSphere / stylizedBlob / detailedCoat / fractalCore
    // — see the "TSL SDF ENGINE" header comment near the top of this
    // file). Since this whole object has to remain a single
    // `EXAMPLES.stylizedSciFiSleekCar = { ... };` literal (no top-level
    // helper consts allowed), the shared sub-routines the GLSL `extra`
    // block used (mapBody/mapTire/sdCar, the 4-wheel fold, the env-map
    // helpers) are ported as extra `_`-prefixed methods on this same
    // object — same convention the "add a `_u` property" conversion
    // rule uses for uniforms, just extended to the rest of the shared
    // code. map()/shade() (the only two entry points the engine calls
    // bare, without a receiver) reach them via the fully-qualified
    // `EXAMPLES.stylizedSciFiSleekCar._foo(...)` path; every other
    // helper method reaches its siblings the same way for safety
    // (calling a method off the literal's own `this` only works if the
    // caller itself was invoked with a receiver, which map/shade are
    // NOT).
    //
    // KNOWN-GAP APPROXIMATION (flagged, not silently dropped): the GLSL
    // original's `shade()` samples the scene's equirectangular HDRI via
    // `sampleEnvMap(sdfReflectWorld(p, n))` for every metal/glass/
    // chrome/light reflection term. That HDRI texture plumbing
    // (uEnvMap/uEnvMapStrength) is an explicit, documented gap on the
    // current TSL path — see this file's "TSL SDF ENGINE" header
    // comment: "no uEnvMap/HDRI reflection plumbing yet (sampleEnvMap/
    // sdfReflectWorld have no TSL equivalent here)". The coordinate-
    // transform half of that helper (`sdfReflectWorld` — local hit
    // point/normal -> world-space reflection vector, no texture
    // involved) IS ported faithfully below as `_reflectWorld`. Only the
    // texture lookup itself is substituted, with a small procedural
    // sky/ground gradient + soft sun-glow term (`_envApprox`) standing
    // in for the missing `sampleEnvMap`. Every material branch that
    // read `envR`/`sky` reads this approximation instead — the car will
    // look flatter / less "photographed" than the GLSL+HDRI path until
    // real uEnvMap sampling is wired into TSL; no geometry, materials,
    // or shading branches were dropped to get there.
    // =================================================================
    bounds: { min: [-1.10, -0.63, -2.10], max: [1.10, 1.10, 2.10] },
    quality: 'high',

    // Body paint colour and roughness exposed as live TSL uniform()
    // nodes — call EXAMPLES.stylizedSciFiSleekCar.make({ metalColor,
    // paintRoughness }) for the common case, or reach `_u` directly for
    // full control.
    //
    // Default = silver. F0 in linear space — pass any THREE.Color and
    // the shader treats it as the metal's specular tint. Notable F0
    // values:
    //   Silver:   0xf3eee0 (slightly warm white)
    //   Gold:     0xffb44a (warm yellow-orange)
    //   Copper:   0xf2a387 (pinkish brown)
    //   Aluminum: 0xe7e7e7 (cool gray)
    //   Anodized blue:   0x4d80e6
    //   Anodized purple: 0x8b4dcc
    //
    // uRough: 0 = mirror, 1 = matte. 0.15 keeps the body fractionally
    // rougher than the (mirror-finish) glass so the cabin glazing reads
    // as a separate, glossier material.
    _u: {
        uMetalColor: SDF_TSL.uniform(new THREE.Color(0.95, 0.93, 0.88)),
        uRough: SDF_TSL.uniform(0.15),
    },

    // Material IDs (GLSL `#define MAT_*` block). No id 3.0 — preserved
    // as-is from the original.
    _mat: { PAINT: 0.0, GLASS: 1.0, TIRE: 2.0, CHROME: 4.0, HEAD: 5.0, TAIL: 6.0 },

    // GLSL `pf.xz = abs(pf.xz) - vec2(0.42, 0.95); pf.x = abs(pf.x);` —
    // the fold that turns one wheel's SDF math into all 4 via mirroring.
    // TSL has no swizzle-assignment, so this rebuilds a fresh vec3 from
    // its parts: x is abs'd TWICE (once inside the xz fold, once again
    // after), z only once — same order as the GLSL statements. Shared by
    // mapBody (fender bulge + arch cut), mapTire, sdCar's hubcap disc,
    // and shade()'s chrome hex-tiling branch.
    _foldWheel(p) {
        const T = SDF_TSL;
        const fx = T.abs(p.x).sub(0.42);
        const fz = T.abs(p.z).sub(0.95);
        return T.vec3(T.abs(fx), p.y, fz);
    },

    // Main body — built using the cylinder-section technique.
    // length(p.yz) measures distance from the X-axis in the YZ plane.
    // Constraining it below a threshold gives a cylinder along X;
    // clipping the upper half gives the curved roof sweeping in one
    // continuous arc to each side.
    _mapBody(p0) {
        const T = SDF_TSL;
        const EX = EXAMPLES.stylizedSciFiSleekCar;
        const vec3 = T.vec3;

        // Main body shell — cylinder centered ABOVE the car so the
        // visible (lower) half forms the roof arching down to the sides.
        const p = p0.add(vec3(0.0, 1.05, 0.0));
        const r = T.length(p.yz);
        let d = T.length(T.max(vec3(T.abs(p.x).sub(0.32), r.sub(1.78), p.y.negate().add(1.30)), 0.0)).sub(0.06);
        d = T.max(d, T.abs(p.z).sub(1.10));

        // Nose tuck — second cylinder section pulled forward and down;
        // smin'd into the body for a sloped nose.
        const pn = p0.add(vec3(0.0, 0.55, -0.40));
        const rn = T.length(pn.yz);
        let dn = T.length(T.max(vec3(T.abs(pn.x).sub(0.30), rn.sub(0.95), pn.y.negate().add(0.70)), 0.0)).sub(0.05);
        dn = T.max(dn, T.abs(pn.z).sub(0.55));
        d = T.smin(d, dn, T.float(0.10));

        // Fender bulges (4 wheels via the shared fold helper).
        const pf = EX._foldWheel(p0.add(vec3(0.0, -0.20, 0.0)));
        const rf = T.length(pf.yz);
        const df = T.length(T.max(vec3(pf.x.sub(0.06), rf.sub(0.30), pf.y.negate().sub(0.06)), 0.0)).sub(0.04);
        d = T.smin(d, df, T.float(0.06));

        // Belt-line indent (thin horizontal subtraction at mid-side).
        const pb = p0;
        const belt = T.max(
            T.abs(pb.y.sub(0.30)).sub(0.012),
            T.max(T.float(0.32).sub(T.abs(pb.x)), T.abs(pb.z).sub(1.00)),
        );
        d = T.max(d, belt.negate().add(0.005));

        // Wheel arch carve (cylinder subtraction at each wheel).
        const archCut = T.max(pf.x.sub(0.18), T.length(pf.yz).sub(0.26));
        d = T.max(d, archCut.negate());

        return d;
    },

    // Capped torus tire — 4 wheels via the same fender folding.
    _mapTire(p0) {
        const T = SDF_TSL;
        const EX = EXAMPLES.stylizedSciFiSleekCar;
        const pf = EX._foldWheel(p0.add(T.vec3(0.0, -0.20, 0.0)));
        return T.length(T.vec2(T.max(pf.x.sub(0.13), 0.0), T.length(pf.yz).sub(0.20))).sub(0.045);
    },

    // Body + glass + lights + hubcaps. Internally authored at pre-scale;
    // final SDF distance multiplied by S to give world-space distances
    // the marcher can step through. Returns { dist, mat } (the TSL
    // equivalent of the GLSL vec2(dist, matId) pairs) so opU can pick
    // the closer surface + carry its material id along in one call.
    _sdCar(p) {
        const T = SDF_TSL;
        const EX = EXAMPLES.stylizedSciFiSleekCar;
        const { vec3, vec2, float } = T;
        const MAT = EX._mat;

        const S = 1.5;
        const pl = p.div(S);
        const plm = vec3(T.abs(pl.x), pl.y, pl.z);

        const body = EX._mapBody(pl);
        let res = { dist: body.mul(S), mat: float(MAT.PAINT) };

        const tire = EX._mapTire(pl);
        res = T.opU(res, { dist: tire.mul(S), mat: float(MAT.TIRE) });

        // Glass patches — thin shell straddling the body surface, gated
        // to specific regions for windshield / rear / sides.
        const bodyShell = T.abs(body).sub(0.012);

        // Windshield: front-upper roof.
        const wsRegion = T.max(
            T.max(pl.z.sub(0.10), float(-0.65).sub(pl.z)),
            T.max(float(0.42).sub(pl.y), plm.x.sub(0.30)),
        );
        const windshield = T.max(bodyShell, wsRegion);

        // Rear glass: rear-upper roof.
        const rwRegion = T.max(
            T.max(pl.z.sub(0.90), float(0.30).sub(pl.z)),
            T.max(float(0.42).sub(pl.y), plm.x.sub(0.30)),
        );
        const rearGlass = T.max(bodyShell, rwRegion);

        // Side window: half-ellipse profile, flat-bottom at the
        // beltline, single curve sweeping front-to-rear.
        const yzP = vec2(pl.y, pl.z);
        const yzC = vec2(0.45, -0.05);
        const dYz = yzP.sub(yzC).div(vec2(0.30, 0.60));
        const ellipse = T.length(dYz).sub(1.0);
        const halfEllipse = T.max(ellipse, float(0.45).sub(pl.y));
        const swRegion = T.max(halfEllipse, T.max(float(0.32).sub(plm.x), plm.x.sub(0.45)));
        const sideWin = T.max(bodyShell, swRegion);

        const glass = T.min(T.min(windshield, rearGlass), sideWin);
        res = T.opU(res, { dist: glass.mul(S), mat: float(MAT.GLASS) });

        // Headlights & taillights — 2 each, hand-tuned positions.
        const hlR = T.sdSphere(pl.sub(vec3(0.146, 0.311, 1.080)), float(0.06));
        const hlL = T.sdSphere(pl.sub(vec3(-0.154, 0.310, 1.072)), float(0.06));
        res = T.opU(res, { dist: T.min(hlR, hlL).mul(S), mat: float(MAT.HEAD) });

        const tlR = T.sdSphere(pl.sub(vec3(0.151, 0.286, -1.077)), float(0.06));
        const tlL = T.sdSphere(pl.sub(vec3(-0.152, 0.281, -1.079)), float(0.06));
        res = T.opU(res, { dist: T.min(tlR, tlL).mul(S), mat: float(MAT.TAIL) });

        // Chrome hubcap discs filling the wheel wells.
        const wp = EX._foldWheel(pl.add(vec3(0.0, -0.20, 0.0)));
        const wr = T.length(wp.yz);
        const hubcap = T.max(wr.sub(0.16), T.max(wp.x.sub(0.16), float(0.10).sub(wp.x)));
        res = T.opU(res, { dist: hubcap.mul(S), mat: float(MAT.CHROME) });

        return res;
    },

    // KNOWN-GAP APPROXIMATION stand-in for the missing uEnvMap sampler
    // (see the header comment above `EXAMPLES.stylizedSciFiSleekCar`) —
    // a simple ground/horizon/zenith gradient plus a soft glow around
    // the sun direction, so metal/glass/chrome still pick up a
    // directional highlight and a plausible ambient tint instead of
    // reading as flat, unlit color. `dir` is a WORLD-space direction
    // (the output of `_reflectWorld`, or world-up for the ambient term).
    _envApprox(dir) {
        const T = SDF_TSL;
        const { vec3, float } = T;
        const d = T.normalize(dir);
        const skyT = T.clamp(d.y.mul(0.5).add(0.5), 0.0, 1.0);
        const ground = vec3(0.16, 0.14, 0.12);
        const horizon = vec3(0.62, 0.60, 0.56);
        const zenith = vec3(0.30, 0.40, 0.62);
        let col = T.mix(ground, horizon, T.smoothstep(0.0, 0.20, skyT));
        col = T.mix(col, zenith, T.smoothstep(0.20, 1.0, skyT));
        const sunDir = T.normalize(vec3(0.45, 0.78, 0.30));
        const sunAmt = T.pow(T.max(float(0.0), T.dot(d, sunDir)), 8.0);
        return col.add(vec3(1.2, 1.05, 0.85).mul(sunAmt).mul(0.6));
    },

    // Faithful port of the GLSL `sdfReflectWorld` helper (see this
    // file's "Equirectangular HDRI sampler" section) — only the
    // local->world transform + reflect(), no texture sampling involved,
    // so unlike sampleEnvMap this half has an exact TSL equivalent.
    // modelWorldMatrix / cameraPosition are the same WORLD-space TSL
    // builtins the engine itself uses for the view-normal debug pass
    // (see _buildSdfNodeMaterial's passType.equal(1) branch).
    _reflectWorld(pLocal, nLocal) {
        const T = SDF_TSL;
        const pWorld = T.modelWorldMatrix.mul(T.vec4(pLocal, 1.0)).xyz;
        const nWorld = T.normalize(T.modelWorldMatrix.mul(T.vec4(nLocal, 0.0)).xyz);
        const viewWorld = T.normalize(T.cameraPosition.sub(pWorld));
        return T.reflect(viewWorld.negate(), nWorld);
    },

    map(p) {
        return EXAMPLES.stylizedSciFiSleekCar._sdCar(p);
    },

    shade(p, n, mat, ctx) {
        const T = SDF_TSL;
        const EX = EXAMPLES.stylizedSciFiSleekCar;
        const { vec3, float } = T;
        const MAT = EX._mat;

        // int matID = int(mat + 0.5); — defensive round-to-nearest
        // before the equality branches below (mat only ever takes exact
        // small integer values via opU's select(), so this is
        // belt-and-braces, same as the GLSL original).
        const matID = T.floor(mat.add(0.5));

        const SUN_DIR = T.normalize(vec3(0.45, 0.78, 0.30));
        // View dir for the specular/fresnel dot products below stays in
        // LOCAL space (matches n and p) — ctx.ro is the LOCAL-space
        // camera; T.cameraPosition is WORLD space and must not be mixed
        // with local p/n here (see the "AGENT API" header note + the
        // CONVERSION RULES this port follows).
        const V = T.normalize(ctx.ro.sub(p));
        const H = T.normalize(SUN_DIR.add(V));
        const NdL = T.max(T.dot(n, SUN_DIR), 0.0);
        const NdV = T.max(T.dot(n, V), 0.0);
        const NdH = T.max(T.dot(n, H), 0.0);

        const sh = ctx.softShadow(p.add(n.mul(0.004)), SUN_DIR, 0.01, 12.0, float(24.0));
        const fres = T.pow(float(1.0).sub(NdV), 5.0);

        // ---- KNOWN-GAP APPROXIMATION (see header comment) ----
        // GLSL original: envR = sampleEnvMap(sdfReflectWorld(p, n));
        //                sky  = sampleEnvMap(vec3(0, 1, 0));
        // TSL: sdfReflectWorld ported faithfully as _reflectWorld;
        // sampleEnvMap's texture lookup substituted with the procedural
        // _envApprox gradient (no uEnvMap plumbing on this path yet).
        const envR = EX._envApprox(EX._reflectWorld(p, n));
        const sun = vec3(1.15, 1.05, 0.85);
        const sky = EX._envApprox(vec3(0.0, 1.0, 0.0));

        const col = vec3(0.5, 0.5, 0.5).toVar();

        // Pure metal body. uMetalColor IS F0 — the metal's characteristic
        // specular tint (gold = warm yellow, copper = pinkish brown,
        // silver = neutral white, anodized = saturated tints). Schlick
        // fresnel pushes it toward white at glancing angles. No diffuse.
        T.If(matID.equal(MAT.PAINT), () => {
            const F0 = EX._u.uMetalColor;
            const F = F0.add(vec3(1.0, 1.0, 1.0).sub(F0).mul(fres));
            const rough = T.max(EX._u.uRough, 0.06);

            const a = rough.mul(rough);
            const D = a.div(float(3.14159).mul(T.pow(NdH.mul(NdH).mul(a.sub(1.0)).add(1.0), 2.0)));
            const sunSpec = sun.mul(D).mul(F).mul(sh);

            // Full env reflection scaled by roughness; F0 tints the
            // whole env so the entire body reads as that metal.
            const envCol = envR.mul(F).mul(float(1.0).sub(rough.mul(0.4)));

            col.assign(envCol.add(sunSpec.mul(1.5)));
            // Tiny F0-tinted ambient bounce so deeply-shadowed metal
            // doesn't go pitch black on dim HDRIs.
            col.addAssign(F0.mul(sky).mul(0.05));
        });

        T.If(matID.equal(MAT.GLASS), () => {
            const tint = vec3(0.01, 0.012, 0.018);
            col.assign(tint.add(envR.mul(fres.mul(0.9).add(0.08))));
            col.addAssign(sun.mul(T.pow(NdH, 80.0)).mul(sh).mul(0.6));
        });

        T.If(matID.equal(MAT.TIRE), () => {
            const base = vec3(0.025, 0.025, 0.028);
            col.assign(base.mul(NdL.mul(sh).mul(sun).add(sky.mul(0.3)).add(0.04)));
            col.addAssign(envR.mul(0.03).mul(fres));
        });

        T.If(matID.equal(MAT.CHROME), () => {
            // Hex-tiled chrome hubcap. Re-fold to the wheel-local frame
            // (shared EX._foldWheel helper) so the hex grid stays
            // centred on the hub for all 4 wheels.
            const wp = EX._foldWheel(p.div(1.5).add(vec3(0.0, -0.20, 0.0)));

            // Standard 60-degree hex tiling on the disc plane (yz,
            // perpendicular to the wheel axle): two offset rectangular
            // lattices, pick the closer centre per fragment (GLSL
            // ternary -> T.select, per the CONVERSION RULES).
            const uv = wp.yz.mul(12.0);
            const r = T.vec2(1.0, 1.7320508);
            const hs = r.mul(0.5);
            const a = T.mod(uv, r).sub(hs);
            const b = T.mod(uv.sub(hs), r).sub(hs);
            const gv = T.select(T.dot(a, a).lessThan(T.dot(b, b)), a, b);
            const hexD = T.max(T.abs(gv.x).mul(0.866).add(T.abs(gv.y).mul(0.5)), T.abs(gv.y));
            // 0 deep inside cell, 1 on the cell border.
            const hexEdge = T.smoothstep(0.40, 0.47, hexD);

            // Cell interior = mirror silver; cell border gets darkened
            // F0 + extra roughness so the hex lattice reads against the
            // reflection.
            const chromeF0 = vec3(0.95, 0.93, 0.88);
            const F0 = T.mix(chromeF0, chromeF0.mul(0.35), hexEdge);
            const F = F0.add(vec3(1.0, 1.0, 1.0).sub(F0).mul(fres));
            const roughC = T.mix(0.02, 0.20, hexEdge);

            col.assign(envR.mul(F).mul(float(1.0).sub(roughC.mul(0.5))));
            col.addAssign(sun.mul(T.pow(NdH, T.mix(1500.0, 80.0, hexEdge))).mul(sh).mul(T.mix(16.0, 4.0, hexEdge)));
        });

        T.If(matID.equal(MAT.HEAD), () => {
            const emit = vec3(3.6, 3.5, 3.0);
            const core = T.pow(float(1.0).sub(fres), 3.0);
            col.assign(emit.mul(float(0.85).add(core.mul(1.6))));
            col.addAssign(envR.mul(fres).mul(0.3));
            col.addAssign(sun.mul(T.pow(NdH, 200.0)).mul(sh).mul(1.0));
        });

        T.If(matID.equal(MAT.TAIL), () => {
            const redEmit = vec3(4.5, 0.18, 0.08);
            const core = T.mix(0.95, 1.5, T.pow(float(1.0).sub(fres), 2.0));
            col.assign(redEmit.mul(core));
            col.addAssign(envR.mul(fres).mul(0.18));
        });

        return col;
    },

    /**
     * Direct-call factory.
     *
     * Options:
     *   metalColor:     hex / THREE.Color / [r,g,b]. Treated as the
     *                   metal's F0 (specular tint). Pass realistic
     *                   metals — silver 0xf3eee0, gold 0xffb44a,
     *                   copper 0xf2a387, aluminum 0xe7e7e7 — or
     *                   saturated anodized colours like 0x4d80e6
     *                   (anodized blue) or 0x8b4dcc (anodized
     *                   purple). Default: silver.
     *   paintRoughness: 0..1. 0.0 = perfect mirror (show-car polish),
     *                   ~0.10 = polished (default), ~0.35 = brushed,
     *                   ~0.6+ = matte/etched.
     */
    make(opts) {
        opts = opts || {};
        const EX = EXAMPLES.stylizedSciFiSleekCar;
        if (opts.metalColor !== undefined) {
            EX._u.uMetalColor.value = new THREE.Color(opts.metalColor);
        }
        if (opts.paintRoughness !== undefined) {
            EX._u.uRough.value = opts.paintRoughness;
        }
        const sdf = createSdfObject(EX);
        // Live-uniform bag so external code (Settings UI, timeline
        // keyframes, etc.) can find + drive these TSL uniform() nodes by
        // name after creation — same spirit as the legacy GLSL path's
        // mesh.userData.sdfUniforms bag, but for real TSL uniform()
        // nodes (mutate `.value` directly, no shader recompile needed).
        sdf.userData.sdfLiveUniforms = EX._u;
        return sdf;
    },
};

EXAMPLES.stylizedFighterJet = {
    // TSL — ported 2026-07-04 from the GLSL original (bilateral-symmetry
    // hull/wing/tail/engine-pod solid built from smooth-unioned
    // ellipsoids/boxes/Z-axis capped cylinders, CSG-cut engine bores, a
    // bubble canopy, an emissive plume, wing-pylon AAMs, and a centerline
    // bomb). uCamoMode is now a live TSL uniform node
    // (EXAMPLES.stylizedFighterJet._u.uCamoMode) instead of the old GLSL
    // `uniforms: { uCamoMode: {...} } }` spec — see `_u` below and make().
    //
    // FLAGGED APPROXIMATION: the GLSL original's sampleEnvMap()/
    // sdfReflectWorld() (HDRI reflection sampling) have no TSL equivalent
    // in this engine yet (see the "TSL SDF ENGINE" header's KNOWN GAPS
    // note near the top of sdf_raymarch_loader.js) — approxEnvMap() below
    // substitutes a simple analytic sky-over-ground gradient keyed on
    // direction.y for both the sky-fill term and the fresnel-driven
    // "envR" reflection term. This preserves the shading ROLE (cool sky
    // fill + a brighter reflected highlight at grazing angles) but will
    // not pick up an actual HDRI/environment texture the way the GLSL
    // path did.
    bounds: { min: [-3.0, -0.9, -4.1], max: [3.0, 1.15, 3.4] },
    quality: 'high',

    // Live uniform — 0 = silver, 1 = sky, 2 = desert, 3 = forest. Set via
    // make({ camo: ... }) at creation time, or mutate
    // sdf.userData.sdfLiveUniforms.uCamoMode.value directly afterward.
    // NOTE: this node is shared module-wide across every instance made
    // from this spec (it lives on the EXAMPLES object, not per-mesh) —
    // if two stylizedFighterJet SDFs are alive at once, changing one's
    // camo changes both. Fine for the common single-hero-jet case; a
    // multi-jet scene wanting independent camo per instance would need
    // its own uniform per mesh (out of scope for this port).
    _u: {
        uCamoMode: SDF_TSL.uniform(1.0),
    },

    map(p) {
        const T = SDF_TSL;
        const { vec3, vec2, float } = T;
        const MAT_HULL = 0.0, MAT_GLASS = 1.0, MAT_WEAPON = 2.0, MAT_PLUME = 3.0;

        // Z-axis capped cylinder — the loader's own primitives don't
        // ship one (sdCapsule/sdCap2 are round-capped along an arbitrary
        // a→b axis, not flat-capped along Z), and the engine pods /
        // missiles / bomb all need a flat-capped cylinder. Ported
        // straight from the GLSL local helper `_jetCylZ`.
        const jetCylZ = (pp, h) => {
            const d = T.abs(vec2(T.length(pp.xy), pp.z)).sub(h);
            return T.min(T.max(d.x, d.y), 0.0).add(T.length(T.max(d, 0.0)));
        };

        // Bilateral symmetry around the X=0 plane.
        const pSym = T.opMirrorX(p);

        // ---- Hull / wings / tail / engine pods (single solid) ----
        let hull = T.sdEllipsoid(p.sub(vec3(0.0, 0.0, -0.5)), vec3(0.45, 0.35, 3.0));
        hull = T.smin(hull,
            T.sdEllipsoid(p.sub(vec3(0.0, -0.05, 1.8)), vec3(0.20, 0.15, 1.5)),
            float(0.6));

        // Main wings — domain shear gives them a swept silhouette.
        let pWing = pSym.sub(vec3(0.4, 0.0, -0.5));
        pWing = vec3(pWing.x, pWing.y, pWing.z.sub(pWing.x.mul(0.8)));
        const wings = T.sdBox(pWing, vec3(2.5, 0.025, 0.9));
        hull = T.smin(hull, wings, float(0.2));

        // Horizontal stabilizers + canted vertical fins (F-18 style).
        let pTail = pSym.sub(vec3(0.4, 0.0, -2.5));
        pTail = vec3(pTail.x, pTail.y, pTail.z.sub(pTail.x.mul(0.6)));
        const rearWing = T.sdBox(pTail, vec3(1.2, 0.02, 0.5));
        hull = T.smin(hull, rearWing, float(0.15));

        let pFin = pSym.sub(vec3(0.3, 0.4, -2.4));
        // pFin.xy *= mat2(cos(0.2), sin(0.2), -sin(0.2), cos(0.2)) — the
        // angle is a compile-time constant, so cos/sin are plain JS
        // numbers rather than a T.cos/T.sin node pair (see the "mat2
        // rotation idioms" conversion rule).
        const cFin = Math.cos(0.2), sFin = Math.sin(0.2);
        pFin = vec3(pFin.x.mul(cFin).sub(pFin.y.mul(sFin)), pFin.x.mul(sFin).add(pFin.y.mul(cFin)), pFin.z);
        pFin = vec3(pFin.x, pFin.y, pFin.z.sub(pFin.y.mul(0.8)));
        const fin = T.sdBox(pFin, vec3(0.02, 0.6, 0.5));
        hull = T.smin(hull, fin, float(0.2));

        // Engine pods — outer shell, then inner-bore subtraction so the
        // intake/exhaust holes punch cleanly through everything already
        // smin'd above.
        const pEng = pSym.sub(vec3(0.65, -0.05, -1.5));
        const engOuter = jetCylZ(pEng, vec2(0.35, 1.2));
        const engInner = jetCylZ(pEng, vec2(0.28, 1.3));
        hull = T.smin(hull, engOuter, float(0.2));
        hull = T.max(hull, engInner.negate());

        // Turbine face + exhaust struts (visible inside the bore).
        const turbineFace = jetCylZ(pEng.sub(vec3(0.0, 0.0, 0.8)), vec2(0.28, 0.02));
        const pExh = pEng.sub(vec3(0.0, 0.0, -0.8));
        const exhCone = jetCylZ(pExh, vec2(0.10, 0.3));
        let struts = T.sdBox(pExh, vec3(0.28, 0.015, 0.15));
        struts = T.min(struts, T.sdBox(pExh, vec3(0.015, 0.28, 0.15)));
        hull = T.min(hull, T.min(turbineFace, T.min(exhCone, struts)));

        // res starts directly as the hull pair — the GLSL original
        // opU'd the hull against a vec2(1000.0, 0.0) sentinel first,
        // which is equivalent to just assigning the hull pair outright.
        let res = { dist: hull, mat: float(MAT_HULL) };

        // ---- Cockpit canopy (bubble glass) ----
        const canopy = T.sdEllipsoid(p.sub(vec3(0.0, 0.28, 1.2)), vec3(0.18, 0.20, 0.8));
        res = T.opU(res, { dist: canopy, mat: float(MAT_GLASS) });

        // ---- Engine plume (emissive ellipsoid behind each nozzle) ----
        const plume = T.sdEllipsoid(pEng.sub(vec3(0.0, 0.0, -1.4)), vec3(0.18, 0.18, 0.4));
        res = T.opU(res, { dist: plume, mat: float(MAT_PLUME) });

        // ---- Wing pylons + AAMs (built in the wing-swept frame so they
        //      hang parallel to the wing chord, not world Z). ----
        const pMis = pWing.sub(vec3(1.5, -0.25, 0.0));
        const pylon = T.sdBox(pMis.sub(vec3(0.0, 0.12, 0.0)), vec3(0.015, 0.12, 0.3));
        res = T.opU(res, { dist: pylon, mat: float(MAT_HULL) });

        let missile = jetCylZ(pMis, vec2(0.08, 0.8));
        missile = T.min(missile, T.sdEllipsoid(pMis.sub(vec3(0.0, 0.0, 0.8)), vec3(0.08, 0.08, 0.2)));
        missile = T.min(missile, T.sdBox(pMis.sub(vec3(0.0, 0.0, -0.6)), vec3(0.20, 0.01, 0.15)));
        missile = T.min(missile, T.sdBox(pMis.sub(vec3(0.0, 0.0, -0.6)), vec3(0.01, 0.20, 0.15)));
        res = T.opU(res, { dist: missile, mat: float(MAT_WEAPON) });

        // ---- Centerline bomb (asymmetric — built in unmirrored p) ----
        const pBomb = p.sub(vec3(0.0, -0.55, -0.5));
        const bombPylon = T.sdBox(pBomb.sub(vec3(0.0, 0.22, 0.0)), vec3(0.02, 0.22, 0.4));
        res = T.opU(res, { dist: bombPylon, mat: float(MAT_HULL) });

        let bomb = jetCylZ(pBomb, vec2(0.15, 0.9));
        bomb = T.min(bomb, T.sdEllipsoid(pBomb.sub(vec3(0.0, 0.0, 0.9)), vec3(0.15, 0.15, 0.3)));
        bomb = T.min(bomb, T.sdEllipsoid(pBomb.sub(vec3(0.0, 0.0, -0.9)), vec3(0.15, 0.15, 0.3)));
        let pbFin = pBomb.sub(vec3(0.0, 0.0, -0.7));
        const cBomb = Math.cos(0.785), sBomb = Math.sin(0.785);
        pbFin = vec3(pbFin.x.mul(cBomb).sub(pbFin.y.mul(sBomb)), pbFin.x.mul(sBomb).add(pbFin.y.mul(cBomb)), pbFin.z);
        bomb = T.min(bomb, T.sdBox(pbFin, vec3(0.25, 0.015, 0.15)));
        bomb = T.min(bomb, T.sdBox(pbFin, vec3(0.015, 0.25, 0.15)));
        res = T.opU(res, { dist: bomb, mat: float(MAT_WEAPON) });

        return res;
    },

    shade(p, n, mat, ctx) {
        const T = SDF_TSL;
        const { vec3, float } = T;
        const mode = EXAMPLES.stylizedFighterJet._u.uCamoMode;

        // Camo color resolver. The CAMO BLOBS are the only part that
        // varies by mode — the dark nose cone and wing pinstripes carry
        // through every scheme so the silhouette still reads as a
        // military airframe and not a plastic toy. `mode` is a runtime
        // uniform, so the GLSL if/else cascade becomes a nested
        // T.select() chain (a value-level branch) rather than a JS if.
        const jetCamoColor = (pp, modeVal) => {
            const blob = T.fbm(pp.mul(1.6));
            const t = T.smoothstep(0.50, 0.52, blob);

            const pick = (v0, v1, v2, v3) => T.select(modeVal.lessThan(0.5), v0,
                T.select(modeVal.lessThan(1.5), v1,
                    T.select(modeVal.lessThan(2.5), v2, v3)));

            // 0=silver/urban, 1=sky/air-superiority, 2=desert, 3=forest/woodland
            const light = pick(vec3(0.55, 0.57, 0.60), vec3(0.30, 0.40, 0.62), vec3(0.52, 0.42, 0.26), vec3(0.30, 0.34, 0.18));
            const dark = pick(vec3(0.26, 0.27, 0.29), vec3(0.08, 0.14, 0.34), vec3(0.28, 0.20, 0.12), vec3(0.12, 0.16, 0.08));
            let col = T.mix(light, dark, t);

            // Nose cone — dark sensor housing past z = 1.5, all modes.
            col = T.mix(col, vec3(0.20, 0.21, 0.22), T.smoothstep(1.5, 1.52, pp.z));

            // Wing pinstripes (dark accent + light line) on the outer
            // wing panels, gated to |x| > 0.6 via select() — the GLSL
            // `if` here existed purely to scope `ax`, so select()
            // reproduces the same gate at the value level.
            const ax = T.abs(pp.x);
            let striped = T.mix(vec3(0.13), col, T.smoothstep(0.38, 0.40, T.abs(ax.sub(2.0))));
            striped = T.mix(vec3(0.55), striped, T.smoothstep(0.08, 0.10, T.abs(ax.sub(1.4))));
            return T.select(ax.greaterThan(0.6), striped, col);
        };

        const SUN_DIR = T.normalize(vec3(0.45, 0.78, 0.30));
        // LOCAL-space view dir — ctx.ro is the local-space camera;
        // cameraPosition/p mixing world+local space is the bug this
        // convention avoids.
        const V = T.normalize(ctx.ro.sub(p));
        const H = T.normalize(SUN_DIR.add(V));
        const NdL = T.max(T.dot(n, SUN_DIR), 0.0);
        const NdV = T.max(T.dot(n, V), 0.0);
        const NdH = T.max(T.dot(n, H), 0.0);

        const sh = ctx.softShadow(p.add(n.mul(0.004)), SUN_DIR, 0.01, 12.0, float(24.0));
        const fres = T.pow(float(1.0).sub(NdV), 5.0);

        // FLAGGED APPROXIMATION — see the object-level comment above: no
        // HDRI plumbing on this TSL path, so sampleEnvMap()/
        // sdfReflectWorld() are replaced with a directional sky/ground
        // gradient. Keeps the "cool sky fill + brighter grazing-angle
        // reflection" shading role without an actual environment sample.
        const approxEnvMap = (dir) => T.mix(vec3(0.25, 0.22, 0.20), vec3(0.55, 0.70, 0.95), dir.y.mul(0.5).add(0.5));
        const R = T.reflect(V.negate(), n);
        const envR = approxEnvMap(R);
        const sun = vec3(1.15, 1.05, 0.85);
        const sky = approxEnvMap(vec3(0.0, 1.0, 0.0));

        const col = vec3(0.5).toVar();

        T.If(mat.lessThan(0.5), () => {
            // MAT_HULL — camo paint. Diffuse + soft sky fill + low-key
            // dielectric spec + a thin env sheen at grazing angles.
            const base = jetCamoColor(p, mode);
            const diffuse = base.mul(NdL.mul(sh).mul(sun).add(sky.mul(0.20)).add(vec3(0.05)));
            const spec = sun.mul(T.pow(NdH, 24.0)).mul(sh).mul(0.25);
            const env = envR.mul(fres).mul(0.10);
            col.assign(diffuse.add(spec).add(env));
        }).ElseIf(mat.lessThan(1.5), () => {
            // MAT_GLASS
            let c = vec3(0.02, 0.04, 0.07).add(envR.mul(fres.mul(0.95).add(0.06)));
            c = c.add(sun.mul(T.pow(NdH, 100.0)).mul(sh).mul(0.7));
            col.assign(c);
        }).ElseIf(mat.lessThan(2.5), () => {
            // MAT_WEAPON — dark olive ordnance with subtle warning bands
            // along the missile/bomb body axis (sin-on-z gives even ribbing).
            let base = vec3(0.20, 0.22, 0.18);
            const band = T.smoothstep(0.92, 1.0, T.abs(T.sin(p.z.mul(15.0))));
            base = base.mul(float(1.0).sub(band.mul(0.25)));
            const diffuse = base.mul(NdL.mul(sh).mul(sun).add(sky.mul(0.30)).add(vec3(0.04)));
            col.assign(diffuse.add(sun.mul(T.pow(NdH, 48.0)).mul(sh).mul(0.4)).add(envR.mul(fres).mul(0.08)));
        }).ElseIf(mat.lessThan(3.5), () => {
            // MAT_PLUME — hot core fading to orange/red at the silhouette edge.
            const core = NdV;
            const hot = vec3(2.4, 2.2, 1.4);
            const cool = vec3(2.0, 0.6, 0.15);
            col.assign(T.mix(cool, hot, T.smoothstep(0.0, 0.7, core)));
        }).Else(() => {
            col.assign(vec3(0.5));
        });

        return col;
    },

    /**
     * Direct-call factory.
     *
     * Options:
     *   camo:  'silver' | 'sky' | 'desert' | 'forest'
     *          OR equivalent integer 0..3.
     *          Default: 'sky' (air-superiority blue-grey).
     *            silver — light pewter on dark gunmetal (urban camo)
     *            sky    — slate blue-grey on dark blue (high-altitude)
     *            desert — coyote tan on dark khaki
     *            forest — olive on dark green-brown (woodland)
     *   The dark nose cone and wing pinstripes are mode-independent —
     *   only the camo blob colors vary between schemes.
     *
     * uCamoMode is now a live TSL uniform (EXAMPLES.stylizedFighterJet
     * ._u.uCamoMode) instead of the old GLSL `uniforms: {...}` override
     * spec — make() sets `_u.uCamoMode.value` directly, and the returned
     * mesh also gets `userData.sdfLiveUniforms` pointing at `_u` so a
     * caller can flip camo after creation with
     * `sdf.userData.sdfLiveUniforms.uCamoMode.value = 2`.
     */
    make(opts) {
        opts = opts || {};
        const _u = EXAMPLES.stylizedFighterJet._u;
        if (opts.camo !== undefined) {
            const namedToId = { silver: 0, sky: 1, desert: 2, forest: 3 };
            let id;
            if (typeof opts.camo === 'string') {
                id = namedToId[opts.camo.toLowerCase()];
                if (id === undefined) {
                    throw new Error(
                        `stylizedFighterJet: unknown camo "${opts.camo}". ` +
                        `Use one of: silver, sky, desert, forest.`,
                    );
                }
            } else {
                id = opts.camo | 0;
            }
            _u.uCamoMode.value = id;
        }
        const sdf = createSdfObject({ ...EXAMPLES.stylizedFighterJet });
        sdf.userData.sdfLiveUniforms = _u;
        return sdf;
    },
};

// =====================================================================
// Pyroclastic fireball — TSL port (2026-07-05) of a classic HLSL->GLSL
// displaced-sphere explosion. An animated sphere radius carries a
// rotating-octave fbm displacement; the DISPLACEMENT (not a material id)
// rides the march's mat channel into shade(), where it drives a
// hot-white -> yellow -> red -> smoke gradient. The hot core stays
// emissive (HDR values up to 4.0 — blooms under auto-enhance); the smoky
// rim picks up normal shading. The radius pulses on a ~25s cycle
// (sin(t*0.25)+0.5 — it collapses through zero for part of the cycle,
// faithful to the source), and the noise field scrolls downward so the
// fire appears to rise. Live knobs on _u: uSpeed / uNoiseFreq / uNoiseAmp.
// =====================================================================
EXAMPLES.explosion = {
    bounds: { min: [-2.1, -2.1, -2.1], max: [2.1, 2.1, 2.1] },
    quality: 'balanced',
    maxSteps: 64, stepScale: 0.5, surfEps: 0.005,
    _u: {
        uSpeed: SDF_TSL.uniform(1.0),
        uNoiseFreq: SDF_TSL.uniform(4.0),
        uNoiseAmp: SDF_TSL.uniform(-0.5),
    },
    // Rotating-octave fbm (distinct from SDF_TSL.fbm): each octave spins
    // through a fixed rotation so octaves decorrelate — that rotation is
    // what gives pyroclastic clouds their cauliflower look. Final octave
    // is abs()'d, total normalized by /0.9375 (faithful to the source).
    _mrot(v) {
        const { vec3 } = SDF_TSL;
        return vec3(
            v.y.mul(-0.80).add(v.z.mul(-0.60)),
            v.x.mul(0.80).add(v.y.mul(0.36)).add(v.z.mul(-0.48)),
            v.x.mul(0.60).add(v.y.mul(-0.48)).add(v.z.mul(0.64)),
        );
    },
    _fbmPyro(p) {
        const T = SDF_TSL;
        const E = EXAMPLES.explosion;
        let f = T.vnoise(p).mul(0.5000);
        let q = E._mrot(p).mul(2.02);
        f = f.add(T.vnoise(q).mul(0.2500)); q = E._mrot(q).mul(2.03);
        f = f.add(T.vnoise(q).mul(0.1250)); q = E._mrot(q).mul(2.01);
        f = f.add(T.vnoise(q).mul(0.0625)); q = E._mrot(q).mul(2.02);
        f = f.add(T.abs(T.vnoise(q)).mul(0.03125));
        return f.div(0.9375);
    },
    map(p) {
        const T = SDF_TSL;
        const { vec3 } = T;
        const E = EXAMPLES.explosion;
        const t = T.time.mul(E._u.uSpeed);
        const radius = T.sin(t.mul(0.25)).add(0.5);           // animated radius
        // pyroclastic displacement — scrolls downward so the fire rises
        const displace = E._fbmPyro(p.mul(E._u.uNoiseFreq).add(vec3(0.0, -1.0, 0.0).mul(t)));
        const d = T.length(p).sub(radius).add(displace.mul(E._u.uNoiseAmp));
        return { dist: d, mat: displace };   // displacement rides the mat channel
    },
    shade(p, n, mat /* = displacement at the hit */) {
        const T = SDF_TSL;
        const { vec3, float } = T;
        // color gradient lookup (hot white -> yellow -> red -> smoke grey)
        const x = T.clamp(mat.mul(1.5).sub(0.2), 0.0, 0.99);
        const t = T.fract(x.mul(3.0));
        const c0 = vec3(4.0, 4.0, 4.0), c1 = vec3(1.0, 1.0, 0.0);
        const c2 = vec3(1.0, 0.0, 0.0), c3 = vec3(0.4, 0.4, 0.4);
        const c = T.select(x.lessThan(0.3333), T.mix(c0, c1, t),
            T.select(x.lessThan(0.6666), T.mix(c1, c2, t), T.mix(c2, c3, t)));
        // hot core stays emissive; smoky rim picks up normal shading
        const diffuse = n.z.mul(0.5).add(0.5);
        return T.mix(c, c.mul(diffuse), T.clamp(x.sub(0.5).mul(2.0), 0.0, 1.0));
    },
    make(opts) {
        const o = { ...(opts || {}) };
        const E = EXAMPLES.explosion;
        if (o.speed != null) E._u.uSpeed.value = o.speed;
        if (o.noiseFreq != null) E._u.uNoiseFreq.value = o.noiseFreq;
        if (o.noiseAmp != null) E._u.uNoiseAmp.value = o.noiseAmp;
        delete o.speed; delete o.noiseFreq; delete o.noiseAmp;
        const sdf = createSdfObject({ ...EXAMPLES.explosion, ...o });
        sdf.userData.sdfLiveUniforms = E._u;
        return sdf;
    },
};

// =====================================================================
// Expanding smoke-ring detonation — TSL port (2026-07-05) of a torus-
// based volumetric nuke: a torus that eases outward over a ~4.5s loop
// while the volume INSIDE the tube rotates around the tube's own axis
// (the rolling-smoke effect), density from a 4-octave noise stack in the
// rotated space, heat->color palette that cools as the loop progresses,
// and a decay fade. This is the helper's first PARTICIPATING-MEDIA
// example — built on createSdfVolume (front-to-back density accumulation),
// not the surface march. The source's ground shadow/glow, camera shake
// and vignette are SCENE-level work and intentionally not part of the
// placeable. Live knob: _u.uSpeed. Camera stays outside the bounds box.
// =====================================================================
EXAMPLES.explosionRing = {
    bounds: { min: [-1.2, -0.25, -1.2], max: [1.2, 1.0, 1.2] },
    steps: 320,
    _u: {
        uSpeed: SDF_TSL.uniform(1.0),
    },
    // animation state, all derived from time (loops every 4.5s/uSpeed).
    // MEMOIZED: sample() runs once per march step — without the memo this
    // subgraph would be rebuilt into the shader once per step. Cleared in
    // make() so each built instance gets fresh nodes (never share TSL node
    // objects across material builds).
    _animMemo: null,
    _anim() {
        const E = EXAMPLES.explosionRing;
        if (E._animMemo) return E._animMemo;
        const T = SDF_TSL;
        const t = T.mod(T.time.mul(EXAMPLES.explosionRing._u.uSpeed), 4.5).mul(4.0);
        const rotT = T.pow(t.mul(0.2), 1.2);
        const decay = T.float(1.0).sub(T.smoothstep(7.0, 20.0, t));
        // easeOut(min(t,2), 0.01, 1, 2): u = min(t,2)/2 -> 0.01 + u*(2-u)
        const u = T.min(t, 2.0).div(2.0);
        const ease = u.mul(T.float(2.0).sub(u)).add(0.01);
        const r = T.clamp(ease, 0.0, 1.0).mul(0.1);
        const radius = r.mul(1.2).add(t.mul(0.02));
        const thickness = r.mul(2.0);
        E._animMemo = { t, rotT, decay, radius, thickness };
        return E._animMemo;
    },
    _sdTorus(p, tx, ty) {
        const T = SDF_TSL;
        const q = T.vec2(T.length(p.xz).sub(tx), p.y);
        return T.length(q).sub(ty);
    },
    // rotate the volume inside the tube around the tube's own axis — the
    // rolling-smoke effect. up is tilted 0.01 in z so cross() never
    // degenerates on the axis.
    _samplePos(rp, radius, rotT) {
        const T = SDF_TSL;
        const { vec3 } = T;
        const up = vec3(0.0, 1.0, 0.01);
        const fw = T.normalize(vec3(rp.x, 0.0, rp.z));
        const pIn = fw.mul(radius);
        const rt = T.cross(fw, up);
        const lp = rp.sub(pIn);
        // into the tube frame (transpose of [fw, up, rt])
        const l = vec3(T.dot(fw, lp), T.dot(up, lp), T.dot(rt, lp));
        // rotz(-rotT)
        const c = T.cos(rotT), s = T.sin(rotT);
        const l2 = vec3(l.x.mul(c).sub(l.y.mul(s)), l.x.mul(s).add(l.y.mul(c)), l.z);
        // back out of the tube frame
        return fw.mul(l2.x).add(up.mul(l2.y)).add(rt.mul(l2.z)).add(pIn);
    },
    _heatToColor(heat) {
        const T = SDF_TSL;
        const { vec3 } = T;
        let col = T.mix(vec3(0.0), vec3(1.0, 0.3, 0.0), T.clamp(heat.mul(15.0).sub(2.0), 0.0, 1.0));
        col = T.mix(col, vec3(1.0, 1.0, 0.6), T.clamp(heat.mul(15.1).sub(4.0), 0.0, 1.0));
        col = T.mix(col, vec3(1.0, 0.9, 0.8), T.clamp(heat.mul(190.0).sub(60.0), 0.0, 1.0));
        return col;
    },
    sample(p) {
        const T = SDF_TSL;
        const { vec3, float } = T;
        const E = EXAMPLES.explosionRing;
        const A = E._anim();

        // torus distance, noise-roughened (the dot(v,v) surface wobble)
        const v = T.cos(A.t.mul(0.15).add(p.mul(15.0))).add(T.sin(A.t.mul(0.25).add(p.mul(10.0))));
        const dRough = E._sdTorus(p, A.radius, A.thickness).sub(T.dot(v, v).mul(0.005));
        const dLo = E._sdTorus(p, A.radius, A.thickness).mul(0.005);

        // in-tube density shaping: 1 inside the tube, feathering at the wall
        // (source used reversed-edge smoothstep(0, -thick/2, d) — rewritten
        // to the defined-order form)
        const wall = float(1.0).sub(T.smoothstep(A.thickness.mul(-0.5), 0.0, dRough));

        // 4-octave noise stack in the ROTATED space (the rolling smoke)
        const sp = E._samplePos(p, A.radius, A.rotT);
        let d = T.vnoise(sp.mul(22.0)).mul(0.8);
        d = d.add(T.vnoise(sp.mul(70.0)).mul(0.4));
        d = d.add(T.vnoise(sp.mul(100.0)).mul(0.2));
        d = d.add(T.vnoise(sp.mul(350.0)).mul(0.45).mul(d));
        const density = T.clamp(wall.mul(d).sub(0.4).div(0.8), 0.0, 1.0);

        // heat cools as the loop progresses; low heat reads as grey smoke
        const heat = density.div(T.max(float(1.0), A.t.mul(0.5).sub(0.1)));
        const smoke = heat.div(0.03);
        const col = T.select(smoke.lessThan(1.0), vec3(smoke.mul(0.5)), E._heatToColor(heat));

        // per-sample opacity (density * source's 0.024 * decay), zeroed
        // below the ground line the source break'd at; adaptive step —
        // fine inside the tube, coarse in empty space
        const alpha = density.mul(0.024).mul(A.decay).mul(T.step(-0.2, p.y));
        // two-speed stepping (the source pre-marched coarsely to the tube,
        // then volume-marched finely): 1cm strides through empty space,
        // sub-mm inside the roughened tube
        const step = T.select(dRough.greaterThan(0.0), float(0.01), float(0.0015));
        return { color: col, alpha, step };
    },
    post(sum) {
        const T = SDF_TSL;
        // the source's contrast + alpha shaping (its sqrt() was display
        // encoding — our pipeline has its own output transform, skipped)
        return T.vec4(T.smoothstep(0.0, 0.3, sum.xyz), T.smoothstep(0.0, 0.95, sum.w));
    },
    make(opts) {
        const o = { ...(opts || {}) };
        const E = EXAMPLES.explosionRing;
        E._animMemo = null;   // fresh nodes per built instance
        if (o.speed != null) E._u.uSpeed.value = o.speed;
        delete o.speed;
        const vol = createSdfVolume({ ...EXAMPLES.explosionRing, ...o });
        vol.userData.sdfLiveUniforms = E._u;
        return vol;
    },
};

// =====================================================================
// Torch flame — TSL port (2026-07-05) of a classic 2D simplex-fbm flame,
// REVOLVED around the Y axis into a placeable volumetric fire. The 2D
// field is symmetric in its x coordinate, so the revolution is exact:
// q.x becomes the radial distance |p.xz|. Faithful pieces: the gradient-
// simplex noise + rotated-octave fbm (its own noise, NOT the engine's
// value noise — gradient noise is signed and the flame shape depends on
// it), the teardrop field, the downward-scrolling turbulence, the
// orange->yellow->white palette, and the late "smoke veil" mix. The
// flame occupies local y in [0, ~1.4]; base sits at y=0.
// Live knobs on _u: uStrength (1..5, turbulence scale a la the source's
// five side-by-side flames) and uSpeed.
// =====================================================================
EXAMPLES.flame = {
    bounds: { min: [-0.65, 0.0, -0.65], max: [0.65, 1.45, 0.65] },
    steps: 56,
    _u: {
        uStrength: SDF_TSL.uniform(3.0),
        uSpeed: SDF_TSL.uniform(1.0),
    },
    _animMemo: null,
    // signed 2D gradient hash (the source's): -1..1 per component
    _hash2(p) {
        const T = SDF_TSL;
        const { vec2 } = T;
        const q = vec2(T.dot(p, vec2(127.1, 311.7)), T.dot(p, vec2(269.5, 183.3)));
        return T.fract(T.sin(q).mul(43758.5453123)).mul(2.0).sub(1.0);
    },
    // 2D simplex noise (signed, ~-1..1)
    _noise2(p) {
        const T = SDF_TSL;
        const { vec2, vec3, float } = T;
        const E = EXAMPLES.flame;
        const K1 = 0.366025404, K2 = 0.211324865;
        const i = T.floor(p.add(p.x.add(p.y).mul(K1)));
        const a = p.sub(i).add(i.x.add(i.y).mul(K2));
        const o = T.select(a.x.greaterThan(a.y), vec2(1.0, 0.0), vec2(0.0, 1.0));
        const b = a.sub(o).add(K2);
        const c = a.sub(1.0).add(2.0 * K2);
        const h = T.max(vec3(0.5).sub(vec3(T.dot(a, a), T.dot(b, b), T.dot(c, c))), vec3(0.0));
        const h4 = h.mul(h).mul(h).mul(h);
        const n = h4.mul(vec3(
            T.dot(a, E._hash2(i)),
            T.dot(b, E._hash2(i.add(o))),
            T.dot(c, E._hash2(i.add(1.0)))));
        return T.dot(n, vec3(70.0));
    },
    // rotated-octave fbm, remapped to 0..1 (m2 = [1.6 1.2; -1.2 1.6])
    _fbm2(uv) {
        const T = SDF_TSL;
        const { vec2 } = T;
        const E = EXAMPLES.flame;
        const m2 = (v) => vec2(v.x.mul(1.6).sub(v.y.mul(1.2)), v.x.mul(1.2).add(v.y.mul(1.6)));
        let f = E._noise2(uv).mul(0.5000);
        let q = m2(uv);
        f = f.add(E._noise2(q).mul(0.2500)); q = m2(q);
        f = f.add(E._noise2(q).mul(0.1250)); q = m2(q);
        f = f.add(E._noise2(q).mul(0.0625));
        return f.mul(0.5).add(0.5);
    },
    sample(p) {
        const T = SDF_TSL;
        const { vec2, vec3, float } = T;
        const E = EXAMPLES.flame;
        if (!E._animMemo) {
            const strength = E._u.uStrength;
            E._animMemo = {
                strength,
                T3: T.max(float(3.0), strength.mul(1.25)).mul(T.time).mul(E._u.uSpeed),
            };
        }
        const { strength, T3 } = E._animMemo;

        // revolve the 2D flame field: q.x = radial distance, q.y = height-0.25
        const q = vec2(T.length(p.xz), p.y.sub(0.25));
        const n = E._fbm2(q.mul(strength).sub(vec2(0.0, 1.0).mul(T3)));
        const c = float(1.0).sub(T.pow(T.max(float(0.0),
            T.length(q.mul(vec2(q.y.mul(1.5).add(1.8), 0.75)))
                .sub(n.mul(T.max(float(0.0), q.y.add(0.25))))), 1.2).mul(16.0));
        // max(0, y) before pow: WGSL pow(x, y) is NaN for x < 0 — without the
        // guard every sample below the flame base (p.y < 0 in the bounds box)
        // went NaN and rendered as a garbage slab + mirrored flame ghost.
        const c1 = T.clamp(n.mul(c).mul(float(1.5).sub(T.pow(T.max(float(0.0), p.y).mul(1.25), 4.0))), 0.0, 1.0);

        // palette: orange base -> yellow -> white-hot core
        let col = vec3(c1.mul(1.5), c1.mul(c1).mul(c1).mul(1.5),
            c1.mul(c1).mul(c1).mul(c1).mul(c1).mul(c1));
        // late smoke veil (the source's "just added" line)
        const veil = T.pow(E._fbm2(q.mul(strength).mul(1.25).sub(vec2(0.0, 1.0).mul(T3))), 2.0);
        col = T.mix(col, vec3(T.pow(veil, 2.0)),
            T.clamp(float(0.75).sub(col.x.add(col.y).add(col.z).div(3.0)), 0.0, 1.0));

        // per-sample opacity from the flame field, fading toward the tip.
        // GATED by the flame intensity c1: the raw field c stays positive in
        // a fat noise-inflated column the full height of the bounds box, and
        // its color there is the gray smoke veil — ungated it rendered the
        // whole box as a milky slab around the visible fire.
        const a = T.clamp(c, 0.0, 1.0)
            .mul(T.smoothstep(0.02, 0.22, c1))
            .mul(float(1.0).sub(T.pow(T.clamp(p.y.div(1.4), 0.0, 1.0), 3.0)));
        return { color: col, alpha: a.mul(0.22), step: float(0.028) };
    },
    make(opts) {
        const o = { ...(opts || {}) };
        const E = EXAMPLES.flame;
        E._animMemo = null;   // fresh nodes per built instance
        if (o.strength != null) E._u.uStrength.value = o.strength;
        if (o.speed != null) E._u.uSpeed.value = o.speed;
        delete o.strength; delete o.speed;
        const vol = createSdfVolume({ ...EXAMPLES.flame, ...o });
        vol.userData.sdfLiveUniforms = E._u;
        return vol;
    },
};

// =====================================================================
// Smoke column — an ORIGINAL volumetric example (2026-07-05, not a port):
// a rising, widening plume. Density = a radial column profile (radius
// grows with height) gated by two upward-advected fbm fields (one fine,
// one slow billow), faded in at the base and dissipating at the top.
// Grey-blue gradient, slightly darker at the base. Reads correctly over
// any backdrop thanks to premultiplied accumulation. Live knobs on _u:
// uSpeed, uDensity.
// =====================================================================
EXAMPLES.smoke = {
    bounds: { min: [-0.95, 0.0, -0.95], max: [0.95, 2.6, 0.95] },
    steps: 80,
    _u: {
        uSpeed: SDF_TSL.uniform(1.0),
        uDensity: SDF_TSL.uniform(1.0),
    },
    _animMemo: null,
    sample(p) {
        const T = SDF_TSL;
        const { vec3, float } = T;
        const E = EXAMPLES.smoke;
        if (!E._animMemo) E._animMemo = { t: T.time.mul(E._u.uSpeed) };
        const { t } = E._animMemo;

        const h = T.clamp(p.y.div(2.4), 0.0, 1.0);
        // column profile: radius widens with height, soft wall
        const rad = h.mul(0.5).add(0.14);
        const core = float(1.0).sub(T.smoothstep(rad.mul(0.35), rad, T.length(p.xz)));
        // two advected turbulence fields (scroll down = smoke rises)
        const fine = T.fbm(p.mul(3.2).add(vec3(0.0, -0.95, 0.0).mul(t)));
        const billow = T.fbm(p.mul(1.4).add(vec3(0.22, -0.6, 0.0).mul(t)).add(7.3));
        let dens = core.mul(T.smoothstep(0.28, 0.74, fine.mul(0.65).add(billow.mul(0.55))));
        // fade in at the base, dissipate at the top
        dens = dens.mul(T.smoothstep(0.0, 0.18, p.y))
            .mul(float(1.0).sub(T.smoothstep(1.8, 2.55, p.y)));

        // grey-blue, darker at the base, faint warm lift where dense
        const col = T.mix(vec3(0.16, 0.16, 0.17), vec3(0.52, 0.54, 0.58), h)
            .add(dens.mul(0.05));
        return { color: col, alpha: dens.mul(0.09).mul(E._u.uDensity), step: float(0.05) };
    },
    make(opts) {
        const o = { ...(opts || {}) };
        const E = EXAMPLES.smoke;
        E._animMemo = null;   // fresh nodes per built instance
        if (o.speed != null) E._u.uSpeed.value = o.speed;
        if (o.density != null) E._u.uDensity.value = o.density;
        delete o.speed; delete o.density;
        const vol = createSdfVolume({ ...EXAMPLES.smoke, ...o });
        vol.userData.sdfLiveUniforms = E._u;
        return vol;
    },
};



// GLSL primitive library as a raw string for agents building unrelated
// ShaderMaterials that want the same primitives.
const SDF_PRIMITIVES = SDF_PRIMITIVES_GLSL;

// ═══════════════════════════════════════════════════════════════════════
//  makeSdfTexture — render an SDF into an off-screen WebGLRenderTarget
//
//  Different from createSdfObject: that one places an SDF body in the
//  3D scene and integrates with depth/lighting. THIS one renders an
//  SDF (with its own internal orbiting camera) into a texture, so the
//  resulting texture can be plugged into any material's `map` /
//  `emissiveMap` / wherever — same SDF, multiple monitors, full PBR.
//
//  Usage:
//
//      const bulb = SdfRaymarchLoader.makeSdfTexture({
//          recipe: 'mandelbulb',
//          width: 512, height: 256,
//          uniforms: { power: 8.0, iterations: 96, paletteHueShift: 0.0 },
//          cameraOrbitRadius: 2.6, cameraOrbitSpeed: 0.18,
//          cameraPitch: 0.4, cameraFov: 1.6,
//          updateEvery: 1,
//      });
//      const tv = new THREE.Mesh(plane, new THREE.MeshStandardMaterial({
//          map: bulb.texture,
//          emissiveMap: bulb.texture,
//          emissive: 0xffffff, emissiveIntensity: 0.9,
//      }));
//      // In renderFrame:
//      bulb.update(t, renderer);
//      composer.render();
//
//  Recipes shipped: 'mandelbulb', 'sierpinski_tetra', 'menger_sponge',
//  'gyroid'. Pass `customDe`/`customShade` GLSL strings to override.
// ═══════════════════════════════════════════════════════════════════════

const SDF_TEX_VERTEX_SHADER = /* glsl */`
varying vec2 vUv;
void main() {
    vUv = uv;
    gl_Position = vec4(position, 1.0);
}
`;

// HSV-cycle palette as a default, plus a few canned alternatives the
// recipes can switch via paletteMode (0=spectrum_warm, 1=cyan_pink,
// 2=mono_amber, 3=greenscale).
const SDF_TEX_PALETTE_GLSL = /* glsl */`
vec3 sdfTexPalette(float t, vec3 p, float mode) {
    if (mode < 0.5) {
        return 0.5 + 0.5 * cos(t * 0.30 + p * 3.5 + vec3(0.0, 2.1, 4.2));
    } else if (mode < 1.5) {
        vec3 a = vec3(0.10, 0.65, 0.85);
        vec3 b = vec3(0.95, 0.20, 0.60);
        float k = 0.5 + 0.5 * sin(t * 0.4 + p.x * 2.5 + p.z * 1.7);
        return mix(a, b, k);
    } else if (mode < 2.5) {
        vec3 amber = vec3(1.0, 0.62, 0.18);
        float k = 0.4 + 0.6 * sin(t * 0.35 + length(p) * 3.0);
        return amber * (0.55 + 0.45 * k);
    } else {
        vec3 g = vec3(0.20, 0.95, 0.55);
        float k = 0.5 + 0.5 * sin(t * 0.45 + p.y * 4.0);
        return g * (0.4 + 0.6 * k);
    }
}
`;

// Default shade — Lambert + fresnel + iter-based AO + palette colour.
const SDF_TEX_DEFAULT_SHADE = /* glsl */`
vec3 sdfTexShade(vec3 p, vec3 n, vec3 rd, int iter, int maxIter, float t, float paletteMode) {
    float ao = 1.0 - float(iter) / float(maxIter);
    vec3 lDir = normalize(vec3(0.6, 0.8, -0.3));
    float diff = max(dot(n, lDir), 0.0);
    float fres = pow(1.0 - max(0.0, dot(n, -rd)), 2.5);
    vec3 baseCol = sdfTexPalette(t, p, paletteMode);
    vec3 col = baseCol * (0.25 + 0.85 * diff) * (0.45 + 0.55 * ao);
    col += vec3(1.0, 0.75, 0.5) * fres * 0.7;
    col += vec3(1.0, 0.9, 0.7) * pow(1.0 - max(0.0, dot(-rd, n)), 8.0) * 0.4;
    return col;
}
`;

// Default sky — soft nebula gradient + sparse stars, fading from the
// silhouette edge of the SDF body.
const SDF_TEX_DEFAULT_SKY = /* glsl */`
vec3 sdfTexSky(vec2 uv, float minDist, float t, float paletteMode) {
    vec3 a, b, glow;
    if (paletteMode < 0.5)        { a = vec3(0.05,0.02,0.08); b = vec3(0.20,0.04,0.16); glow = vec3(0.95,0.55,0.85); }
    else if (paletteMode < 1.5)   { a = vec3(0.02,0.04,0.10); b = vec3(0.04,0.10,0.22); glow = vec3(0.40,0.85,1.00); }
    else if (paletteMode < 2.5)   { a = vec3(0.06,0.04,0.02); b = vec3(0.18,0.10,0.04); glow = vec3(1.00,0.65,0.25); }
    else                          { a = vec3(0.02,0.06,0.03); b = vec3(0.04,0.16,0.08); glow = vec3(0.30,0.95,0.55); }
    vec3 sky = mix(a, b, 0.5 + 0.5 * uv.y);
    sky += glow * exp(-minDist * 7.0) * 0.6;
    vec2 starUV = uv * 18.0;
    float starHash = fract(sin(dot(floor(starUV), vec2(127.1, 311.7))) * 43758.5);
    float star = smoothstep(0.985, 1.0, starHash) * (0.7 + 0.3 * sin(t * 2.0 + starHash * 12.0));
    sky += vec3(1.0, 0.95, 0.85) * star;
    return sky;
}
`;

// ── Recipe distance estimators ────────────────────────────────────────
const SDF_TEX_RECIPES = {
    mandelbulb: {
        defaultUniforms: {
            power: 8.0, iterations: 96, bailout: 6.0,
            paletteMode: 0.0, paletteHueShift: 0.0,
        },
        de: /* glsl */`
            float DE(vec3 pos) {
                vec3 z = pos;
                float dr = 1.0;
                float r = 0.0;
                // Mandelbulb inner-iteration count is fixed at 8 — uPower
                // is the fractal exponent, not the iteration count.
                for (int i = 0; i < 8; i++) {
                    r = length(z);
                    if (r > 2.0) break;
                    float theta = acos(clamp(z.z / r, -1.0, 1.0));
                    float phi   = atan(z.y, z.x);
                    dr = pow(r, uPower - 1.0) * uPower * dr + 1.0;
                    float zr = pow(r, uPower);
                    theta = theta * uPower;
                    phi   = phi * uPower;
                    z = zr * vec3(sin(theta) * cos(phi),
                                  sin(theta) * sin(phi),
                                  cos(theta));
                    z += pos;
                }
                return 0.5 * log(r) * r / dr;
            }
        `,
    },
    sierpinski_tetra: {
        // Kaleidoscopic IFS folded tetrahedron — sharp crystalline geometry.
        defaultUniforms: {
            power: 1.0, iterations: 80, bailout: 8.0,
            paletteMode: 1.0, paletteHueShift: 0.0,
            scale: 2.0, foldCount: 12.0,
        },
        de: /* glsl */`
            float DE(vec3 pos) {
                vec3 a1 = vec3( 1.0,  1.0,  1.0);
                vec3 a2 = vec3(-1.0, -1.0,  1.0);
                vec3 a3 = vec3( 1.0, -1.0, -1.0);
                vec3 a4 = vec3(-1.0,  1.0, -1.0);
                vec3 z = pos;
                float dist;
                for (int i = 0; i < 24; i++) {
                    if (float(i) >= uFoldCount) break;
                    vec3 c = a1; float minDist = length(z - a1);
                    dist = length(z - a2); if (dist < minDist) { c = a2; minDist = dist; }
                    dist = length(z - a3); if (dist < minDist) { c = a3; minDist = dist; }
                    dist = length(z - a4); if (dist < minDist) { c = a4; }
                    z = uScale * z - c * (uScale - 1.0);
                }
                return length(z) * pow(uScale, -float(uFoldCount));
            }
        `,
    },
    menger_sponge: {
        // Iterated cube subtraction — recursive cross-cut grid.
        defaultUniforms: {
            power: 1.0, iterations: 90, bailout: 8.0,
            paletteMode: 2.0, paletteHueShift: 0.0,
            foldCount: 5.0,
        },
        de: /* glsl */`
            float sdBox(vec3 p, vec3 b) {
                vec3 d = abs(p) - b;
                return min(max(d.x, max(d.y, d.z)), 0.0) + length(max(d, 0.0));
            }
            float DE(vec3 pos) {
                float d = sdBox(pos, vec3(1.0));
                float s = 1.0;
                for (int i = 0; i < 8; i++) {
                    if (float(i) >= uFoldCount) break;
                    vec3 a = mod(pos * s, 2.0) - 1.0;
                    s *= 3.0;
                    vec3 r = 1.0 - 3.0 * abs(a);
                    float c = (min(max(r.x, r.y), min(max(r.y, r.z), max(r.z, r.x)))) / s;
                    d = max(d, c);
                }
                return d;
            }
        `,
    },
    gyroid: {
        // Triply periodic minimal surface — endless interlinked tunnels.
        defaultUniforms: {
            power: 1.0, iterations: 80, bailout: 8.0,
            paletteMode: 3.0, paletteHueShift: 0.0,
            scale: 3.5, isoOffset: 0.0,
        },
        de: /* glsl */`
            float DE(vec3 pos) {
                vec3 p = pos * uScale;
                float g = dot(sin(p), cos(p.yzx)) - uIsoOffset;
                return g * 0.55 / uScale;
            }
        `,
    },
};

function _glslUniformDeclarations(uniforms) {
    // Map JS uniforms to GLSL uniform declarations. All numeric values
    // become `uniform float u<Name>;`. Booleans are floats too.
    const lines = [];
    for (const k of Object.keys(uniforms)) {
        const upper = 'u' + k[0].toUpperCase() + k.slice(1);
        lines.push(`uniform float ${upper};`);
    }
    return lines.join('\n');
}

function _buildSdfTexFragmentShader(recipe, customDe, customShade) {
    const deGLSL = customDe || recipe.de;
    const shadeBlock = customShade
        ? `vec3 sdfTexShade(vec3 p, vec3 n, vec3 rd, int iter, int maxIter, float t, float paletteMode) { ${customShade} }`
        : SDF_TEX_DEFAULT_SHADE;
    const declared = _glslUniformDeclarations(recipe.defaultUniforms);
    return [
        'precision highp float;',
        'varying vec2 vUv;',
        'uniform float uTime;',
        'uniform float uAspect;',
        'uniform float uOrbitR;',
        'uniform float uOrbitSpeed;',
        'uniform float uPitch;',
        'uniform float uFov;',
        'uniform vec3  uTarget;',
        declared,
        SDF_TEX_PALETTE_GLSL,
        deGLSL,
        'vec3 calcNormal(vec3 p) {',
        '    const float h = 0.0008;',
        '    const vec2 k = vec2(1.0, -1.0);',
        '    return normalize(',
        '        k.xyy * DE(p + k.xyy * h) +',
        '        k.yyx * DE(p + k.yyx * h) +',
        '        k.yxy * DE(p + k.yxy * h) +',
        '        k.xxx * DE(p + k.xxx * h)',
        '    );',
        '}',
        shadeBlock,
        SDF_TEX_DEFAULT_SKY,
        'void main() {',
        '    vec2 uv = vUv * 2.0 - 1.0;',
        '    uv.x *= uAspect;',
        '    float ang = uTime * uOrbitSpeed;',
        '    float ca = cos(ang), sa = sin(ang);',
        '    vec3 ro = uTarget + vec3(sa * uOrbitR, uPitch + 0.30 * sin(uTime * 0.12), ca * uOrbitR);',
        '    vec3 ww = normalize(uTarget - ro);',
        '    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));',
        '    vec3 vv = cross(uu, ww);',
        '    vec3 rd = normalize(uv.x * uu + uv.y * vv + uFov * ww);',
        '    float t = 0.5;',
        '    float minDist = 1e9;',
        '    int hitIter = 0;',
        '    bool hit = false;',
        '    const int MAX_ITER = 160;',
        '    for (int i = 0; i < MAX_ITER; i++) {',
        '        if (float(i) >= uIterations) break;',
        '        vec3 p = ro + rd * t;',
        '        float d = DE(p);',
        '        minDist = min(minDist, d);',
        '        if (d < 0.0008 * t) { hit = true; hitIter = i; break; }',
        '        if (t > uBailout) break;',
        '        t += d * 0.85;',
        '    }',
        '    vec3 col;',
        '    if (hit) {',
        '        vec3 p = ro + rd * t;',
        '        vec3 n = calcNormal(p);',
        '        col = sdfTexShade(p, n, rd, hitIter, MAX_ITER, uTime, uPaletteMode);',
        '    } else {',
        '        col = sdfTexSky(uv, minDist, uTime, uPaletteMode);',
        '    }',
        '    vec2 buv = vUv;',
        '    float vig = smoothstep(0.0, 0.04, buv.x) * smoothstep(0.0, 0.04, buv.y)',
        '              * smoothstep(0.0, 0.04, 1.0-buv.x) * smoothstep(0.0, 0.04, 1.0-buv.y);',
        '    col *= 0.55 + 0.45 * vig;',
        '    gl_FragColor = vec4(col, 1.0);',
        '}',
    ].join('\n');
}

function makeSdfTexture(opts) {
    if (!THREE) {
        throw new Error('sdf_raymarch_loader.makeSdfTexture: window.THREE not found.');
    }
    opts = opts || {};
    const recipeName = opts.recipe || 'mandelbulb';
    const recipe = SDF_TEX_RECIPES[recipeName];
    if (!recipe && !opts.customDe) {
        throw new Error(`makeSdfTexture: unknown recipe '${recipeName}'. ` +
            `Built-ins: ${Object.keys(SDF_TEX_RECIPES).join(', ')}. ` +
            `Pass customDe to use your own.`);
    }
    const baseRecipe = recipe || { defaultUniforms: { power: 1, iterations: 96, bailout: 6.0, paletteMode: 0.0 } };

    const width  = opts.width  | 0 || 512;
    const height = opts.height | 0 || 256;
    const aspect = opts.aspect != null ? opts.aspect : (width / height);

    // Merge default + user uniforms
    const mergedUniforms = Object.assign({}, baseRecipe.defaultUniforms, opts.uniforms || {});
    const u = {
        uTime:        { value: 0 },
        uAspect:      { value: aspect },
        uOrbitR:      { value: opts.cameraOrbitRadius != null ? opts.cameraOrbitRadius : 2.6 },
        uOrbitSpeed:  { value: opts.cameraOrbitSpeed  != null ? opts.cameraOrbitSpeed  : 0.18 },
        uPitch:       { value: opts.cameraPitch       != null ? opts.cameraPitch       : 0.4 },
        uFov:         { value: opts.cameraFov         != null ? opts.cameraFov         : 1.6 },
        uTarget:      { value: new THREE.Vector3(
            ...((opts.cameraTarget && opts.cameraTarget.length === 3) ? opts.cameraTarget : [0, 0, 0])
        )},
    };
    for (const k of Object.keys(mergedUniforms)) {
        const upper = 'u' + k[0].toUpperCase() + k.slice(1);
        u[upper] = { value: mergedUniforms[k] };
    }

    const fragmentShader = _buildSdfTexFragmentShader(baseRecipe, opts.customDe, opts.customShade);
    const material = new THREE.ShaderMaterial({
        uniforms: u,
        vertexShader: SDF_TEX_VERTEX_SHADER,
        fragmentShader,
        depthTest: false, depthWrite: false,
    });

    // Private fullscreen-quad scene + ortho camera
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    const scene = new THREE.Scene();
    scene.add(quad);
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    // Render target
    const renderTarget = new THREE.WebGLRenderTarget(width, height, {
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
        format:    THREE.RGBAFormat,
        type:      THREE.UnsignedByteType,
        depthBuffer: false,
        stencilBuffer: false,
    });
    renderTarget.texture.colorSpace = THREE.SRGBColorSpace;
    renderTarget.texture.generateMipmaps = false;
    if (opts.anisotropy && opts.anisotropy > 1) {
        renderTarget.texture.anisotropy = opts.anisotropy;
    }

    let frameCount = 0;
    const updateEvery = Math.max(1, opts.updateEvery | 0 || 1);

    function update(t, renderer) {
        if (frameCount % updateEvery !== 0) { frameCount++; return; }
        frameCount++;
        material.uniforms.uTime.value = t;
        // Bypass render_scene.mjs's monkey-patch on renderer.render so
        // we write to OUR render target, not the auto-composer's.
        const doRender = renderer._origRender
            ? renderer._origRender
            : renderer.render.bind(renderer);
        const oldRT = renderer.getRenderTarget();
        const oldClear = renderer.autoClear;
        renderer.autoClear = true;
        renderer.setRenderTarget(renderTarget);
        doRender(scene, camera);
        renderer.setRenderTarget(oldRT);
        renderer.autoClear = oldClear;
    }

    function setUniform(name, value) {
        const upper = name.startsWith('u') && name.length > 1 && name[1] === name[1].toUpperCase()
            ? name : ('u' + name[0].toUpperCase() + name.slice(1));
        if (material.uniforms[upper]) material.uniforms[upper].value = value;
    }

    function dispose() {
        renderTarget.dispose();
        material.dispose();
        quad.geometry.dispose();
    }

    return {
        texture: renderTarget.texture,
        renderTarget, material, scene, camera,
        update, setUniform, dispose,
    };
}

// Window-attachment shim. When this module is loaded as an ES module
// inside a browser page (e.g. via `<script type="module">` injected by
// render_scene.mjs's loader hook), expose the API on a stable global so
// scene scripts evaluated in plain script context can call into it
// without doing their own ESM import. ESM consumers see no behavioural
// change — they keep using the named exports.
if (typeof window !== 'undefined') {
    window.SdfRaymarchLoader = {
        QUALITY_PRESETS,
        createSdfObject,
        createSdfVolume,
        registerSdfHelper,
        EXAMPLES,
        SDF_PRIMITIVES,
        SDF_TSL,
        makeSdfTexture,
        SDF_TEX_RECIPES,
    };

    // ─── Agent-discoverable help ───
    window.SdfRaymarchLoader.help = function () {
        const exampleNames = (typeof EXAMPLES === 'object' && EXAMPLES) ? Object.keys(EXAMPLES) : [];
        const recipeNames  = (typeof SDF_TEX_RECIPES === 'object' && SDF_TEX_RECIPES) ? Object.keys(SDF_TEX_RECIPES) : [];
        const qualityNames = (typeof QUALITY_PRESETS === 'object' && QUALITY_PRESETS) ? Object.keys(QUALITY_PRESETS) : [];
        const lines = [
            '────────── SdfRaymarchLoader API reference ──────────',
            '',
            "Build ANY raymarched object — characters, vehicles, buildings, abstract",
            "geometry, anything you can describe with a signed distance function. The",
            "EXAMPLES list (stylizedModernSedan, stylizedFighterJet, etc.) is just convenience shortcuts —",
            "the real power is writing your OWN map(p) GLSL function and dropping it in.",
            '',
            '════════ PRIMARY USE: roll your own SDF ════════',
            '',
            "Pass GLSL strings to createSdfObject — `map(p)` returns vec2(distance, matId),",
            "`shade(p, n, mat)` returns the surface color. SDF_PRIMITIVES is auto-prepended,",
            "so all the primitives + ops below are available in your strings.",
            '',
            '── Minimal recipe ──',
            '  const sdf = SdfRaymarchLoader.createSdfObject({',
            '    bounds: { min: [-1.5, -1, -1.5], max: [1.5, 1, 1.5] },',
            "    quality: 'balanced',",
            '    map: `',
            '      vec2 map(vec3 p) {',
            '        // Two spheres smoothly joined into a peanut',
            '        float a = sdSphere(p - vec3(-0.4, 0.0, 0.0), 0.5);',
            '        float b = sdSphere(p - vec3( 0.4, 0.0, 0.0), 0.5);',
            '        return vec2(smin(a, b, 0.3), 1.0);',
            '      }`,',
            '    shade: `',
            '      vec3 shade(vec3 p, vec3 n, float mat) {',
            '        vec3 L = normalize(vec3(0.5, 0.9, 0.4));',
            '        return vec3(0.85, 0.45, 0.25) * (0.4 + 0.6 * max(0.0, dot(n, L)));',
            '      }`,',
            '  });',
            '  scene.add(sdf.mesh);',
            '  // Per frame: sdf.update(t);',
            '',
            '── Available primitives (auto-included in your map() GLSL) ──',
            '  sdSphere(p, r)  sdSphere(p, c, r)               sphere',
            '  sdBox(p, halfExtents)  sdRoundBox(p, b, r)      axis-aligned box',
            '  sdCapsule(p, a, b, r)                            capsule between two points',
            '  sdCap2(p, a, b, r1, r2)                          tapered capsule (limbs!)',
            '  sdEllipsoid(p, radii)  sdEllipsoid(p, c, r)     squashed sphere',
            '  sdTorus(p, vec2(R, r))                           donut',
            '  sdCone(p, vec2(sin/cos), h)                      cone',
            '  sdRoundCone(p, a, b, r1, r2)                     ice-cream-cone shape',
            '  sdTriPrism(p, hx, hz)                            triangular prism',
            '',
            '── Combinators (same library) ──',
            '  smin(a, b, k)               smooth union of two distances (k = blend radius)',
            '  smax(a, b, k)               smooth intersection',
            '  opSub(a, b)  opSmoothSub(a, b, k)                a minus b',
            '  opInt(a, b)                 a intersected with b',
            '  opRotateX/Y/Z(p, angle)     rotate the SAMPLING POINT (cheap rotation)',
            '  opMirrorX/Z(p)              fold for symmetry (build half, mirror)',
            '',
            '── Recipe patterns ──',
            '  • Character body:  capsule (torso) + 4 sdCap2 (limbs) + 2 sdSphere (head/eyes),',
            "                     all union'd with smin(k=0.05) for soft attach. Animate by",
            '                     varying limb endpoints with sin(uTime).',
            '  • Crystal/gem:     sdOctahedron OR sdEllipsoid (radii != equal) + tiny',
            '                     spheres at vertices via opSmoothU, animated emissive.',
            "  • Tentacle:        chain of sdCap2 with each segment's centerpoint computed",
            '                     from sin(uTime + segmentIndex), smin them together.',
            '  • Hollow shell:    opSmoothSub(innerSphere, outerSphere, k=0.05).',
            '  • Repeating prop:  domain mod p = mod(p + period/2, period) - period/2 to',
            '                     get an infinite grid of one shape (cheap forest, fence).',
            '',
            '── Custom uniforms (drive shape from JS each frame) ──',
            '  const sdf = createSdfObject({',
            '    map: `vec2 map(vec3 p) { return vec2(sdSphere(p, uRadius), 1.0); }`,',
            '    shade: `vec3 shade(vec3 p, vec3 n, float m) { return uColor; }`,',
            '    uniforms: { uRadius: { value: 0.5 }, uColor: { value: new THREE.Color(0xff7a3c) } },',
            '  });',
            '  // Per frame: sdf.material.uniforms.uRadius.value = 0.5 + 0.2*Math.sin(t);',
            '',
            '── createSdfObject(spec) full signature ──',
            '  spec.map        REQUIRED   GLSL string defining `vec2 map(vec3 p)`',
            '  spec.shade      REQUIRED   GLSL string defining `vec3 shade(vec3 p, vec3 n, float mat)`',
            '  spec.extra      optional   GLSL prepended (helper functions, your own constants)',
            '  spec.bounds     optional   { min: [x,y,z], max: [x,y,z] } — TIGHTEN for performance',
            '  spec.quality    optional   preset name — see QUALITY_PRESETS below',
            '  spec.uniforms   optional   { name: { value: ... } } — accessible by name in your GLSL',
            '  spec.maxSteps / maxDist / stepScale / surfEps  override quality preset internals',
            '',
            '════════ SHORTCUTS: drop in a registered example ════════',
            '',
            '  const sdf = SdfRaymarchLoader.createSdfObject(EXAMPLES.stylizedModernSedan);',
            '  // OR via registerSdfHelper for examples that expose custom uniforms (mood, etc.)',
            '',
            '── Pre-built EXAMPLES (' + exampleNames.length + ') ──',
            '  ' + (exampleNames.join(', ') || '(none registered)'),
            '  (these are just convenience — read them as templates for your own SDFs)',
            '',
            '── Quality presets (' + qualityNames.length + ') ──',
            '  ' + (qualityNames.join(', ') || '(none)') + '   — controls march steps + screen scale',
            '',
            '════════ TEXTURED-QUAD MODE: makeSdfTexture() ════════',
            '',
            'Render a SDF directly into a CanvasTexture-style target — for CRT screen',
            'content, holograms, billboards, animated wallpaper. No separate scene/composer.',
            "  const tex = SdfRaymarchLoader.makeSdfTexture({",
            "    recipe: 'cube_neon', width: 512, height: 512, palette: [...],",
            '  });',
            '  someMesh.material.map = tex.texture;',
            '  // Per frame: tex.update(t);',
            '',
            '── SDF_TEX_RECIPES (' + recipeNames.length + ') ──',
            '  ' + (recipeNames.join(', ') || '(none)'),
            '',
            '════════ Common gotchas ════════',
            '  • SDF raymarching is fragment-shader-bound — make `bounds` as TIGHT as',
            '    possible. Rays exit cheaply outside the bounding box.',
            "  • Quality trade-off: marchSteps × screenScale = pixel cost. 'low' for",
            "    distant objects, 'medium' for hero shots, 'high' for stills only.",
            '  • In your map(): return vec2(distance, materialId). materialId is a float',
            '    you receive in shade() to pick colors per region.',
            '  • smin(k=...) — small k (0.05) = subtle blend, large k (0.3) = mushy organic',
            "    melt. Match k to the unit scale of your bounds.",
            '  • SDF objects write proper depth via the depth-pipe pre-pass — they',
            "    composite correctly with regular meshes (won't show through walls).",
            '',
            'Source: /opt/render3d/sdf_raymarch_loader.js  (search for SDF_PRIMITIVES_GLSL',
            'for the full primitive library, or grep "EXAMPLES = {" for templates).',
        ];
        const msg = lines.join('\n');
        console.log(msg);
        return msg;
    };

    console.log('[sdf_raymarch_loader] Loaded: createSdfObject, createSdfVolume, registerSdfHelper, makeSdfTexture + EXAMPLES + SDF_TEX_RECIPES + QUALITY_PRESETS. Call SdfRaymarchLoader.help() for API reference.');
}
