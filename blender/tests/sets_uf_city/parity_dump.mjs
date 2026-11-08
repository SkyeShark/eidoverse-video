// Dumps the WebGPU city kit's numbers (plan, buildings, lamps, traffic, far skyline, cameras, rim towers, cables,
// noise, environment, hashes, the sign atlas's packing) for test_parity.py to compare with the Blender port.
//   deno run --no-config --no-lock -A parity_dump.mjs <three.module.js> <worktree> <out.json>
const [threePath, worktree, outPath] = Deno.args;
const THREE = await import('file:///' + threePath.replace(/\\/g, '/'));
const base = 'file:///' + worktree.replace(/\\/g, '/') + '/eidoverse/sets/unknown_force/';
const KIT = await import(base + 'citykit.js');
const C = await import(base + 'city.js');
const H = await import(base + 'hole.js');

// city.js keeps planLamps / planTraffic / emitFarSkyline / ringSector private: lift them from the source as written
const src = Deno.readTextFileSync(new URL(base + 'city.js'));
function lift(name) {
    const i = src.indexOf('function ' + name + '(');
    let depth = 0, j = src.indexOf('{', i);
    for (let k = j; k < src.length; k++) { if (src[k] === '{') depth++; else if (src[k] === '}') { depth--; if (depth === 0) { j = k + 1; break; } } }
    return src.slice(i, j);
}
const scope = { KIT, THREE, ...KIT, lerp: KIT.lerp, rng: KIT.rng };
const names = Object.keys(scope);
const mk = (fnName) => new Function(...names, lift(fnName) + '; return ' + fnName + ';')(...names.map((n) => scope[n]));
const planLamps = mk('planLamps'), planTraffic = mk('planTraffic');
const emitFarSkyline = mk('emitFarSkyline'), ringSector = mk('ringSector');

const out = {};
const r = KIT.rng(1909); out.rng1909 = Array.from({ length: 8 }, () => r());
out.hash1 = [0, 1, 2.5, 7.13, 100.37].map(KIT.hash1);
out.nearestAvenue = [[0.1, 50], [0.8, 200], [2.0, 400], [-1.2, 170]].map(([t, rr]) => KIT.nearestAvenue(t, rr));
out.keyed = [0, 3, 7.5, 12, 33].map((t) => KIT.keyed([{ t: 0, v: [0, 1] }, { t: 5, v: [10, 2] }, { t: 10, v: [4, 8] }, { t: 20, v: [7, 7] }], t));

// the plan
const plan = C.planCity(1909);
out.plan = { blocks: plan.blocks.length, lots: plan.lots.length, supertalls: plan.supertalls,
    firstLots: plan.lots.slice(0, 6), seedSum: plan.lots.reduce((a, l) => a + l.seed, 0),
    blockSample: [0, 7, 50, plan.blocks.length - 1].map((i) => plan.blocks[i]) };
// every building, as build() emits them (nearer lots first)
const buf = { concrete: new KIT.GeoBuf(), metal: new KIT.GeoBuf(), frame: new KIT.GeoBuf(), strip: new KIT.GeoBuf() };
const bctx = { buf, signs: [], lights: [] };
const lots = plan.lots.slice().sort((a, b) => (a.r0 - b.r0));
const built = [];
for (const l of lots) { const b = C.emitBuilding(THREE, l, bctx); if (b) built.push(b); }
const types = {}; for (const b of built) types[b.type || 'plaza'] = (types[b.type || 'plaza'] || 0) + 1;
const sig = (s) => ({ id: s.id, pos: s.pos, quat: [s.quat.x, s.quat.y, s.quat.z, s.quat.w], w: s.w, h: s.h, gain: s.gain, flicker: s.flicker, power: s.power });
out.buildings = { count: built.length, types, signs: bctx.signs.length, lights: bctx.lights.length,
    verts: Object.fromEntries(Object.entries(buf).map(([k, b]) => [k, b.count])),
    heightSum: built.reduce((a, b) => a + b.H, 0), firstBuilt: built.slice(0, 5),
    signSample: [0, 1, 17, 200, 999, bctx.signs.length - 1].map((i) => sig(bctx.signs[i])),
    lightSample: [0, 5, bctx.lights.length - 1].map((i) => bctx.lights[i]),
    posSum: [0, 1, 2].map((k) => buf.concrete.p.filter((_, i) => i % 3 === k).reduce((a, v) => a + v, 0)),
    uvSum: [0, 1].map((k) => buf.metal.uv.filter((_, i) => i % 2 === k).reduce((a, v) => a + v, 0)),
    aTSum: [0, 1, 2, 3].map((k) => buf.frame.aT.filter((_, i) => i % 4 === k).reduce((a, v) => a + v, 0)),
    aMSum: [0, 1, 2, 3].map((k) => buf.strip.aM.filter((_, i) => i % 4 === k).reduce((a, v) => a + v, 0)) };
