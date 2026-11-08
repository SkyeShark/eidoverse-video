// js_parity.mjs: the sky worlds' plain-JavaScript maths, run from the WebGPU sources, dumped as JSON for the Python
// port to match (js_parity.py compares). Run with deno:
//   deno run --no-config --no-lock -A blender/tests/sky_worlds/js_parity.mjs <three build dir> <eanpa engine dir> <out.json>
// - redgiant.js (Eanpa engine): flareEnv for every slot and the shield's five impact slots over time
// - ring_eclipse.js (Eanpa engine): ringSolarVisibility over a grid of suns and receivers
// - fragment_motion.js (Eanpa engine): the separated base positions and update(t) of a stand-in cluster
// - eidoverse/ringworld.js eclipseK (copied inline below from the module's returned object: a pure function)
const [threeDir, eanpaDir, outPath] = Deno.args;
// (named T, not THREE: the eval'd classic script must resolve THREE to the global mock below)
const T = await import('file:///' + threeDir.replace(/\\/g, '/') + '/three.module.js');
const toUrl = (p) => 'file:///' + p.replace(/\\/g, '/');

// ---- red giant: the module reads THREE at call time; only uniform() and Vector3 are needed outside TSL graphs ----
// a uniform is {value}; any node method on it (uStarT.mul(...) builds part of a TSL graph) returns a dummy node
const node = () => new Proxy(() => node(), { get: (_t, k) => (k === Symbol.toPrimitive ? () => 0 : node()) });
const uniform = (v) => new Proxy({ value: v }, {
    get: (t, k) => (k === 'value' ? t.value : node()),
    set: (t, k, val) => { if (k === 'value') t.value = val; return true; },
});
globalThis.THREE = { ...T, uniform };
const rgSrc = Deno.readTextFileSync(eanpaDir + '/redgiant.js');
eval(rgSrc);
const rg = await globalThis.makeRedGiant({ opts: { shield: true } });
const sky = { sunDir: new T.Vector3(), uniforms: { sunDiscI: { value: 48 }, sunGlowI: { value: 1 } } };
rg._sky = sky;
const redgiant = { flares: [], impacts: [], basis: [] };
for (let t = 0; t <= 120; t += 7.3) {
    const env = rg.flares.map((f) => rg.flareEnv(f, t));
    redgiant.flares.push({ t, env });
}
for (const [t, el] of [[0, 0.5], [3.7, 0.3], [11.2, 0.05], [29.9, -0.2], [64.0, 0.8], [101.5, 0.12]]) {
    sky.sunDir.set(Math.cos(el) * 0.6, Math.sin(el), Math.cos(el) * 0.8).normalize();
    rg.update(t);
    redgiant.impacts.push({ t, sun: sky.sunDir.toArray(),
        imp: rg.uniforms.impP.map((u, i) => [...u.value.toArray(), rg.uniforms.impA[i].value]),
        burst: rg.uniforms.burstK.value });
}

// ---- ring eclipse ----
const ecl = await import(toUrl(eanpaDir + '/ring_eclipse.js'));
const eclipse = [];
for (const sy of [-0.1, 0.02, 0.2, 0.6, 0.95]) {
    for (const sx of [-0.3, 0.0, 0.12]) {
        const s = new T.Vector3(sx, sy, 0.5).normalize();
        for (const p of [[0, 0, 0], [300, 2, -40], [-470, 0, 800], [0, 60, 2500]]) {
            eclipse.push({ sun: s.toArray(), p, v: ecl.ringSolarVisibility({ x: p[0], y: p[1], z: p[2] }, s,
                { center: { x: 0, y: 4921.6, z: 0.45 } }) });
        }
    }
}

// ---- fragment motion on a stand-in cluster (positions and radii as the shattered moon's) ----
const fm = await import(toUrl(eanpaDir + '/fragment_motion.js'));
const pieces = [];
const spec = [[-0.2, 0.25, 0.0, 0.55], [-1.52, 0.02, 0.1, 0.2], [-1.08, 0.14, -0.12, 0.21], [0.66, 0.21, -0.17, 0.25],
    [1.2, 0.1, 0.17, 0.22], [1.66, -0.03, -0.12, 0.2], [-2.0, -0.17, 0.03, 0.08], [0.33, 0.48, 0.27, 0.07]];
for (const [x, y, z, r] of spec) {
    // a pyramid of points at distance r from the piece's origin
    const pts = [[r, 0, 0], [-r * 0.5, r * 0.6, 0], [0, -r * 0.7, r * 0.3], [0, 0, -r * 0.9]];
    pieces.push({
        position: new T.Vector3(x, y, z), quaternion: new T.Quaternion(), scale: new T.Vector3(1, 1, 1),
        geometry: { getAttribute: () => ({ count: pts.length, getX: (i) => pts[i][0], getY: (i) => pts[i][1],
            getZ: (i) => pts[i][2] }) },
    });
}
const makePieces = (sp) => sp.map(([x, y, z, r]) => {
    // a pyramid of points at distance r from the piece's origin
    const pts = [[r, 0, 0], [-r * 0.5, r * 0.6, 0], [0, -r * 0.7, r * 0.3], [0, 0, -r * 0.9]];
    return {
        position: new T.Vector3(x, y, z), quaternion: new T.Quaternion(), scale: new T.Vector3(1, 1, 1),
        geometry: { getAttribute: () => ({ count: pts.length, getX: (i) => pts[i][0], getY: (i) => pts[i][1],
            getZ: (i) => pts[i][2] }) },
    };
});
const fragOf = (sp) => {
    const ps = makePieces(sp);
    const motion = fm.makeFragmentMotion(T, ps, { spread: 1.75 });
    const out = { spec: sp, base: motion.basePositions.map((v) => v.toArray()), hero: motion.heroIndex,
        stats: motion.stats, frames: [] };
    for (const t of [0, 13.5, 77.25]) {
        motion.update(t);
        out.frames.push({ t, pos: ps.map((p) => p.position.toArray()), quat: ps.map((p) => p.quaternion.toArray()) });
    }
    return out;
};
const frag = fragOf(spec);
// a crowded cluster: the envelopes overlap, so the separation loop has to move them apart
const frag2 = fragOf([[0, 0, 0, 0.5], [0.3, 0.1, 0, 0.4], [-0.2, -0.1, 0.2, 0.35], [0.1, 0.4, -0.1, 0.3],
    [0.05, -0.3, -0.2, 0.25]]);

Deno.writeTextFileSync(outPath, JSON.stringify({ redgiant, eclipse, frag, frag2 }, null, 1));
console.log('[js_parity] wrote ' + outPath);
