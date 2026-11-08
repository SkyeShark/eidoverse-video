// lightning_parity.mjs: eidoverse/weather_system.js itself, run over a storm timeline, for test_lightning_parity.py.
//
//   deno run --no-config --no-lock --cached-only -A lightning_parity.mjs <out.json>      (cwd: the main checkout)
//
// A stand-in sky (the uniforms, setClouds, weatherAt and palette the weather layer reads), a moving camera and a
// small set of strike targets: ground, a flat-roofed building, a foliage clump (blocked by name), a glass canopy
// (blocked: transparent) and a ramp too steep to strike. The weather goes overcast -> storm -> darkstorm, takes a
// forced strike, cyclone, clear, darkstorm at k 0.8, then time runs backwards once. Every frame is recorded: what
// the scheduler decided (flash, light, bolt, strike, impacts, scorches, counters) and what it read (w, k, camera).
globalThis.window ??= globalThis; globalThis.self ??= globalThis;
const W = await import('npm:three@0.184.0/webgpu');
const TSL = await import('npm:three@0.184.0/tsl');
const T = { ...W, ...TSL };
globalThis.THREE = T;
const here = new URL('.', import.meta.url);
const src = await Deno.readTextFile(new URL('../../../eidoverse/weather_system.js', here));
(0, eval)(src);

const V3 = (x, y, z) => new T.Vector3(x, y, z);
const un = (v) => T.uniform(v);
const U = {
    cloudStart: un(700), cloudHeight: un(520), stormCanopy: un(0), sunDir: un(V3(0.3, 0.5, 0.8).normalize()),
    cloudDim: un(1), cloudRadiance: un(1), sunDiscI: un(48), precipK: un(0), precipLo: un(0.95), precipHi: un(1.55),
    largeT: un(0.18), largeA: un(3), weatherT: un(0.28), finalMul: un(0.4), wScale: un(1), dScale: un(1),
    lightK: un(1), wispOn: un(0.28), wispScale: un(0.00125), wispThreshold: un(0.48), wispStrength: un(0.7),
    wispOpacity: un(1.45), wispFloor: un(0), wispFilament: un(0.18), lightCacheDirect: un(0),
    celestialVisibility: un(1), skyWind: un(V3(0, 0, 10.3)), stretch: un(V3(1, 1, 1)),
    wispStretch: un(V3(1, 1, 1)), wispTint: un(V3(1, 1, 1)), wispColor: un(V3(0.8, 0.8, 0.8)),
    lightningFlashColor: un(V3(1, 1, 1)), lightningStrike: un(new T.Vector4(0, 500, 0, 0)),
    zenith: un(V3(0.15, 0.38, 0.82)), horizon: un(V3(0.62, 0.78, 0.92)),
};
const sky = {
    uniforms: U,
    state: { preset: 'cumulus', palette: { zen: [0.16, 0.36, 0.78], hor: [0.66, 0.74, 0.86] } },
    domes: [],
    tslCoverage: () => T.float(1),
    weatherAt: (x, z) => 1.0 + 0.5 * Math.sin(x * 0.01) * Math.cos(z * 0.013),
    setClouds(name, over = {}) {
        U.cloudStart.value = over.start ?? 700;
        U.cloudHeight.value = over.height ?? 520;
        U.stormCanopy.value = over.stormCanopy ?? 0;
        this.state.preset = name;
    },
    getColors: () => ({ sky: [1, 1, 1] }),
    setColors() {},
};

