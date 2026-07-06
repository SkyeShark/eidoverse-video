// terrain.js — procedural heightfield terrain with vertex-painted texture
// blending. Flat PlaneGeometry ground is the #1 reason outdoor scenes read as
// tech demos; this gives undulating ground with up to three texture layers
// blended by height, slope, and noise — baked as VERTEX COLORS once at build
// time (a one-time CPU pass; the per-frame work is all GPU).
//
//   const terrain = globalThis.makeTerrain({
//       size: 80, segments: 160, amplitude: 3, seed: 7,
//       layers: [
//           { map: grassDiff, normalMap: grassNor, repeat: 18 },  // base (low/flat)
//           { map: dirtDiff,  repeat: 14 },                        // high ground (noise-broken)
//           { map: rockDiff,  repeat: 10 },                        // steep slopes
//       ],
//       flatRadius: 8,    // optional flat clearing at the center (stage your action there)
//   });
//   scene.add(terrain.mesh);
//   const y = terrain.heightAt(x, z);     // exact height anywhere — spawn props/characters with it
//
// Pairs with: snapToGround(prop, [terrain.mesh]) for props,
// scatterOn(rocks, terrain.mesh, { sink: [0.15, 0.35], tiltMax: 0.3 }) for
// debris fields, and the VRMCharacterController's collision meshes for walks.
(function () {
    'use strict';
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[terrain] THREE global not present — skipping load'); return; }

    function mulberry32(seed) {
        let a = (seed | 0) || 1;
        return () => {
            a |= 0; a = (a + 0x6D2B79F5) | 0;
            let t = Math.imul(a ^ (a >>> 15), 1 | a);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    globalThis.makeTerrain = (opts = {}) => {
        const {
            size = 80, segments = 128, amplitude = 3, seed = 1,
            layers = [],
            flatRadius = 0, flatHeight = 0,
            slopeSteep = [0.25, 0.55],   // (1 - normal.y) range where the steep layer fades in
            highStart = null,            // world-Y where the mid layer starts (default 0.45*amplitude)
            octaves = 4, frequency = 2.5,
        } = opts;
        const rand = mulberry32(seed);
        const GS = 64;
        const grid = new Float32Array(GS * GS);
        for (let i = 0; i < grid.length; i++) grid[i] = rand();
        const lerp = (a, b, t) => a + (b - a) * t;
        const sm = (t) => t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t);
        const g = (X, Y) => grid[((Y % GS + GS) % GS) * GS + ((X % GS + GS) % GS)];
        const vnoise = (x, y) => {
            const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
            return lerp(lerp(g(xi, yi), g(xi + 1, yi), sm(xf)),
                        lerp(g(xi, yi + 1), g(xi + 1, yi + 1), sm(xf)), sm(yf));
        };
        const fbm = (x, y) => {
            let v = 0, a = 0.5, f = 1;
            for (let o = 0; o < octaves; o++) { v += a * vnoise(x * f, y * f); a *= 0.5; f *= 2; }
            return v / (1 - Math.pow(0.5, octaves));
        };
        const heightAt = (x, z) => {
            const u = (x / size + 0.5) * frequency, v = (z / size + 0.5) * frequency;
            let h = (fbm(u, v) - 0.5) * 2 * amplitude;
            if (flatRadius > 0) {
                const d = Math.hypot(x, z);
                const k = sm((d - flatRadius) / Math.max(0.001, flatRadius * 0.6));
                h = lerp(flatHeight, h, k);
            }
            return h;
        };

        const geo = new THREE.PlaneGeometry(size, size, segments, segments);
        geo.rotateX(-Math.PI / 2);
        const pos = geo.attributes.position;
        for (let i = 0; i < pos.count; i++) pos.setY(i, heightAt(pos.getX(i), pos.getZ(i)));
        geo.computeVertexNormals();

        // bake blend weights as vertex colors: R = base, G = mid, B = steep
        const nor = geo.attributes.normal;
        const colors = new Float32Array(pos.count * 3);
        const hi = highStart == null ? amplitude * 0.45 : highStart;
        const nLayers = Math.min(3, layers.length);
        for (let i = 0; i < pos.count; i++) {
            const slope = 1 - nor.getY(i);
            let wSteep = nLayers >= 3 ? sm((slope - slopeSteep[0]) / (slopeSteep[1] - slopeSteep[0])) : 0;
            const x = pos.getX(i), z = pos.getZ(i), y = pos.getY(i);
            const breakup = fbm(x * 0.15 + 31.7, z * 0.15 + 7.3) - 0.5;
            let wMid = nLayers >= 2
                ? sm((y - hi + breakup * amplitude) / Math.max(0.001, amplitude * 0.5)) * (1 - wSteep)
                : 0;
            const wBase = Math.max(0, 1 - wMid - wSteep);
            colors[i * 3] = wBase; colors[i * 3 + 1] = wMid; colors[i * 3 + 2] = wSteep;
        }
        geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const mat = new THREE.MeshStandardNodeMaterial({ roughness: 0.95, metalness: 0.0 });
        if (nLayers) {
            const { texture: texNode, uv, attribute } = THREE;
            const w = attribute('color');
            let colorNode = null;
            layers.slice(0, 3).forEach((L, i) => {
                if (!L.map) return;
                const rep = L.repeat ?? 12;
                L.map.wrapS = L.map.wrapT = THREE.RepeatWrapping;
                const sample = texNode(L.map, uv().mul(rep));
                const wi = i === 0 ? w.x : i === 1 ? w.y : w.z;
                const term = sample.mul(wi);
                colorNode = colorNode ? colorNode.add(term) : term;
            });
            if (colorNode) mat.colorNode = colorNode;
            if (layers[0].normalMap) {
                const rep0 = layers[0].repeat ?? 12;
                layers[0].normalMap.wrapS = layers[0].normalMap.wrapT = THREE.RepeatWrapping;
                layers[0].normalMap.repeat.set(rep0, rep0);
                mat.normalMap = layers[0].normalMap;
            }
        } else {
            mat.color = new THREE.Color(0x6b6f5e);
        }

        const mesh = new THREE.Mesh(geo, mat);
        mesh.name = 'terrain';
        mesh.receiveShadow = true;
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('makeTerrain');
        return { mesh, heightAt };
    };
})();
