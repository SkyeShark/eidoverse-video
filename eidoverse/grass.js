// Procedural wind GRASS for the eidoverse pipeline.
//
// WHY: flat PlaneGeometry ground is the #1 tech-demo tell; a field of real
// tapered blades with a height-gradient colour and GPU wind sway sells an
// outdoor scene instantly. There was no helper for it, so agents left ground
// bare or hand-rolled blades. This is ONE call, and the wind animates itself
// on the GPU (TSL positionNode — no per-frame CPU loop), exactly like
// makeParticles.
//
//   globalThis.makeGrass({ scene, width: 40, depth: 40 });        // simplest
//   // wind animates itself every frame; you call nothing.
//
// Tune everything the brief needs:
//   globalThis.makeGrass({
//       scene, width: 60, depth: 40, center: [0, -15],
//       color: 0x2f5212, colorTip: 0xb6d45a,    // base → tip gradient (dry? autumn? alien?)
//       bladeHeight: 0.7, spacing: 0.18, perCell: 5,   // taller + denser = lush meadow
//       wind: 0.28, windSpeed: 2.0,              // breezy; wind: 0 = dead-still grass
//   });
//
// opts:
//   scene                 (or globalThis._s)
//   width, depth          field size in METRES (default 30 × 30). `size` = square shortcut.
//   center  [x,z]         field centre (default [0,0])
//   y                     ground height the blades grow from (default 0)
//   heightFn (x,z)=>y     OPTIONAL — drape over uneven terrain (pass terrain.heightAt)
//   spacing               metres between tufts (default 0.25; SMALLER = denser → heavier)
//   perCell               blades per tuft (default 4; more = lusher, clumpier)
//   bladeHeight           metres (default 0.5; each blade randomised 0.6–1.5×)
//   bladeWidth            metres (default 0.03)
//   color, colorTip       base + tip colours 0xRRGGBB (default field greens). The tip
//                         colour shows at the blade ends — lift it for sun-kissed grass.
//   wind                  sway AMPLITUDE (default 0.18; 0 = no wind). 0.1 calm, 0.3 breezy.
//   windSpeed             wind-clock speed (default 1.6)
//   lean                  blade lean fraction (default 0.5; 0 = bolt-upright)
//   clipFn (x,z)=>bool    OPTIONAL — return true to SKIP a blade (carve a path / keep-out)
//   parent                Object3D to add to (default scene)
//
// returns { mesh, material, update, uniforms: { wind }, bladeCount }
//   (update is auto-registered; calling it yourself is optional. uniforms.wind
//    is the live wind clock if you ever want to drive it from a beat envelope.)
(function () {
    'use strict';
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[grass] THREE global not present — skipping load'); return; }
    const { positionLocal, attribute, vec2, vec3, float, sin, texture, uniform } = THREE;

    // Shared scrolling value-noise "gust" field — built once, reused by every
    // grass field (gusts ripple across the blades on top of the base sway).
    let _gust = null;
    function gustTex() {
        if (_gust) return _gust;
        const n = 256, d = new Uint8Array(n * n * 4);
        const val = (x, y) => { const h = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453; return h - Math.floor(h); };
        const sm = (x, y) => {
            const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
            const a = val(xi, yi), b = val(xi + 1, yi), c = val(xi, yi + 1), e = val(xi + 1, yi + 1);
            const ux = xf * xf * (3 - 2 * xf), uy = yf * yf * (3 - 2 * yf);
            return a * (1 - ux) * (1 - uy) + b * ux * (1 - uy) + c * (1 - ux) * uy + e * ux * uy;
        };
        for (let i = 0; i < n * n; i++) {
            const x = i % n, y = (i / n) | 0; let v = 0, amp = 0.6, f = 0.05;
            for (let o = 0; o < 4; o++) { v += sm(x * f, y * f) * amp; amp *= 0.5; f *= 2; }
            const c = Math.max(0, Math.min(255, v * 255)) | 0;
            d[i * 4] = c; d[i * 4 + 1] = c; d[i * 4 + 2] = c; d[i * 4 + 3] = 255;
        }
        const t = new THREE.DataTexture(d, n, n, THREE.RGBAFormat);
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearFilter; t.needsUpdate = true;
        _gust = t; return t;
    }

    globalThis.makeGrass = function makeGrass(opts = {}) {
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('makeGrass');
        const scene = opts.scene || globalThis._s || globalThis._scene;
        if (!scene) { console.warn('[grass] no scene (pass opts.scene or set globalThis._s)'); return null; }

        const W = opts.width ?? opts.size ?? 30;
        const D = opts.depth ?? opts.size ?? 30;
        const cx = (opts.center && opts.center[0]) || 0;
        const cz = (opts.center && opts.center[1]) || 0;
        const baseY = opts.y ?? 0;
        const heightFn = typeof opts.heightFn === 'function' ? opts.heightFn : null;
        const spacing = Math.max(0.04, opts.spacing ?? 0.25);
        const perCell = Math.max(1, opts.perCell ?? 4);
        const bH = opts.bladeHeight ?? 0.5;
        const bW = opts.bladeWidth ?? 0.03;
        const leanAmt = opts.lean ?? 0.5;
        const windAmp = opts.wind ?? 0.18;
        const windSpeed = opts.windSpeed ?? 1.6;
        const clipFn = typeof opts.clipFn === 'function' ? opts.clipFn : null;
        const baseC = new THREE.Color(opts.color ?? 0x3c5a18);
        const tipC = new THREE.Color(opts.colorTip ?? 0xa9c95a);
        // RIM FADE — dissolve the field's outer band into the haze so the
        // boundary never reads as a cut line: blades near the rim blend
        // toward the fog/horizon colour AND thin out. Defaults ON when the
        // scene has fog (fadeColor = fog colour); disable with fade: false.
        const fadeOn = opts.fade !== false;
        const fadeC = new THREE.Color(opts.fadeColor ?? (scene.fog ? scene.fog.color : 0xbfb49a));
        const fadeStart = opts.fadeStart ?? 0.62;   // fraction of the half-extent
        const fadeEnd = opts.fadeEnd ?? 0.98;

        // 5-vertex tapered blade (James-Smyth technique): two width pairs + a tip,
        // each blade on a jittered grid of tufts so coverage reads continuous
        // (no isolated-blade "chunks"). vertex colour = base→tip height gradient;
        // aH = normalised height (tip sways most via aH²); aPh = per-blade phase.
        const pos = [], col = [], aH = [], aPh = [], idx = []; let vb = 0;
        const up = new THREE.Vector3(0, 1, 0), ref = new THREE.Vector3(1, 0, 0);
        const t1 = new THREE.Vector3(), t2 = new THREE.Vector3(), side = new THREE.Vector3(), fwd = new THREE.Vector3(), P = new THREE.Vector3(), V = new THREE.Vector3(), tmp = new THREE.Color();
        t1.crossVectors(up, ref).normalize(); t2.crossVectors(up, t1);   // up = +Y (ground grass)
        const nc = Math.ceil(W / spacing), nr = Math.ceil(D / spacing);
        for (let ic = 0; ic < nc; ic++) for (let ir = 0; ir < nr; ir++) {
            const ccx = cx - W / 2 + (ic + 0.5) * spacing, ccz = cz - D / 2 + (ir + 0.5) * spacing;
            for (let k = 0; k < perCell; k++) {
                const x = ccx + (Math.random() - 0.5) * spacing * 1.15, z = ccz + (Math.random() - 0.5) * spacing * 1.15;
                if (clipFn && clipFn(x, z)) continue;
                // Rim factor 0 (interior) → 1 (edge): thin the density and
                // haze-blend the colour so the boundary disperses.
                let rim = 0;
                if (fadeOn) {
                    const rx = Math.abs(x - cx) / (W / 2), rz = Math.abs(z - cz) / (D / 2);
                    rim = Math.max(0, Math.min(1, (Math.max(rx, rz) - fadeStart) / Math.max(1e-6, fadeEnd - fadeStart)));
                    if (Math.random() < rim * rim) continue;   // density dissolves outward
                }
                const y = heightFn ? heightFn(x, z) : baseY;
                const h = bH * (0.6 + Math.random() * 0.9) * (1 - rim * 0.45), w = bW * (0.8 + Math.random() * 0.6);
                const roll = Math.random() * 6.283, lean = (Math.random() - 0.5) * leanAmt * h, ph = Math.random() * 6.283;
                const cr = Math.cos(roll), sr = Math.sin(roll);
                side.copy(t1).multiplyScalar(cr).addScaledVector(t2, sr);
                fwd.copy(t1).multiplyScalar(-sr).addScaledVector(t2, cr);
                const vi = [];
                for (const hw of [[0, 1], [0.5, 0.62], [1, 0]]) {
                    const hl = hw[0], wf = hw[1];
                    tmp.copy(baseC).lerp(tipC, hl);
                    if (rim > 0) tmp.lerp(fadeC, rim * 0.85);   // haze-blend at the rim
                    const lx = lean * hl * hl;
                    P.set(x, y, z).addScaledVector(up, hl * h).addScaledVector(fwd, lx);
                    if (wf > 0) {
                        V.copy(P).addScaledVector(side, w * wf); pos.push(V.x, V.y, V.z); col.push(tmp.r, tmp.g, tmp.b); aH.push(hl); aPh.push(ph); vi.push(vb++);
                        V.copy(P).addScaledVector(side, -w * wf); pos.push(V.x, V.y, V.z); col.push(tmp.r, tmp.g, tmp.b); aH.push(hl); aPh.push(ph); vi.push(vb++);
                    } else { pos.push(P.x, P.y, P.z); col.push(tmp.r, tmp.g, tmp.b); aH.push(hl); aPh.push(ph); vi.push(vb++); }
                }
                idx.push(vi[0], vi[1], vi[2], vi[1], vi[3], vi[2], vi[2], vi[3], vi[4]);
            }
        }

        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
        g.setAttribute('aH', new THREE.Float32BufferAttribute(aH, 1));
        g.setAttribute('aPh', new THREE.Float32BufferAttribute(aPh, 1));
        g.setIndex(idx); g.computeVertexNormals();

        const mat = new THREE.MeshStandardNodeMaterial({ vertexColors: true, roughness: 1, metalness: 0, side: THREE.DoubleSide });
        const windU = uniform(0);   // wind clock; advanced per frame by the auto-updater
        if (windAmp > 0) {
            const H = attribute('aH'), PH = attribute('aPh'), h2 = H.mul(H);
            const px = positionLocal.x, pz = positionLocal.z;
            // base sway (sine in world-X so neighbours don't move in lockstep)
            const sway = sin(windU.mul(1.0).add(px.mul(0.45)).add(PH));
            // scrolling gust field (clumps of wind ripple across the meadow)
            const cuv = vec2(px.mul(0.012).add(windU.mul(0.05)), pz.mul(0.012).add(windU.mul(0.085)));
            const gust = texture(gustTex(), cuv).r.sub(0.5);
            const amt = sway.mul(windAmp).add(gust.mul(windAmp * 2.4)).mul(h2);   // ×aH² → tip moves, base anchored
            mat.positionNode = positionLocal.add(vec3(amt, float(0), amt.mul(0.4)));
        }
        // Tip translucency — grass blades pass light near the tip; a small
        // vertex-colour emissive term scaled by height² reads as backlight
        // without real SSS. opts.backlight (default 0.22), 0 disables.
        const backlight = opts.backlight ?? 0.22;
        if (backlight > 0) {
            const HB = attribute('aH');
            mat.emissiveNode = attribute('color').mul(HB.mul(HB)).mul(float(backlight));
        }

        const mesh = new THREE.Mesh(g, mat);
        mesh.userData.noSupportCheck = true; mesh.userData.noClippingCheck = true; mesh.userData.noCameraCollide = true;
        mesh.frustumCulled = false;   // a field's bbox often straddles the frustum edge; never pop out
        (opts.parent || scene).add(mesh);

        const update = (t) => { windU.value = (t || 0) * windSpeed; };
        update(globalThis._sceneTime || 0);
        // Auto-register so the wind animates even if the scene never calls update()
        // — the render loop drains _autoParticleSystems(t) every frame.
        (globalThis._autoParticleSystems || (globalThis._autoParticleSystems = [])).push(update);

        const bladeCount = (aH.length / 5) | 0;   // 5 verts per blade
        console.log(`[grass] field ${W}×${D}m, ${bladeCount} blades, wind ${windAmp}`);
        return { mesh, material: mat, update, uniforms: { wind: windU }, bladeCount };
    };

    console.log('[grass] makeGrass ready — GPU wind grass (width/depth/density/height/color/wind adjustable)');
})();