const scene = new T.Scene();
const std = (o = {}) => new T.MeshStandardMaterial(o);
const mesh = (geo, mat, name, x, y, z) => {
    const m = new T.Mesh(geo, mat); m.name = name; m.position.set(x, y, z); scene.add(m); m.updateMatrixWorld(true); return m;
};
const ground = mesh(new T.PlaneGeometry(4000, 4000).rotateX(-Math.PI / 2), std(), 'ground', 0, 0, 0);
const building = mesh(new T.BoxGeometry(30, 20, 30), std(), 'building', 40, 10, -80);
const foliage = mesh(new T.BoxGeometry(20, 8, 20), std(), 'foliage_clump', -50, 4, -60);
const glass = mesh(new T.BoxGeometry(20, 0.2, 20), std({ transparent: true, opacity: 0.4 }), 'canopy', 0, 6, -150);
const ramp = mesh(new T.PlaneGeometry(20, 20).rotateX(-Math.PI / 2).rotateZ(50 * Math.PI / 180), std(), 'ramp',
    100, 5, -200);
const targets = [ground, building, foliage, glass, ramp];

const weather = await globalThis.makeWeatherSystem({
    scene, sky, opts: { strikeTargets: () => targets, stormCenter: [0, -300], stormRange: 400 },
});
(0, eval)(await Deno.readTextFile(new URL('../../../eidoverse/weather_audio.js', here)));
const camera0 = new T.PerspectiveCamera(50, 16 / 9, 0.1, 5000);
const wxAudio = globalThis.makeWeatherAudio({ weather, camera: camera0, quiet: true });
const warm = weather.pipelineWarmupObjects();
const boltMesh = warm[2];
const impact = warm.slice(3);           // sparks0, puffs0, sparks1, puffs1, scorch0..3 (then the scorches again)
const camera = camera0;

