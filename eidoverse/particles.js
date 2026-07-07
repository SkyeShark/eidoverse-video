// GPU particle system for the eidoverse pipeline.
//
// WHY: there's a ~75-texture particle library at assets/particle_textures/, but
// no helper — so agents either build sparks/smoke/dust out of BoxGeometry (looks
// terrible) or hand-loop flat planes on the CPU (non-billboarded, breaks the
// GPU-only rule). This gives one call that makes a real, camera-facing, textured
// particle system whose motion runs entirely on the GPU (TSL positionNode — no
// per-frame CPU loop), modelled on the underwater-bubbles pattern.
//
//   const tex = await globalThis.loadImageTexture(globalThis.ASSETS.spark, { srgb: true });
//   globalThis.makeParticles({ scene, camera, preset: 'sparks', map: tex, origin: [0, 1, 0] });
//   // motion + billboarding update themselves every frame; you call nothing.
//
// opts:
//   scene, camera        (camera optional — only used for the billboard basis)
//   preset               sparks|embers|smoke|dust|snow|magic|stars|muzzle (default sparks)
//   map                  a loaded THREE.Texture from the particle library (recommended).
//                        Omit → a soft procedural dot (always works, less characterful).
//   origin   [x,y,z]     emitter centre (default [0,0,0])
//   count, size, color, area (number | [x,y,z] extents), speed, lifetime, gravity[3], grow, wobble, opacity, blending
//                        — each defaults from the preset; override any.
// returns { mesh, material, update(t) }  (update is auto-registered; calling it is optional).
(function () {
    'use strict';
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[particles] THREE global not present — skipping load'); return; }

    // preset → look + motion. color is 0xRRGGBB. blending 'additive' for
    // light-emitting stuff (sparks/fire/magic/glow), 'normal' for matter (smoke/
    // dust/snow). grow>0 expands over life (smoke), <0 shrinks (sparks).
    const PRESETS = {
        sparks: { count: 220, size: 0.06, lifetime: 0.9,  speed: 1, gravity: [0, -4.0, 0], area: 0.15, up: 2.2, spread: 1.6, color: 0xffd27f, blending: 'additive', grow: -0.8, wobble: 0.0, opacity: 1.0, twinkle: 0 },
        embers: { count: 140, size: 0.05, lifetime: 2.6,  speed: 1, gravity: [0,  0.5, 0], area: 0.4,  up: 0.7, spread: 0.5, color: 0xff7a30, blending: 'additive', grow: -0.5, wobble: 0.25, opacity: 1.0, twinkle: 0.4 },
        smoke:  { count: 70,  size: 0.7,  lifetime: 4.5,  speed: 1, gravity: [0,  0.45,0], area: 0.3,  up: 0.5, spread: 0.3, color: 0x8a8a8a, blending: 'normal',   grow:  1.8, wobble: 0.35, opacity: 0.35, twinkle: 0 },
        dust:   { count: 160, size: 0.04, lifetime: 6.0,  speed: 1, gravity: [0,  0.02,0], area: 3.0,  up: 0.05,spread: 0.2, color: 0xbcb2a0, blending: 'normal',   grow:  0.2, wobble: 0.5,  opacity: 0.4,  twinkle: 0.3 },
        snow:   { count: 320, size: 0.05, lifetime: 8.0,  speed: 1, gravity: [0, -0.7, 0], area: 6.0,  up: 0.0, spread: 0.1, color: 0xffffff, blending: 'normal',   grow:  0.0, wobble: 0.55, opacity: 0.9,  twinkle: 0 },
        magic:  { count: 180, size: 0.08, lifetime: 2.4,  speed: 1, gravity: [0,  0.6, 0], area: 0.5,  up: 0.4, spread: 0.6, color: 0x9b5cff, blending: 'additive', grow: -0.3, wobble: 0.4,  opacity: 1.0, twinkle: 0.7, swirl: 1.4 },
        stars:  { count: 420, size: 0.07, lifetime: 3.0,  speed: 1, gravity: [0,  0.0, 0], area: 22.0, up: 0.0, spread: 0.0, color: 0xffffff, blending: 'additive', grow:  0.0, wobble: 0.0,  opacity: 1.0, twinkle: 1.0 },
        muzzle: { count: 48,  size: 0.45, lifetime: 0.22, speed: 1, gravity: [0,  0.0, 0], area: 0.05, up: 0.2, spread: 2.4, color: 0xfff0c0, blending: 'additive', grow: -1.4, wobble: 0.0,  opacity: 1.0, twinkle: 0 },
        // fire: real flame shape — color-over-life (white→yellow→orange→red),
        // velocity convergence toward the axis (tapered candle profile),
        // asymmetric size curve (grows fast at base, tapers as it rises),
        // subtle per-particle sway (tongue textures must stay upright). Pair
        // with flame_05/flame_06 (vertical flame tongues — flame_01..04 are
        // wispy puffs that read as smoke); the
        // city builder's spawnFireParticles loads one automatically.
        fire:   { count: 150, size: 0.5,  lifetime: 0.55, speed: 1, gravity: [0,  0.5, 0], area: 0.10, up: 0.55, spread: 0.18, color: 0xffffff, blending: 'additive', grow: 0, wobble: 0.15, opacity: 1.0, twinkle: 0.25, flame: true, converge: 0.85, rotate: 0.35 },
    };

    function rand(a, b) { return a + Math.random() * (b - a); }

    globalThis.makeParticles = function makeParticles(opts) {
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('makeParticles');
        opts = opts || {};
        const scene = opts.scene || globalThis._scene || globalThis._s;
        const camera = opts.camera || globalThis._c || globalThis._camera;
        if (!scene) { console.warn('[particles] no scene (pass opts.scene or set globalThis._s)'); return null; }

        const base = PRESETS[opts.preset] || PRESETS.sparks;
        const P = Object.assign({}, base, opts);   // opts override preset
        const count = P.count | 0;
        const map = opts.map || null;
        // accept `origin` OR `position` — scenes reach for `position` first,
        // and a silently-ignored key strands every emitter at world (0,0,0)
        const origin = opts.origin || opts.position || [0, 0, 0];

        const {
            Fn, vec3, attribute, time, mod, fract, sin, cos, float, uniform,
            positionLocal, clamp, max, uv, texture, mix, smoothstep, vec2,
        } = THREE;

        // Per-instance buffers (computed once on the CPU at build time — this is
        // allowed; the PER-FRAME motion is all GPU). iEmit: spawn offset within
        // the emitter area; iVel: launch velocity; iSeed: (phase, wobbleAmt, sizeVar).
        // `area` accepts a scalar radius OR [x,y,z] per-axis extents; anything
        // non-numeric falls back to the preset and WARNS instead of NaN-ing
        // every particle position (a NaN area silently kills the whole emitter)
        let areaX, areaY, areaZ;
        if (Array.isArray(P.area)) {
            areaX = Number(P.area[0]) || 0;
            areaY = P.area.length > 1 ? (Number(P.area[1]) || 0) : areaX;
            areaZ = P.area.length > 2 ? (Number(P.area[2]) || 0) : areaX;
        } else if (Number.isFinite(Number(P.area))) {
            areaX = areaY = areaZ = Number(P.area);
        } else {
            console.warn(`[particles] invalid area ${JSON.stringify(P.area)} — expected number or [x,y,z]; using preset ${base.area}`);
            areaX = areaY = areaZ = base.area;
        }
        const emit = new Float32Array(count * 3);
        const vel = new Float32Array(count * 3);
        const seed = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            const th = rand(0, Math.PI * 2), ph = Math.acos(rand(-1, 1)), r = Math.cbrt(Math.random());
            emit[i * 3]     = Math.sin(ph) * Math.cos(th) * r * areaX;
            emit[i * 3 + 1] = Math.cos(ph) * r * 0.6 * areaY;
            emit[i * 3 + 2] = Math.sin(ph) * Math.sin(th) * r * areaZ;
            vel[i * 3]      = rand(-1, 1) * P.spread;
            vel[i * 3 + 1]  = P.up + rand(-0.2, 0.2) * P.spread;
            vel[i * 3 + 2]  = rand(-1, 1) * P.spread;
            seed[i * 3]     = Math.random();              // phase 0..1
            seed[i * 3 + 1] = rand(0.5, 1.5) * P.wobble;  // wobble amount
            seed[i * 3 + 2] = rand(0.7, 1.3);             // size variance
        }
        const geo = new THREE.PlaneGeometry(1, 1);
        geo.setAttribute('iEmit', new THREE.InstancedBufferAttribute(emit, 3));
        geo.setAttribute('iVel',  new THREE.InstancedBufferAttribute(vel, 3));
        geo.setAttribute('iSeed', new THREE.InstancedBufferAttribute(seed, 3));

        const blend = (P.blending === 'normal') ? THREE.NormalBlending : THREE.AdditiveBlending;
        const mat = new THREE.MeshBasicNodeMaterial({
            transparent: true, depthWrite: false, blending: blend, side: THREE.DoubleSide,
            toneMapped: P.blending !== 'additive',
        });
        // Keep the quads OUT of the G-buffer. The auto-enhance scene pass MRT
        // writes encoded normals + metalrough for GTAO/SSR; an alpha-blended
        // billboard smears garbage normals over its whole quad footprint and
        // GTAO renders that as hard dark rectangles behind smoke. Material
        // mrtNode MERGES per-channel over the pass MRT (color stays default),
        // and vec4(0) has alpha 0, which preserves the destination under both
        // normal and additive blending — visible in color, invisible to AO.
        if (THREE.mrt && THREE.vec4) {
            mat.mrtNode = THREE.mrt({
                normal: THREE.vec4(0),
                metalrough: THREE.vec4(0),
            });
        }

        // Uniforms (camRight/camUp updated each frame for billboarding).
        const uOrigin = uniform(new THREE.Vector3(origin[0], origin[1], origin[2]));
        const uGravity = uniform(new THREE.Vector3(P.gravity[0], P.gravity[1], P.gravity[2]));
        const uCamRight = uniform(new THREE.Vector3(1, 0, 0));
        const uCamUp = uniform(new THREE.Vector3(0, 1, 0));
        const uSize = uniform(float(P.size));
        const uGrow = uniform(float(P.grow || 0));
        const uLife = uniform(float(P.lifetime));
        const uCyc = uniform(float((P.speed || 1) / P.lifetime));   // cycles/sec
        const uSwirl = uniform(float(P.swirl || 0));
        const uOpacity = uniform(float(P.opacity != null ? P.opacity : 1));
        const uTwinkle = uniform(float(P.twinkle || 0));
        const col = new THREE.Color(P.color);
        const uColor = uniform(new THREE.Vector3(col.r, col.g, col.b));

        const tLocalOf = (phase) => fract(time.mul(uCyc).add(phase));   // 0..1 per particle

        mat.positionNode = Fn(() => {
            const e = attribute('iEmit'), v = attribute('iVel'), s = attribute('iSeed');
            const phase = s.x, wob = s.y, sizeVar = s.z;
            const tL = tLocalOf(phase).toVar();
            const age = tL.mul(uLife).toVar();
            // emit + ballistic + drift (+ optional swirl for magic)
            const grav = uGravity.mul(float(0.5).mul(age).mul(age));
            const a2 = time.mul(1.2).add(phase.mul(6.2832));
            const drift = vec3(sin(a2).mul(wob), cos(a2.mul(0.7)).mul(wob).mul(0.4), cos(a2).mul(wob));
            const ang = age.mul(uSwirl);
            const swirl = vec3(cos(ang).mul(uSwirl).mul(0.15), float(0), sin(ang).mul(uSwirl).mul(0.15));
            const off = e.add(v.mul(age)).add(grav).add(drift).add(swirl).toVar();
            // flame: converge horizontal offset toward the axis with age —
            // wide at the base, tapering to a tip (candle profile). Built as
            // an explicit vec3 — swizzle-assign on a toVar broke the graph.
            let centerOff = off;
            if (P.flame || P.converge) {
                const conv = float(1).sub(tL.mul(float(P.converge != null ? P.converge : 0.85))).toVar();
                centerOff = vec3(off.x.mul(conv), off.y, off.z.mul(conv));
            }
            const center = uOrigin.add(centerOff).toVar();
            // billboard the quad to the camera; grow/shrink over life
            const szBase = uSize.mul(sizeVar).toVar();
            if (P.flame) {
                // asymmetric: pop in fast at the base, taper slowly to the tip
                szBase.mulAssign(smoothstep(float(0), float(0.12), tL).sqrt()
                    .mul(float(1).sub(tL.mul(0.55))));
            }
            const sz = max(float(0.005), szBase.mul(float(1).add(uGrow.mul(tL)))).toVar();
            let lx = positionLocal.x, ly = positionLocal.y;
            if (P.rotate) {
                // per-particle spin: random initial angle + signed angular velocity
                const rAng = phase.mul(6.2832)
                    .add(time.mul(float(P.rotate)).mul(phase.sub(0.5).mul(2)));
                const ca = cos(rAng).toVar(), sa = sin(rAng).toVar();
                const rx = positionLocal.x.mul(ca).sub(positionLocal.y.mul(sa)).toVar();
                const ry = positionLocal.x.mul(sa).add(positionLocal.y.mul(ca)).toVar();
                lx = rx; ly = ry;
            }
            const corner = uCamRight.mul(lx.mul(sz)).add(uCamUp.mul(ly.mul(sz)));
            return center.add(corner);
        })();

        const fadeOf = (phase) => {
            const tL = tLocalOf(phase);
            const fin = clamp(tL.div(0.12), 0, 1);
            const fout = clamp(float(1).sub(tL).div(0.35), 0, 1);
            return fin.mul(fout);
        };

        mat.colorNode = Fn(() => {
            let c = uColor;
            if (P.flame) {
                // color-over-life: white-hot base -> yellow -> orange -> red tip
                const tL = tLocalOf(attribute('iSeed').x).toVar();
                const ramp = mix(vec3(1.0, 0.97, 0.88), vec3(1.0, 0.78, 0.25), smoothstep(float(0.0), float(0.3), tL)).toVar();
                ramp.assign(mix(ramp, vec3(1.0, 0.42, 0.10), smoothstep(float(0.3), float(0.65), tL)));
                ramp.assign(mix(ramp, vec3(0.55, 0.12, 0.04), smoothstep(float(0.65), float(1.0), tL)));
                c = ramp.mul(uColor);
            }
            if (map) c = c.mul(texture(map).sample(uv()).rgb);
            return c;
        })();

        mat.opacityNode = Fn(() => {
            const phase = attribute('iSeed').x;
            let a = uOpacity.mul(fadeOf(phase));
            // twinkle: flicker brightness for embers/magic/stars
            const tw = float(0.5).add(sin(time.mul(7).add(phase.mul(40))).mul(0.5));
            a = a.mul(mix(float(1), tw, uTwinkle));
            if (map) {
                a = a.mul(texture(map).sample(uv()).a);
                // rim fade: sprite textures whose alpha doesn't reach zero at
                // the border print the QUAD as a hard square edge (worst on
                // additive fire). A thin smooth fade at the quad rim kills the
                // square outline without touching the sprite's interior.
                const b = uv().sub(0.5).abs();
                a = a.mul(smoothstep(float(0.5), float(0.44), max(b.x, b.y)));
            } else {
                // soft procedural dot — raw textureless quads read as squares
                const dC = uv().sub(0.5).length();
                a = a.mul(smoothstep(float(0.5), float(0.12), dC));
            }
            // Kill the sub-threshold alpha tail EXACTLY to zero. Invisible on
            // its own, the ~0.01-alpha tail across the quad becomes a flat
            // VISIBLE RECTANGLE when a depth-keyed post pass (depth_fog etc.)
            // composites fog over no-depth-write sprites.
            return a.sub(0.004).max(0.0);
        })();

        const mesh = new THREE.InstancedMesh(geo, mat, count);
        mesh.frustumCulled = false;
        mesh.name = opts.name || `particles_${opts.preset || 'sparks'}`;
        mesh.userData.noSupportCheck = true;     // particles fly — not a placement floater
        mesh.userData.noClippingCheck = true;    // they overlap each other + the scene by design
        mesh.userData.noCameraCollide = true;
        scene.add(mesh);

        const _r = new THREE.Vector3(), _u = new THREE.Vector3();
        const update = function () {
            const cam = opts.camera || globalThis._c || globalThis._camera;
            if (!cam) return;
            cam.updateMatrixWorld();
            _r.setFromMatrixColumn(cam.matrixWorld, 0).normalize();
            _u.setFromMatrixColumn(cam.matrixWorld, 1).normalize();
            uCamRight.value.copy(_r);
            uCamUp.value.copy(_u);
        };
        update();
        // Auto-register so billboarding tracks the camera even if the scene
        // never calls update() — the render loop drains _autoParticleSystems.
        (globalThis._autoParticleSystems || (globalThis._autoParticleSystems = [])).push(update);

        return { mesh, material: mat, update, uniforms: { size: uSize, opacity: uOpacity, color: uColor, origin: uOrigin } };
    };

    console.log('[particles] makeParticles ready — presets: ' + Object.keys(PRESETS).join(', '));
})();
