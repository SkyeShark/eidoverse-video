// makeParticleMorph — GPU volumetric particle cloud that MORPHS between
// point-set targets (mesh dissolve → reform into another shape → reform back).
//
// WHY: "dissolve a body into a swirling volumetric cloud and reassemble it
// into a different shape" (teleports, summons, shape-forms, a neuron-map) is a
// recurring motif with no helper — agents would hand-roll CPU point loops
// (breaks the GPU-only rule) or fake it with sprites. This gives N GPU
// particles whose position is mix(targetA, targetB) + curl-noise turbulence,
// all on the GPU (TSL positionNode — no per-frame CPU loop), billboarded like
// makeParticles. The scene drives a 0..1 morph factor from its own timeline.
//
//   const morph = globalThis.makeParticleMorph({
//       scene, camera, count: 60000,
//       targets: [ ParticleMorph.fromMesh(vrm.scene, 60000),
//                  ParticleMorph.neuronGraph({ count: 60000 }),
//                  ParticleMorph.fromMesh(vrm.scene, 60000) ],
//       color: 0x66ccff, size: 0.012, blending: 'additive',
//       curl: { scale: 1.4, strength: 0.5 },
//   });
//   // per frame, from the scene timeline:
//   morph.morph(0, 1, m /*0..1*/, turbulence /*0..1*/);
//
// Target generators (each returns Float32Array length count*3):
//   ParticleMorph.fromMesh(object3D, count)        — surface/vertex sample (skinned-aware)
//   ParticleMorph.neuronGraph({ count, nodes, ... })— procedural node+edge cloud
//   ParticleMorph.fromPoints(arr, count)           — resample any [x,y,z][] / Float32Array
//   ParticleMorph.fromText(str, count, {width,ascii,...})— particles in the SHAPE OF TEXT (word/logo/ASCII art)
(function () {
    'use strict';
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[particle_morph] THREE global not present — skipping'); return; }

    function rand(a, b) { return a + Math.random() * (b - a); }

    // ── Resample an arbitrary point list to EXACTLY n points (count*3 floats).
    function resampleToN(src, n) {
        // src: Float32Array (m*3) or array of [x,y,z]
        let flat;
        if (src instanceof Float32Array) flat = src;
        else { flat = new Float32Array(src.length * 3); for (let i = 0; i < src.length; i++) { flat[i*3]=src[i][0]; flat[i*3+1]=src[i][1]; flat[i*3+2]=src[i][2]; } }
        const m = (flat.length / 3) | 0;
        const out = new Float32Array(n * 3);
        if (m === 0) return out;
        for (let i = 0; i < n; i++) {
            // pick a source point (cycle + tiny jitter when upsampling)
            const j = (m >= n) ? Math.floor(i * m / n) : (i % m);
            const jit = (m < n) ? 0.01 : 0.0;
            out[i*3]   = flat[j*3]   + rand(-jit, jit);
            out[i*3+1] = flat[j*3+1] + rand(-jit, jit);
            out[i*3+2] = flat[j*3+2] + rand(-jit, jit);
        }
        return out;
    }

    const _v = new THREE.Vector3();

    globalThis.ParticleMorph = {
        fromPoints(arr, count) { return resampleToN(arr, count); },

        // Sample world-space points off a mesh/VRM. Skinned meshes are sampled
        // in their CURRENT pose via applyBoneTransform, so the cloud matches
        // exactly what's on screen (dissolve/reform line up).
        fromMesh(object3D, count) {
            const pts = [];
            object3D.updateMatrixWorld(true);
            object3D.traverse((o) => {
                if (!o.isMesh || !o.geometry || !o.geometry.attributes.position) return;
                const pos = o.geometry.attributes.position;
                const skinned = o.isSkinnedMesh && typeof o.applyBoneTransform === 'function';
                const vcount = pos.count;
                // cap per-mesh samples so a huge mesh doesn't dominate
                const step = Math.max(1, Math.floor(vcount / 8000));
                for (let i = 0; i < vcount; i += step) {
                    _v.fromBufferAttribute(pos, i);
                    if (skinned) o.applyBoneTransform(i, _v);       // → current posed local
                    _v.applyMatrix4(o.matrixWorld);                 // → world
                    pts.push([_v.x, _v.y, _v.z]);
                }
            });
            if (!pts.length) { console.warn('[particle_morph] fromMesh: no vertices found'); }
            return resampleToN(pts, count);
        },

        // Particles in the SHAPE OF TEXT. Rasterizes the string to a canvas,
        // samples the filled glyph pixels, and maps them into a centered 3D
        // point cloud — so a cloud can dissolve and REFORM into a word/logo.
        //   ParticleMorph.fromText('HELLO', 40000, { width: 5 })
        //   ParticleMorph.fromText(asciiArtString, 40000, { ascii: true })  // ASCII art → particles
        // opts: width (world width, default 4) · depth (z-thickness, default 0)
        //       fontSize (px, default 160) · fontFamily · ascii (monospace +
        //       preserve whitespace, for multi-line ASCII art) · pixelStride
        //       (sampling density, default 2) · weight ('bold'|'normal').
        fromText(text, count, opts = {}) {
            const ascii = !!opts.ascii;
            const fontPx = opts.fontSize || (ascii ? 28 : 160);
            const family = opts.fontFamily || (ascii ? 'monospace' : 'Arial, sans-serif');
            const font = `${ascii ? '' : (opts.weight || 'bold') + ' '}${fontPx}px ${family}`;
            const lines = String(text).split('\n');
            const lineH = ascii ? fontPx * 1.05 : fontPx * 1.18;
            const doc = globalThis.document;
            if (!doc || !doc.createElement) { console.warn('[particle_morph] fromText: no canvas (document) available'); return new Float32Array(count * 3); }
            const cv = doc.createElement('canvas');
            let ctx = cv.getContext('2d'); ctx.font = font;
            let maxW = 1;
            for (const ln of lines) maxW = Math.max(maxW, ctx.measureText(ln).width || 1);
            const pad = Math.ceil(fontPx * 0.2);
            cv.width = Math.ceil(maxW) + pad * 2;
            cv.height = Math.ceil(lineH * lines.length) + pad * 2;
            ctx = cv.getContext('2d');
            ctx.font = font; ctx.textBaseline = 'top'; ctx.fillStyle = '#ffffff';
            lines.forEach((ln, i) => ctx.fillText(ln, pad, pad + i * lineH));
            const W = cv.width, H = cv.height;
            const img = ctx.getImageData(0, 0, W, H).data;
            const stride = Math.max(1, opts.pixelStride || 2);
            const filled = [];
            for (let y = 0; y < H; y += stride)
                for (let x = 0; x < W; x += stride)
                    if (img[(y * W + x) * 4 + 3] > 128) filled.push([x, y]);
            if (!filled.length) { console.warn('[particle_morph] fromText: no glyph pixels (font/text issue)'); return new Float32Array(count * 3); }
            const targetW = opts.width != null ? opts.width : 4;
            const scale = targetW / W;
            const cx = W / 2, cy = H / 2;
            const dz = opts.depth || 0;
            const pts = filled.map(([x, y]) => [
                (x - cx) * scale,
                -(y - cy) * scale,        // flip Y (canvas down → world up)
                dz ? rand(-dz / 2, dz / 2) : 0,
            ]);
            return resampleToN(pts, count);
        },

        // Procedural "neuron map" cloud: nodes scattered in a disc/slab, linked
        // to nearest neighbours; points are distributed across node clusters
        // (dense glowing blobs) + along the edges (thin strands).
        neuronGraph(opts = {}) {
            const count = opts.count | 0 || 40000;
            const nodes = opts.nodes | 0 || 90;
            const rx = opts.rx != null ? opts.rx : 2.6;
            const ry = opts.ry != null ? opts.ry : 1.6;
            const rz = opts.rz != null ? opts.rz : 1.2;
            const k = opts.k | 0 || 3;            // edges per node (nearest)
            const nodeFrac = opts.nodeFrac != null ? opts.nodeFrac : 0.45; // pts in blobs vs strands
            // node positions (layered slab → reads as a graph, not a ball)
            const N = [];
            for (let i = 0; i < nodes; i++) {
                N.push([rand(-rx, rx), rand(-ry, ry), rand(-rz, rz) * (0.4 + Math.random() * 0.6)]);
            }
            // edges: each node → k nearest
            const E = [];
            for (let i = 0; i < nodes; i++) {
                const d = [];
                for (let j = 0; j < nodes; j++) if (j !== i) {
                    const dx=N[i][0]-N[j][0], dy=N[i][1]-N[j][1], dz=N[i][2]-N[j][2];
                    d.push([dx*dx+dy*dy+dz*dz, j]);
                }
                d.sort((a, b) => a[0] - b[0]);
                for (let e = 0; e < k && e < d.length; e++) { const j = d[e][1]; if (i < j) E.push([i, j]); }
            }
            const out = new Float32Array(count * 3);
            const nodePts = Math.floor(count * nodeFrac);
            for (let i = 0; i < count; i++) {
                let x, y, z;
                if (i < nodePts) {                       // glowing node blob
                    const n = N[i % nodes]; const s = 0.06;
                    x = n[0] + rand(-s, s); y = n[1] + rand(-s, s); z = n[2] + rand(-s, s);
                } else if (E.length) {                   // strand point along an edge
                    const e = E[(i) % E.length]; const a = N[e[0]], b = N[e[1]]; const t = Math.random(); const s = 0.015;
                    x = a[0] + (b[0]-a[0])*t + rand(-s, s);
                    y = a[1] + (b[1]-a[1])*t + rand(-s, s);
                    z = a[2] + (b[2]-a[2])*t + rand(-s, s);
                } else { const n = N[i % nodes]; x = n[0]; y = n[1]; z = n[2]; }
                out[i*3] = x; out[i*3+1] = y; out[i*3+2] = z;
            }
            return out;
        },

        // Classic textbook DEEP NEURAL NETWORK diagram: vertical columns of
        // node circles (one column per layer), fully connected by straight
        // edges between adjacent layers — laid in the XY plane (faces camera),
        // tiny Z jitter for volume. The look from ML papers.
        neuralNet(opts = {}) {
            const count = opts.count | 0 || 40000;
            const layers = opts.layers || [5, 8, 8, 8, 6];
            const width = opts.width != null ? opts.width : 4.6;   // total X span
            const height = opts.height != null ? opts.height : 2.8; // max column height
            const nodeR = opts.nodeR != null ? opts.nodeR : 0.075; // node disc radius
            const depthJit = opts.depthJit != null ? opts.depthJit : 0.05;
            const nodeFrac = opts.nodeFrac != null ? opts.nodeFrac : 0.34;
            const L = layers.length;
            const cols = [];
            for (let li = 0; li < L; li++) {
                const x = (L === 1) ? 0 : (-width / 2 + (li / (L - 1)) * width);
                const n = layers[li]; const col = [];
                // shorter columns for the smaller (input/output) layers read better
                const h = height * (0.45 + 0.55 * (n / Math.max(...layers)));
                for (let ni = 0; ni < n; ni++) {
                    const y = (n === 1) ? 0 : (-h / 2 + (ni / (n - 1)) * h);
                    col.push([x, y, 0]);
                }
                cols.push(col);
            }
            const edges = [];
            for (let li = 0; li < L - 1; li++)
                for (const a of cols[li]) for (const b of cols[li + 1]) edges.push([a, b]);
            const flat = []; for (const c of cols) for (const nd of c) flat.push(nd);
            const out = new Float32Array(count * 3);
            const nodePts = Math.floor(count * nodeFrac);
            for (let i = 0; i < count; i++) {
                let x, y, z;
                if (i < nodePts) {                       // filled node disc (XY)
                    const nd = flat[i % flat.length];
                    const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * nodeR;
                    x = nd[0] + Math.cos(a) * r; y = nd[1] + Math.sin(a) * r; z = nd[2] + rand(-depthJit, depthJit);
                } else if (edges.length) {               // point along a connection line
                    const e = edges[i % edges.length]; const t = Math.random(); const s = 0.006;
                    x = e[0][0] + (e[1][0]-e[0][0])*t + rand(-s, s);
                    y = e[0][1] + (e[1][1]-e[0][1])*t + rand(-s, s);
                    z = rand(-depthJit, depthJit);
                } else { const nd = flat[i % flat.length]; x = nd[0]; y = nd[1]; z = nd[2]; }
                out[i*3] = x; out[i*3+1] = y; out[i*3+2] = z;
            }
            return out;
        },
    };

    globalThis.makeParticleMorph = function makeParticleMorph(opts) {
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('particle_morph');
        opts = opts || {};
        const scene = opts.scene || globalThis._scene || globalThis._s;
        if (!scene) { console.warn('[particle_morph] no scene'); return null; }
        const count = (opts.count | 0) || 40000;
        const map = opts.map || null;
        const curl = opts.curl || {};
        const targets = (opts.targets || []).map((t) => resampleToN(t, count));
        if (targets.length < 2) { console.warn('[particle_morph] need >=2 targets'); }

        const {
            Fn, vec3, attribute, time, fract, sin, cos, float, uniform,
            positionLocal, clamp, max, uv, texture, mix, smoothstep, length, abs,
        } = THREE;

        // Per-instance: iFrom / iTo are the two ACTIVE morph targets (rewritten
        // on the CPU only when the morph segment changes — not per frame).
        const iFrom = new Float32Array(count * 3);
        const iTo = new Float32Array(count * 3);
        const seed = new Float32Array(count * 3);
        if (targets[0]) iFrom.set(targets[0]);
        if (targets[1]) iTo.set(targets[1]);
        for (let i = 0; i < count; i++) {
            seed[i*3] = Math.random();               // phase 0..1
            seed[i*3+1] = rand(0.7, 1.4);            // size variance
            seed[i*3+2] = rand(0.6, 1.6);            // per-particle turbulence scale
        }

        const geo = new THREE.PlaneGeometry(1, 1);
        const aFrom = new THREE.InstancedBufferAttribute(iFrom, 3);
        const aTo = new THREE.InstancedBufferAttribute(iTo, 3);
        aFrom.setUsage(THREE.DynamicDrawUsage); aTo.setUsage(THREE.DynamicDrawUsage);
        geo.setAttribute('iFrom', aFrom);
        geo.setAttribute('iTo', aTo);
        geo.setAttribute('iSeed', new THREE.InstancedBufferAttribute(seed, 3));

        const blend = (opts.blending === 'normal') ? THREE.NormalBlending : THREE.AdditiveBlending;
        const mat = new THREE.MeshBasicNodeMaterial({
            transparent: true, depthWrite: false, blending: blend, side: THREE.DoubleSide,
            toneMapped: opts.blending === 'normal',
        });

        const uMorph = uniform(float(0));        // 0..1 between iFrom/iTo
        const uTurb = uniform(float(0));         // 0..1 turbulence amount
        const uSpin = uniform(float(0));         // Y-rotation of the whole cloud (radians)
        const uVortex = uniform(float(0));       // spiral/vortex swirl during the transition (radians, peaks mid)
        const uCurlScale = uniform(float(curl.scale != null ? curl.scale : 1.3));
        const uCurlStrength = uniform(float(curl.strength != null ? curl.strength : 0.5));
        const uSize = uniform(float(opts.size != null ? opts.size : 0.014));
        const uOpacity = uniform(float(opts.opacity != null ? opts.opacity : 1));
        const uCamRight = uniform(new THREE.Vector3(1, 0, 0));
        const uCamUp = uniform(new THREE.Vector3(0, 1, 0));
        const col = new THREE.Color(opts.color != null ? opts.color : 0x66ccff);
        const uColor = uniform(new THREE.Vector3(col.r, col.g, col.b));
        const col2 = new THREE.Color(opts.color2 != null ? opts.color2 : (opts.color != null ? opts.color : 0xff66cc));
        const uColor2 = uniform(new THREE.Vector3(col2.r, col2.g, col2.b));

        // Cheap divergence-light analytic "curl": sin/cos cross of position.
        // Peaks mid-morph (env = sin(pi*m)) so the cloud is loosest in transit
        // and snaps crisp at both ends.
        mat.positionNode = Fn(() => {
            const from = attribute('iFrom');
            const to = attribute('iTo');
            const s = attribute('iSeed');
            const me = smoothstep(float(0), float(1), uMorph);
            const base0 = mix(from, to, me);
            // spin the cloud around Y (so it can track a spinning body); the
            // billboard corner is added AFTER in world space, so quads still
            // face the camera regardless of spin.
            const ca = cos(uSpin), sa = sin(uSpin);
            const base = vec3(base0.x.mul(ca).add(base0.z.mul(sa)), base0.y, base0.z.mul(ca).sub(base0.x.mul(sa)));
            // vortex: per-particle swirl around Y that peaks mid-transition and
            // unwinds to 0 at both ends → particles spiral INTO place (a distinct
            // reassembly vs the symmetric curl scatter). Per-particle amount via
            // seed so it winds, not rigidly rotates.
            const vEnv = uVortex.mul(sin(uMorph.mul(3.14159265))).mul(s.x.mul(0.8).add(0.6));
            const cv = cos(vEnv), sv = sin(vEnv);
            const baseV = vec3(base.x.mul(cv).add(base.z.mul(sv)), base.y, base.z.mul(cv).sub(base.x.mul(sv)));
            const env = uTurb.mul(sin(uMorph.mul(3.14159265)));   // 0 at ends, 1 mid
            const p = baseV.mul(uCurlScale).add(time.mul(0.35)).add(s.x.mul(12.0));
            const disp = vec3(
                sin(p.y).sub(cos(p.z)),
                sin(p.z).sub(cos(p.x)),
                sin(p.x).sub(cos(p.y)),
            ).mul(s.z);
            const center = baseV.add(disp.mul(env).mul(uCurlStrength));
            const sz = max(float(0.003), uSize.mul(s.y));
            const corner = uCamRight.mul(positionLocal.x.mul(sz)).add(uCamUp.mul(positionLocal.y.mul(sz)));
            return center.add(corner);
        })();

        // colour shifts from color→color2 across the morph; soft round dot.
        mat.colorNode = Fn(() => {
            let c = mix(uColor, uColor2, uMorph);
            if (map) c = c.mul(texture(map).sample(uv()).rgb);
            return c;
        })();

        mat.opacityNode = Fn(() => {
            const s = attribute('iSeed');
            // soft radial dot (so a particle reads as a glowing point w/o a map)
            const d = length(uv().sub(0.5));
            let a = uOpacity.mul(smoothstep(float(0.5), float(0.0), d));
            // gentle twinkle
            const tw = float(0.7).add(sin(time.mul(5).add(s.x.mul(40))).mul(0.3));
            a = a.mul(tw);
            if (map) a = a.mul(texture(map).sample(uv()).a);
            return a;
        })();

        const mesh = new THREE.InstancedMesh(geo, mat, count);
        mesh.frustumCulled = false;
        mesh.name = opts.name || 'particle_morph';
        mesh.userData.noSupportCheck = true;
        mesh.userData.noClippingCheck = true;
        mesh.userData.noCameraCollide = true;
        mesh.userData.noZFightCheck = true;
        scene.add(mesh);

        let curFrom = 0, curTo = 1;
        const setSegment = (fromIdx, toIdx) => {
            if (fromIdx === curFrom && toIdx === curTo) return;
            curFrom = fromIdx; curTo = toIdx;
            if (targets[fromIdx]) { aFrom.array.set(targets[fromIdx]); aFrom.needsUpdate = true; }
            if (targets[toIdx]) { aTo.array.set(targets[toIdx]); aTo.needsUpdate = true; }
        };

        // scene-driven: pick the segment + morph factor + turbulence each frame
        const morph = (fromIdx, toIdx, m, turbulence) => {
            setSegment(fromIdx, toIdx);
            uMorph.value = Math.max(0, Math.min(1, m));
            uTurb.value = (turbulence != null) ? turbulence : Math.sin(uMorph.value * Math.PI);
        };

        const _r = new THREE.Vector3(), _u = new THREE.Vector3();
        const update = () => {
            const cam = opts.camera || globalThis._c || globalThis._camera;
            if (!cam) return;
            cam.updateMatrixWorld();
            _r.setFromMatrixColumn(cam.matrixWorld, 0).normalize();
            _u.setFromMatrixColumn(cam.matrixWorld, 1).normalize();
            uCamRight.value.copy(_r); uCamUp.value.copy(_u);
        };
        update();
        (globalThis._autoParticleSystems || (globalThis._autoParticleSystems = [])).push(update);

        return {
            mesh, material: mat, morph, update, count,
            setTargets: (arr) => { for (let i = 0; i < arr.length; i++) targets[i] = resampleToN(arr[i], count); },
            // swap one target's points mid-render (e.g. capture a live VRM pose
            // at the dissolve instant); re-uploads the active buffer if needed.
            updateTarget: (idx, pts) => {
                targets[idx] = resampleToN(pts, count);
                if (idx === curFrom) { aFrom.array.set(targets[idx]); aFrom.needsUpdate = true; }
                if (idx === curTo) { aTo.array.set(targets[idx]); aTo.needsUpdate = true; }
            },
            uniforms: { morph: uMorph, turb: uTurb, spin: uSpin, vortex: uVortex, size: uSize, opacity: uOpacity, color: uColor, color2: uColor2 },
        };
    };

    console.log('[particle_morph] makeParticleMorph ready — generators: fromMesh, fromText, neuronGraph, neuralNet, fromPoints');
})();