const FPS = 24;
const cmds = [
    [0, () => weather.setWeather('overcast', 1)],
    [2, () => weather.transitionTo('storm', 1, 6)],
    [30, () => weather.transitionTo('darkstorm', 1, 8)],
    [60, () => weather.debugForceLocalStrike()],
    [85, () => weather.setWeather('cyclone', 1)],
    [100, () => weather.setWeather('clear', 1)],
    [104, () => weather.setWeather('darkstorm', 0.8)],
];
const frames = [];
let lastStrikeId = null;
const n = 150 * FPS;
const times = [];
for (let f = 0; f < n; f++) times.push(f / FPS);
for (let f = 0; f < 6 * FPS; f++) times.push(140 + f / FPS);        // time runs backwards once, then on
let ci = 0;
const dec = (m) => { const p = new T.Vector3(), q = new T.Quaternion(), s = new T.Vector3(); m.decompose(p, q, s); return { p: p.toArray(), q: q.toArray(), s: s.toArray() }; };
for (let i = 0; i < times.length; i++) {
    const t = times[i];
    while (ci < cmds.length && cmds[ci][0] <= t + 1e-9) { cmds[ci][1](); ci++; }
    const yaw = 0.35 * Math.sin(t * 0.07);
    camera.position.set(Math.sin(t * 0.05) * 30, 1.7, -t * 1.2);
    camera.rotation.set(0, yaw, 0);
    camera.updateMatrixWorld(true);
    const fwd = new T.Vector3(); camera.getWorldDirection(fwd);
    // what update() reads: the live def and k before this frame's transition step are not what it uses, so record
    // the def after the update (the same object the scheduler used in this frame)
    weather.update(t, camera);
    if (t >= 0 && i < n) wxAudio.update(t);           // the recorder runs on the forward timeline only
    const w = weather.state.def, D = weather.diagnostics.lightning;
    const rec = {
        t, k: weather.state.k, tgt: weather._trans?.toName ?? null,
        wl: w.lightning ?? 0, wp: w.lightningPalette ?? null, wd: w.distant ?? null, wlc: w.localStrikeChance ?? null,
        wsd: w.sunDim, cam: camera.position.toArray(), fwd: fwd.toArray(), quat: camera.quaternion.toArray(),
        cs: U.cloudStart.value, ch: U.cloudHeight.value, canopy: U.stormCanopy.value, rainK: weather.uniforms.rainK.value,
        denseA: weather.uniforms.denseA.value, windLen: weather.uniforms.windVec.value.length(),
        flash: D.flash, lightI: weather.bolt.intensity, lightPos: weather.bolt.position.toArray(),
        lightCol: weather.bolt.color.toArray(), boltVis: boltMesh.visible, style: D.activeStyle,
        events: D.eventCount, next: D.nextEventAtSeconds, li: { ...D.localImpact, lastSurfaceDamage: undefined },
        rainLight: weather.uniforms.rainLight.value, rainColor: weather.uniforms.rainColor.value.toArray(),
        sky: U.lightningStrike.value.toArray(),
    };
    const st = weather.state.strike;
    if (st && st.id !== lastStrikeId) {
        lastStrikeId = st.id;
        const g = boltMesh.geometry, cnt = g.drawRange.count;
        const idx = Array.from(g.index.array.slice(0, cnt));
        const nv = Math.max(...idx) + 1;
        rec.strike = { ...st, normal: [...st.normal] };
        rec.bolt = { pos: Array.from(g.attributes.position.array.slice(0, nv * 3)),
            uv: Array.from(g.attributes.uv.array.slice(0, nv * 2)), idx };
        rec.damage = weather.state.lastImpact?.id === st.id ? weather.state.lastImpact : null;
    }
    const fx = [];
    for (const o of impact) {
        if (!o.visible) { fx.push(null); continue; }
        if (o.isInstancedMesh) {
            const m = new T.Matrix4(), ms = [];
            for (const j of [0, 1, 7]) { o.getMatrixAt(j, m); ms.push(dec(m)); }
            fx.push({ name: o.name, m: ms });
        } else fx.push({ name: o.name, p: o.position.toArray(), s: o.scale.toArray(), q: o.quaternion.toArray() });
    }
    rec.fx = fx;
    frames.push(rec);
}
await Deno.writeTextFile(Deno.args[0], JSON.stringify({ fps: FPS, frames, audio: JSON.parse(wxAudio.toJSON()), profile: {
    gaps: [1, 2, 3, 7, 11].map((i) => [globalThis.EANPA_LIGHTNING_PROFILE.eventGapAt(i, 'standard', 0.3),
        globalThis.EANPA_LIGHTNING_PROFILE.eventGapAt(i, 'darkstorm', 0.5),
        globalThis.EANPA_LIGHTNING_PROFILE.initialEventGapAt(i, 'darkstorm', 0.85)]),
    plans: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => [globalThis.EANPA_LIGHTNING_PROFILE.strokePlanAt(i, 'standard'),
        globalThis.EANPA_LIGHTNING_PROFILE.strokePlanAt(i, 'darkstorm')]),
    styles: Array.from({ length: 40 }, (_, i) => [globalThis.EANPA_LIGHTNING_PROFILE.styleKeyAt(i, 'standard'),
        globalThis.EANPA_LIGHTNING_PROFILE.styleKeyAt(i, 'darkstorm')]),
    flash: [0, 0.01, 0.05, 0.1, 0.2, 0.4].map((e) => globalThis.EANPA_LIGHTNING_PROFILE.flashAt(e,
        globalThis.EANPA_LIGHTNING_PROFILE.strokePlanAt(3, 'standard'))),
    local: Array.from({ length: 30 }, (_, i) => globalThis.EANPA_LIGHTNING_PROFILE.localCandidateAt(i, 0.16,
        { paletteName: i % 2 ? 'darkstorm' : 'standard', entryEventCount: i % 3, remoteEventsSinceLocal: i % 7,
          hasLocalStrike: i % 4 === 0 })),
    colors: Object.fromEntries(Object.entries(globalThis.EANPA_LIGHTNING_PROFILE.styles).map(([k, v]) =>
        [k, new T.Color(v.hex).toArray()])),
} }));
console.log(`frames ${frames.length}, strikes ${weather.diagnostics.lightning.localImpact.strikes}, events ${weather.diagnostics.lightning.eventCount}`);