const far = new KIT.GeoBuf(); emitFarSkyline(THREE, far);
out.far = { verts: far.count, posSum: [0, 1, 2].map((k) => far.p.filter((_, i) => i % 3 === k).reduce((a, v) => a + v, 0)) };
const lamps = planLamps();
out.lamps = { count: lamps.length, sample: [0, 1, 100, lamps.length - 1].map((i) => lamps[i]) };
const paths = planTraffic();
out.traffic = { count: paths.length, sample: [0, 1, 500, paths.length - 1].map((i) => paths[i]),
    speedSum: paths.reduce((a, p) => a + p.speed, 0), phaseSum: paths.reduce((a, p) => a + p.phase, 0) };
const rs = ringSector(THREE, 120, 160, 0.2, 0.6, 11.7, 12.16, 5);
out.ringSector = { n: rs.P.length / 3, p0: rs.P.slice(0, 12), sum: rs.P.reduce((a, v) => a + v, 0) };

// cameras
const T = [0, 2, 4.5, 9, 10, 16, 20, 25, 30, 32.9, 33, 34.5, 37, 40.8];
out.dive = T.map((t) => ({ t, ...C.diveCam(t), focal: C.diveFocal(t), vel: C.camVelocity(C.diveCam, t) }));
out.DIVE_C = C.DIVE_C;
out.holeCams = {};
for (const n of H.HOLE_CAMS) out.holeCams[n] = [0, 0.3, 0.5, 0.9, 1.0].map((u) => H.holeCam(n, u * H.HOLE_CAM_DUR[n]));
out.holeCamDur = H.HOLE_CAM_DUR;
out.RIM = H.RIM;
out.cables = []; for (let i = 0; i < 12; i++) for (const k of [0, 1]) out.cables.push(H.cableEnds(THREE, i, k));

// textures
const nt = KIT.noiseTexture(THREE);
const nd = nt.image.data;
out.noise = { sum: [0, 1, 2, 3].map((c) => { let s = 0; for (let i = c; i < nd.length; i += 4) s += nd[i]; return s; }),
    px: [[0, 0], [17, 3], [255, 400], [511, 511]].map(([x, y]) => Array.from(nd.slice((y * 512 + x) * 4, (y * 512 + x) * 4 + 4))) };
Deno.writeFileSync(outPath.replace(/\.json$/, '_noise.bin'), nd);
const et = KIT.nightEnvTexture(THREE);
const ed = et.image.data;
out.env = { sum: [0, 1, 2].map((c) => { let s = 0; for (let i = c; i < ed.length; i += 4) s += ed[i]; return s; }),
    px: [[0, 0], [100, 120], [300, 140], [511, 255]].map(([x, y]) => Array.from(ed.slice((y * 512 + x) * 4, (y * 512 + x) * 4 + 4))) };

// the sign atlas's shelf packing (makeSignAtlas places items in this order with these sizes; drawing needs a canvas)
{
    const N = 2048, NH = 3200; const items = {}; let cx = 16, cy = 16, rowH = 0;
    const place = (id, w, h) => { if (cx + w + 16 > N) { cx = 16; cy += rowH + 16; rowH = 0; } if (cy + h + 16 > NH) return;
        items[id] = { u: cx / N, v: cy / NH, w: w / N, h: h / NH, aspect: w / h }; cx += w + 16; rowH = Math.max(rowH, h); };
    for (const ad of KIT.AD_COPY) place('ad:' + ad.id, 600, 150);
    KIT.FUTURIST.forEach((w, i) => place('fut:' + i, 768, 128));
    for (const [w] of KIT.SHOPS) place('shop:' + w, 480, 120);
    for (const [w] of KIT.BLADES) place('blade:' + w, 96, 448);
    place('heli', 256, 256); place('chev', 256, 128);
    for (let i = 0; i < 8; i++) place('roof:' + i, 448, 224);
    out.atlas = items;
}
Deno.writeTextFileSync(outPath, JSON.stringify(out));
console.log('[parity-dump] wrote', outPath);
