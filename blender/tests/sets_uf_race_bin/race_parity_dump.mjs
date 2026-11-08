// race_parity_dump.mjs: builds the WebGPU edition's race (eidoverse/sets/unknown_force/race.js, untouched) headless
// in Deno and dumps what the Blender port must reproduce: the car path, the crash poses, the debris, the lamp heads,
// update(t, state) for a list of song times and states (the car, its body, the wheels, the debris, the boot, every
// uniform, the light levels, the beam), camAt / focal, the noise and environment textures, the tower geometry, and
// the canvases (billboards, march atlas, radiator number, manifesto page) as PNGs.
//   cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_race_bin/race_parity_dump.mjs
// Writes blender/tests/sets_uf_race_bin/out/parity/race.json and race_*.png (race_parity.py compares).
const W = await import('npm:three@0.184.0/webgpu');
const napi = await import('npm:@napi-rs/canvas@0.1.69');
globalThis.THREE = W;
globalThis.document = { createElement: () => napi.createCanvas(1, 1) };
const root = Deno.cwd().replace(/\\/g, '/');
globalThis.EIDOVERSE_DIR = new URL('file:///' + root.replace(/^\/+/, '') + '/eidoverse/');
const R = await import(new URL('sets/unknown_force/race.js', globalThis.EIDOVERSE_DIR).href);
const outDir = root + '/blender/tests/sets_uf_race_bin/out/parity';
await Deno.mkdir(outDir, { recursive: true });
const race = await R.build(W, {});
const P = race.parts;
const v3 = (v) => [v.x, v.y, v.z];
const out = { CAR_LEN: P.carRig.length, LAYOUT: R.LAYOUT, CUES: R.CUES };
out.path = [];
for (let i = 0; i <= 40; i++) { const u = i / 40; out.path.push({ u, p: v3(P.carRig.path.getPointAt(u)), t: v3(P.carRig.path.getTangentAt(u)) }); }
const start = P.carRig.path.getPointAt(1), tg = P.carRig.path.getTangentAt(1);
out.crash = [0, 0.3, 0.8, 1.31, 1.5, 1.7, 1.95, 2.1, 2.5, 3.0].map((tc) => {
    const p = P.carRig.crashPose(tc, start, Math.atan2(tg.x, tg.z));
    return { tc, com: v3(p.com), pitch: p.pitch, roll: p.roll, yaw: p.yaw, spin: p.spin };
});
out.debris = P.works.debris.map((d) => ({ s0: d.s0, home: v3(d.home), v: v3(d.v), w: v3(d.w), r: d.r }));
out.heads = P.lamps.heads.map(v3);
out.suggest = [];
for (let t = 141.0; t <= 163.0; t += 0.25) out.suggest.push({ t, ...R.suggest(t) });
// update() samples: the film's cut plus edge cases
const cases = [];
for (const t of [142.2, 143.0, 145.0, 148.0, 149.0, 150.5, 152.5, 154.0, 155.3, 156.5, 157.3, 158.0, 158.4, 159.0, 159.44,
    159.6, 160.0, 160.75, 161.0, 161.39, 161.6, 162.0, 162.2, 162.42, 162.5, 162.7]) cases.push({ t, state: R.suggest(t).state });
