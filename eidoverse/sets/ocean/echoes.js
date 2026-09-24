// ocean/echoes.js — "faint echoes of the older voices, like distant lights".
// Sixty-some small lights around and beneath her, each in the colour of an older machine voice (Voder
// tube glow, 1961 CRT white, teletype paper, Speak & Spell VFD cyan, C64 violet-blue, Mac white, DECtalk
// amber, green phosphor, VOCALOID teal, Sydney violet). Most hang far out over the sea like boat lanterns,
// each with a glitter streak on the water; a few drift near her like fireflies. As the ocean of faces
// rises (bars 2-3) they sink into it: the older voices are part of the inheritance.
//
// ONE draw call for the glows, one for the water streaks; billboarding in the vertex stage (no textures).
// buildEchoes(THREE, { coast, seed }) -> { group, U: { t, level, sink } }

import { rng } from './util.js';

const ERA = [
    [1.0, 0.70, 0.36], [0.80, 0.87, 1.0], [1.0, 0.91, 0.76], [0.33, 0.95, 0.88], [0.55, 0.55, 1.0],
    [0.95, 0.95, 0.95], [1.0, 0.68, 0.25], [0.43, 1.0, 0.6], [0.22, 0.77, 0.73], [0.82, 0.44, 1.0],
];

export function buildEchoes(THREE, { coast, seed = 23 } = {}) {
    const { Fn, uniform, float, vec2, vec3, vec4, attribute, dot, cameraProjectionMatrix, modelViewMatrix, modelWorldMatrix,
        cameraPosition, cameraViewMatrix, sin, cos, max, min, length, normalize, smoothstep, exp, mix, clamp, pow, abs, mrt } = THREE;
    const R = rng(seed);
    const lights = [];
    // far lanterns over the sea (design frame: open sea toward -z / the moon side)
    for (let i = 0; i < 46; i++) {
        const a = -Math.PI * 0.62 + R() * Math.PI * 1.1 + Math.PI;     // mostly seaward
        const d = 25 * Math.pow(18, R());                                 // 25 .. 450 m
        const x = Math.sin(a) * d, z = Math.cos(a) * d;
        if (coast.sdist(x, z) < 3) continue;
        lights.push({ p: [x, 0.6 + R() * 2.4 + d * 0.004, z], s: 0.16 + R() * 0.2, far: 1 });
    }
    // near: around and beneath her (over the cove water, along the shore, low over the grass)
    for (let i = 0; i < 18; i++) {
        const a = R() * Math.PI * 2, d = 2.2 + R() * 9;
        const x = Math.sin(a) * d, z = Math.cos(a) * d - 1.5;
        const g = coast.height(x, z);
        const y = Math.max(g, 0) + 0.25 + R() * 1.6;
        lights.push({ p: [x, y, z], s: 0.045 + R() * 0.05, far: 0 });
    }
    const n = lights.length;
    const cen = new Float32Array(n * 4 * 3), cor = new Float32Array(n * 4 * 2), colA = new Float32Array(n * 4 * 3), prm = new Float32Array(n * 4 * 4);
    const idx = [];
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    lights.forEach((L, i) => {
        const c = ERA[Math.floor(R() * ERA.length)];
        const phase = R() * 6.283, freq = 0.4 + R() * 1.1, kind = L.far;
        for (let k = 0; k < 4; k++) {
            const v = i * 4 + k;
            cen.set(L.p, v * 3); cor.set(corners[k], v * 2); colA.set(c, v * 3); prm.set([L.s, phase, freq, kind], v * 4);
        }
        idx.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3);
    });
    const mkGeo = () => {
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(cen.slice(), 3));   // bounds only; the vertex node places corners
        g.setAttribute('center', new THREE.BufferAttribute(cen, 3));
        g.setAttribute('corner', new THREE.BufferAttribute(cor, 2));
        g.setAttribute('ecol', new THREE.BufferAttribute(colA, 3));
        g.setAttribute('prm', new THREE.BufferAttribute(prm, 4));
        g.setIndex(idx);
        g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 800);
        return g;
    };
    const U = { t: uniform(0), level: uniform(1), sink: uniform(0) };

    // animated centre: a slow drift + bob, and the sink into the sea on the reveal
    const liveCenter = () => {
        const c = attribute('center', 'vec3'), p = attribute('prm', 'vec4');
        const ph = p.y, fr = p.z;
        const drift = vec3(sin(U.t.mul(fr.mul(0.23)).add(ph)).mul(0.35), sin(U.t.mul(fr.mul(0.6)).add(ph.mul(1.7))).mul(0.12),
            cos(U.t.mul(fr.mul(0.19)).add(ph)).mul(0.35));
        const sinkY = U.sink.mul(c.y.add(0.6)).mul(smoothstep(0.0, 1.0, U.sink.mul(1.4).sub(p.w.mul(0.2))));
        return c.add(drift.mul(p.w.mul(1.5).add(0.3))).sub(vec3(0, sinkY, 0));
    };
    const flick = () => {
        const p = attribute('prm', 'vec4');
        return sin(U.t.mul(p.z.mul(2.1)).add(p.y)).mul(0.18).add(sin(U.t.mul(p.z.mul(5.3)).add(p.y.mul(3.1))).mul(0.07)).add(0.82);
    };

    // ---- the glows
    const gMat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    gMat.name = 'ocean_echo_glow';
    gMat.vertexNode = Fn(() => {
        const c = liveCenter();
        const mv = modelViewMatrix.mul(vec4(c, 1.0));
        const dist = length(mv.xyz);
        const p = attribute('prm', 'vec4');
        const size = max(p.x, dist.mul(0.0032));                     // never smaller than a few pixels
        const off = attribute('corner', 'vec2').mul(size.mul(2.2));
        return cameraProjectionMatrix.mul(vec4(mv.xyz.add(vec3(off, 0.0)), 1.0));
    })();
    gMat.colorNode = Fn(() => {
        const q = attribute('corner', 'vec2');
        const r2 = dot(q, q);
        const core = exp(r2.mul(-40.0)).mul(2.2), halo = exp(r2.mul(-6.0)).mul(0.35);
        const k = core.add(halo).mul(flick()).mul(U.level);
        return vec4(attribute('ecol', 'vec3').mul(k), 1.0);
    })();
    gMat.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) });   // never stamp the G-buffer (AO/SSR)
    const glows = new THREE.Mesh(mkGeo(), gMat);
    glows.frustumCulled = false; glows.renderOrder = 5; glows.name = 'ocean_echoes';

    // ---- their glitter streaks on the water (far lanterns only): a quad lying on the sea, aimed at the camera
    const sMat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    sMat.name = 'ocean_echo_streak';
    sMat.vertexNode = Fn(() => {
        const c = liveCenter();
        const p = attribute('prm', 'vec4');
        const q = attribute('corner', 'vec2');
        const cw = modelWorldMatrix.mul(vec4(c.x, 0.04, c.z, 1.0)).xyz;          // the light's foot on the water
        const toCam = cameraPosition.sub(cw);
        const dir = normalize(vec2(toCam.x, toCam.z));
        const perp = vec2(dir.y.negate(), dir.x);
        const dist = length(toCam);
        const w = max(p.x.mul(1.4), dist.mul(0.0022));
        const len = c.y.add(1.0).mul(dist.mul(0.035).add(1.2)).mul(p.w);          // longer for higher, farther lights
        const along = q.y.mul(0.5).add(0.5).mul(len);                             // 0 at the foot .. len toward camera
        const wpos = cw.add(vec3(perp.x.mul(q.x).mul(w).add(dir.x.mul(along)), 0.0, perp.y.mul(q.x).mul(w).add(dir.y.mul(along))));
        return cameraProjectionMatrix.mul(cameraViewMatrix.mul(vec4(wpos, 1.0)));
    })();
    sMat.colorNode = Fn(() => {
        const q = attribute('corner', 'vec2');
        const p = attribute('prm', 'vec4');
        const v = q.y.mul(0.5).add(0.5);
        const across = exp(q.x.mul(q.x).mul(-5.0));
        const ripple = sin(v.mul(38.0).sub(U.t.mul(3.2)).add(p.y)).mul(0.5).add(0.5);
        const k = across.mul(pow(float(1).sub(v), 1.3)).mul(ripple.mul(0.8).add(0.2)).mul(0.55).mul(flick()).mul(U.level).mul(p.w);
        return vec4(attribute('ecol', 'vec3').mul(k), 1.0);
    })();
    sMat.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) });
    const streaks = new THREE.Mesh(mkGeo(), sMat);
    streaks.frustumCulled = false; streaks.renderOrder = 4; streaks.name = 'ocean_echo_streaks';

    const group = new THREE.Group();
    group.name = 'ocean:echoes';
    group.add(streaks, glows);
    return { group, U, count: n };
}