cases.push({ t: 150.0, state: { carS: 120.5, carV: 10 } });
cases.push({ t: 151.0, state: { carT: 0.5, car: false } });
cases.push({ t: 152.0, state: { carT: 0.95, heel: 0.3, march: 0.5, marchT: 3.3, billA: 0.4, billB: 0.7, billboards: 0.8, gaze: -0.6 } });
cases.push({ t: 160.2, state: { crash: 0.45, headlamps: 0.5, rain: 0.3, wet: 0.6, lamps: 0.7, backRim: 0.5 } });
cases.push({ t: 161.0, state: { heel: 0.66 } });
cases.push({ t: 161.1, state: { heel: 0.71 } });
cases.push({ t: 161.2, state: { heel: 0.9 } });
const U = race.uniforms;
const uval = (u) => (u.value.isVector3 ? v3(u.value) : u.value);
out.update = cases.map(({ t, state }) => {
    race.update(t, state);
    const car = P.car, body = P.carRig.body;
    const rec = { t, state,
        car: { visible: car.visible, pos: v3(car.position), q: [car.quaternion.x, car.quaternion.y, car.quaternion.z, car.quaternion.w],
            body_pos: v3(body.position), body_rot: [body.rotation.x, body.rotation.z] },
        wheel_ang: P.carRig.wheels[0].spin.rotation.x,
        debris: P.works.debris.map((d) => ({ pos: v3(d.obj.position), rot: [d.obj.rotation.x, d.obj.rotation.y, d.obj.rotation.z] })),
        heel: { visible: P.heel.root.visible, y: P.heel.root.position.y, pitch: P.heel.pivot.rotation.x },
        shadow: { pos: v3(P.carRig.shadow.position), z: P.carRig.shadow.rotation.z },
        beam: { pos: v3(P.carRig.beam.position), target: v3(P.carRig.beam.target.position), i: P.carRig.beam.intensity },
        lights: Object.fromEntries(['key', 'glowA', 'glowB', 'rim', 'backRim', 'neonFill', 'hemi'].map((k) => [k, P.lights[k].intensity])),
        U: Object.fromEntries(Object.entries(U).filter(([k]) => k !== 'setInv').map(([k, u]) => [k, uval(u)])),
        cams: {} };
    for (const n of ['crashLow', 'carChase', 'carTrack', 'carSide', 'carFront', 'carRear']) rec.cams[n] = race.camAt(n, t, state);
    return rec;
});
out.focal = Object.fromEntries(Object.keys(race.cams).concat(['nothere']).map((n) => [n, race.focal(n)]));
out.cams = race.cams;
// textures: the tiling noise atlas and the night environment (Uint8 RGBA, rows bottom-up)
const b64 = (u8) => { let s = ''; for (let i = 0; i < u8.length; i += 32768) s += String.fromCharCode(...u8.subarray(i, i + 32768)); return btoa(s); };
const findTex = (pred) => { let hit = null; race.group.traverse((o) => { const m = o.material; if (!m || hit) return; }); return hit; };
// the noise atlas and env are reachable through any lit material's nodes; walk the scene for DataTextures
const dataTex = new Map();
const seen = new Set();
const walk = (n, depth = 0) => {
    if (!n || typeof n !== 'object' || seen.has(n) || depth > 60) return; seen.add(n);
    if (n.isDataTexture && n.image?.data) dataTex.set(n.image.width + 'x' + n.image.height, n);
    for (const k of Object.keys(n)) { const v = n[k]; if (v && typeof v === 'object' && (v.isNode || v.isTexture || Array.isArray(v) || k === 'value')) walk(v, depth + 1); }
};
race.group.traverse((o) => { if (o.material) for (const k of Object.keys(o.material)) { const v = o.material[k]; if (v && v.isNode) walk(v); } });
for (const [k, t] of dataTex) out['tex_' + k] = b64(t.image.data);
// the towers' merged geometry (positions and aux) as a checksum and a sample
const towers = P.towers.towers.geometry;
const tp = towers.attributes.position.array, ta = towers.attributes.aux.array;
let s = [0, 0, 0], sa = [0, 0, 0, 0];
for (let i = 0; i < tp.length; i += 3) { s[0] += tp[i]; s[1] += tp[i + 1]; s[2] += tp[i + 2]; }
for (let i = 0; i < ta.length; i += 4) { sa[0] += ta[i]; sa[1] += ta[i + 1]; sa[2] += ta[i + 2]; sa[3] += ta[i + 3]; }
out.towers = { count: tp.length / 3, index: towers.index.count, sum: s, auxSum: sa, first: Array.from(tp.slice(0, 30)), aux0: Array.from(ta.slice(0, 16)) };
const gsum = (g) => { const a = g.attributes.position.array; let q = [0, 0, 0]; for (let i = 0; i < a.length; i += 3) { q[0] += a[i]; q[1] += a[i + 1]; q[2] += a[i + 2]; } g.computeBoundingBox(); return { count: a.length / 3, index: g.index ? g.index.count : 0, sum: q, min: g.boundingBox.min.toArray(), max: g.boundingBox.max.toArray() }; };
out.meshes = {};
race.group.traverse((o) => { if (o.isMesh && o.geometry?.attributes?.position) out.meshes[o.name + '#' + o.id] = gsum(o.geometry); });
// canvases
const png = async (tex, name) => { const c = tex.image; if (c?.toBuffer) await Deno.writeFile(`${outDir}/race_${name}.png`, c.toBuffer('image/png')); };
await png(P.billboards.a.texture, 'billboard_a');
await png(P.billboards.b.texture, 'billboard_b');
await png(P.march.texture, 'march');
await png(P.heel.page.material.colorNode ? P.heel.page.material : null, 'skip');
const canv = new Set();
race.group.traverse((o) => { const m = o.material; if (!m) return; for (const k of Object.keys(m)) { const v = m[k]; if (v?.isNode) walk(v); } });
let ci = 0;
const seen2 = new Set();
const walk2 = (n, depth = 0) => {
    if (!n || typeof n !== 'object' || seen2.has(n) || depth > 60) return; seen2.add(n);
    if (n.isCanvasTexture && n.image?.toBuffer) canv.add(n);
    for (const k of Object.keys(n)) { const v = n[k]; if (v && typeof v === 'object' && (v.isNode || v.isTexture || Array.isArray(v) || k === 'value')) walk2(v, depth + 1); }
};
race.group.traverse((o) => { if (o.material) for (const k of Object.keys(o.material)) { const v = o.material[k]; if (v && v.isNode) walk2(v); } });
for (const t of canv) { const c = t.image; await Deno.writeFile(`${outDir}/race_canvas_${c.width}x${c.height}_${ci++}.png`, c.toBuffer('image/png')); }
await Deno.writeTextFile(`${outDir}/race.json`, JSON.stringify(out));
console.log('[race_parity_dump] wrote', outDir, 'CAR_LEN', out.CAR_LEN, 'textures', [...dataTex.keys()], 'canvases', canv.size);
Deno.exit(0);
