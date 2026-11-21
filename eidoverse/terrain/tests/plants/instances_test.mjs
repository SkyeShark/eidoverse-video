// build/plant_instances.js in this edition's renderer (PORT_PLAN.md 8.2 row P15: "the per-frame LOD a compute pass";
// 10.3: indirect draws in three r184's WebGPU backend headless; SURFACING_DESIGN.md 5.4 package 4 item 3: at most 64
// trees at their full level in any frame, no shrub, grass or forb realised), on a fixture case's terrain and
// Blender's spots of it:
//
//     EIDO_GPU_WRAP='<the GPU queue>' deno run --config deno.json --frozen --allow-all \
//         eidoverse/terrain/tests/plants/instances_test.mjs [--case lauterbrunnen_r250]
//     (the render is a GPU job of its own, behind $EIDO_GPU_WRAP; this orchestrator needs no GPU)
//
// One render job (eidoverse/render_scene.mjs): the case's snapshot built, Blender's spots of it loaded
// (PlantSpots.load, attach), instancePlants, then per test camera (at the focus at eye height, 120 m off it, 400 m
// over it) the LOD pass, its bucket counts read back (test code) against the same rule in JavaScript doubles (the
// hero_k-th nearest within hero_m, the card distance, the billboards beyond), the pass' wall time, and a frame with
// the plants and one without them (the draws are indirect: the plants must show). Writes
// tests/out/plants/instances_test.json and the frames under tests/out/plants/instances/.

import * as S from './_plants.mjs';

const A = S.argsOf();
const T = new S.C.Checks('plants: the instancing and its per-frame LOD');
const root = S.fixtureRoot('the spots fixtures');
const man = root && S.W.exists(`${root}/spots/manifest.json`) ? JSON.parse(Deno.readTextFileSync(`${root}/spots/manifest.json`)) : null;
if (!man) {
    S.W.skip('instances', 'run tests/plants/plants_fixtures.py --spots');
    Deno.exit(0);
}
const name = A.opt('--case', 'lauterbrunnen_r250');
const info = JSON.parse(Deno.readTextFileSync(`${root}/spots/${name}/info.json`));
const snap = `${man.snaps}/${info.args.snap ?? name}.npz`;
const out = `${S.W.out('plants')}/instances`;
const work = `${out}/_scenes`;
Deno.mkdirSync(work, { recursive: true });
const W = 960, H = 540;
const spec = { snap, spots: `${root}/spots/${name}/${name}`, focus: info.focus[0], W, H, result: `${work}/${name}_result.json` };
try { Deno.removeSync(spec.result); } catch (_e) { /* none yet */ }

const script = `// The plants package's instancing check (eidoverse/terrain/tests/plants/instances_test.mjs writes this file).
globalThis.setup = async function () {
    const V = ${JSON.stringify(spec)};
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE,
        reversedDepthBuffer: true });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.shadowMap.enabled = true;
    await renderer.init();
    globalThis._r = renderer;
    globalThis._noAutoEnhance = true;
    // a shader that does not compile says why (the backend reports only that a module is invalid)
    const dev = renderer.backend.device, mk = dev.createShaderModule.bind(dev);
    dev.createShaderModule = (d) => {
        const m = mk(d);
        m.getCompilationInfo?.().then((ci) => {
            for (const msg of ci.messages.filter((x) => x.type === 'error')) {
                const lines = String(d.code).split('\\n');
                const at = Math.max(0, (msg.lineNum ?? 1) - 1);
                console.log('[shader error] ' + (d.label ?? '') + ': ' + msg.message + ' at line ' + msg.lineNum + ': ' +
                    lines.slice(Math.max(0, at - 2), at + 2).join(' | '));
            }
        }).catch(() => {});
        return m;
    };
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0.55, 0.68, 0.85);
    const camera = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 0.1, 40000);
    globalThis._s = scene;
    globalThis._c = camera;
    const API = await import(EIDOVERSE_DIR + 'terrain/index.js');
    const PL = await import(EIDOVERSE_DIR + 'terrain/build/plants.js');
    const PI = await import(EIDOVERSE_DIR + 'terrain/build/plant_instances.js');
    const Sf = await import(EIDOVERSE_DIR + 'terrain/build/surfacing.js');
    const G = await import(EIDOVERSE_DIR + 'terrain/core/gpu.js');
    const R = await G.init({ renderer });
    const t = await API.Terrain.load(V.snap, { renderer, THREE, log: () => {} });
    const clay = Sf.clayMaterial(THREE);
    t.mesh.material = Array.isArray(t.mesh.material) ? t.mesh.material.map(() => clay) : clay;
    const spots = await PL.PlantSpots.load(V.spots);
    await spots.attach(t, null, R);
    const t0 = performance.now();
    const plants = await PI.instancePlants(spots, t, { renderer, R, log: (m) => console.log(m) });
    const instS = (performance.now() - t0) / 1000;
    const world = new THREE.Group();
    world.add(t.mesh, plants.group);
    scene.add(world);
    const sun = new THREE.DirectionalLight(0xffffff, 3.0);
    scene.add(sun, sun.target, new THREE.HemisphereLight(0xbfd4ff, 0x4a4030, 1.2));
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    const [fx, fy] = V.focus;
    const g0 = t.ring.heightAt(fx, fy);
    const cams = [
        { name: 'eye', eye: [fx, fy, g0 + 1.7], aim: [fx - 300, fy - 600, g0 + 40] },
        { name: 'off120', eye: [fx + 120, fy, t.ring.heightAt(fx + 120, fy) + 1.7], aim: [fx - 200, fy - 500, g0 + 30] },
        { name: 'over400', eye: [fx, fy - 300, g0 + 400], aim: [fx, fy, g0] },
    ];
    const toSun = [-0.45, 0.55, 0.7];
    const shaded = await plants.bindSun(new THREE.Vector3(toSun[0], toSun[2], -toSun[1]));
    globalThis._ctx = { V, t, spots, plants, cams, sun, world, instS, PI, PL, shaded, results: [], done: new Set() };
};

// the LOD rule in JavaScript doubles (test code): per species and individual the hero, card and billboard counts
function reference(ctx, cam) {
    const { spots, plants, PI } = ctx;
    const out = {};
    for (const s of plants._still) {
        const e = s.entry, rec = s.rec, n = s.n, V = s.k.length;
        const d = new Float64Array(n), vs = new Int32Array(n);
        for (let i = 0; i < n; i++) {
            const o = 12 * i, sc = rec[o + 4];
            const tn = Math.hypot(rec[o + 7], rec[o + 8]) / Math.max(rec[o + 9], 0.2);
            const zb = rec[o + 2] - sc * (e.sink + e.foot_m * Math.min(tn, 2.0));
            d[i] = Math.hypot(rec[o] - cam[0], zb - cam[2], rec[o + 1] - cam[1]);
            vs[i] = Math.min(Math.max(Math.trunc(rec[o + 10]), 0), V - 1);
        }
        const heroM = s.hero_m, heroK = s.hero_k, cardM = s.card_m;
        const use = heroM > 0 && heroK > 0;
        let rk = -1;
        if (use) {
            const sorted = Array.from(d).sort((a, b) => a - b);
            rk = Math.min(sorted[Math.min(heroK - 1, sorted.length - 1)], heroM);
        }
        const c = Array.from({ length: V }, () => [0, 0, 0]);
        for (let i = 0; i < n; i++) {
            const hero = use && d[i] <= rk;
            if (hero) c[vs[i]][0]++;
            if (d[i] <= cardM && !hero) c[vs[i]][1]++;
            if (d[i] > cardM) c[vs[i]][2]++;
        }
        out[e.name] = { counts: c, rk, cardM, heroK };
    }
    return out;
}

// the share of a small frame's pixels the plants change (the same view rendered without them)
async function plantShare(r, scene, camera, plants) {
    const w = 480, h = 270;
    const rt = new THREE.RenderTarget(w, h, { depthBuffer: true, samples: 4 });
    const px = [];
    for (const on of [true, false]) {
        plants.group.visible = on;
        r.setRenderTarget(rt);
        await r.renderAsync(scene, camera);
        px.push(await r.readRenderTargetPixelsAsync(rt, 0, 0, w, h));
    }
    r.setRenderTarget(null);
    plants.group.visible = true;
    rt.dispose();
    let diff = 0;
    for (let i = 0; i < w * h * 4; i += 4) {
        if (Math.abs(px[0][i] - px[1][i]) + Math.abs(px[0][i + 1] - px[1][i + 1]) + Math.abs(px[0][i + 2] - px[1][i + 2]) > 24) diff++;
    }
    return diff / (w * h);
}

globalThis.renderFrame = async function (tt) {
    const ctx = globalThis._ctx;
    const k = Math.max(0, Math.round(tt));
    const c = ctx.cams[Math.min(ctx.cams.length - 1, k)];
    const camera = globalThis._c;
    camera.position.set(c.eye[0], c.eye[2], -c.eye[1]);
    camera.up.set(0, 1, 0);
    camera.lookAt(c.aim[0], c.aim[2], -c.aim[1]);
    camera.updateMatrixWorld(true);
    const half = 600;
    const sc = ctx.sun.shadow.camera;
    sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half; sc.near = -5000; sc.far = 5000;
    sc.updateProjectionMatrix();
    ctx.sun.target.position.set(c.eye[0], c.eye[2], -c.eye[1]);
    ctx.sun.position.set(c.eye[0] - 450, c.eye[2] + 700, -c.eye[1] - 550);
    ctx.sun.target.updateMatrixWorld(true);
    ctx.sun.updateMatrixWorld(true);
    const r = globalThis._r;
    if (!ctx.done.has(k)) {
        ctx.done.add(k);
        await r.backend.device.queue.onSubmittedWorkDone();
        const t0 = performance.now();
        ctx.plants.update(camera);
        await r.backend.device.queue.onSubmittedWorkDone();
        const passMs = performance.now() - t0;
        if (!ctx.dumped) {            // the LOD pass' compute shaders, for reading (test output)
            ctx.dumped = true;
            const s0 = ctx.plants._still[0];
            const sh = s0.pass.nodes.map((nd) => r._nodes.getForCompute(nd).computeShader);
            Deno.writeTextFileSync(ctx.V.result.replace('_result.json', '_compute.wgsl'), sh.join('\\n// ----\\n'));
        }
        const ref = reference(ctx, c.eye);
        const got = {};
        for (const s of ctx.plants._still) {
            const cnt = new Uint32Array(await r.getArrayBufferAsync(s.pass.debug.cntA));
            const rk = new Float32Array(await r.getArrayBufferAsync(s.pass.debug.rkA))[0];
            const sel = Array.from(new Uint32Array(await r.getArrayBufferAsync(s.pass.debug.selA)));
            const lcnt = new Uint32Array(await r.getArrayBufferAsync(s.pass.debug.lcntA))[0];
            const hist = new Uint32Array(await r.getArrayBufferAsync(s.pass.debug.histA));
            const V = s.k.length;
            const counts = Array.from({ length: V }, () => [0, 0, 0]);
            s.buckets.forEach((b, i) => { counts[b.v][b.lod] = cnt[i]; });
            got[s.entry.name] = { counts, rk, sel, lcnt, histTotal: hist.reduce((a, x) => a + x, 0) };
        }
        const share = await plantShare(r, globalThis._s, camera, ctx.plants);
        const t1 = performance.now();
        await r.renderAsync(globalThis._s, camera);
        await r.backend.device.queue.onSubmittedWorkDone();
        const frameMs = performance.now() - t1;
        ctx.results.push({ camera: c.name, passMs, frameMs, share, ref, got });
        Deno.writeTextFileSync(ctx.V.result, JSON.stringify({ instance_seconds: ctx.instS, shaded: ctx.shaded,
            species: ctx.plants.species, results: ctx.results }, null, 1));
    }
    await r.renderAsync(globalThis._s, camera);
};
`;
const scriptPath = `${work}/${name}.js`, config = `${work}/${name}.json`, video = `${work}/${name}.mp4`;
Deno.writeTextFileSync(scriptPath, script);
const rel = (p) => {
    const a = S.W.norm(p), r = S.W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};
const nFrames = 3;
Deno.writeTextFileSync(config, JSON.stringify({ width: W, height: H, fps: 1, duration: nFrames, script: rel(scriptPath),
    outputVideo: rel(video), capture: { at: Array.from({ length: nFrames }, (_, k) => k), jump: true } }, null, 1));
const argv = S.W.gpuArgv([S.W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
    'eidoverse/render_scene.mjs', rel(config)], { cwd: S.W.REPO });
const log = `${work}/${name}.log`;
const code = await S.W.run(argv, { cwd: S.W.REPO, log, env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
T.ok('the render job ran', code === 0, `exit ${code}; ${log}`);
const res = S.W.exists(spec.result) ? JSON.parse(Deno.readTextFileSync(spec.result)) : null;
T.ok('the scene reported its checks', !!res, spec.result);
if (res) {
    T.ok('instancing the plan', true, `${res.instance_seconds.toFixed(1)} s; species ${JSON.stringify(res.species)}`);
    for (const r of res.results) {
        let heroTrees = 0;
        for (const [sp, g] of Object.entries(r.got)) {
            const ref = r.ref[sp];
            let worst = 0;
            g.counts.forEach((row, v) => row.forEach((x, l) => { worst = Math.max(worst, Math.abs(x - ref.counts[v][l])); }));
            T.ok(`${r.camera} / ${sp}: the LOD pass' buckets equal the rule's (hero, cards, billboards per individual)`, worst <= 1,
                `GPU ${JSON.stringify(g.counts)} vs ${JSON.stringify(ref.counts)}; hero radius ${g.rk.toFixed(3)} vs ${ref.rk.toFixed(3)} m, ` +
                `cards to ${ref.cardM.toFixed(1)} m` + (worst > 1 ? `; the threshold's bin ${g.sel[0]}, need ${g.sel[1]}, within hero_m ` +
                `${g.sel[2]} (histogram ${g.histTotal}), collected ${g.lcnt}` : ''));
            if (res.species[sp] && ref.heroK < 96) heroTrees += g.counts.reduce((a, row) => a + row[0], 0);
        }
        T.ok(`${r.camera}: at most 64 trees at their full level`, heroTrees <= 64, `${heroTrees}`);
        // the first camera's pass compiles its pipelines (reported, not graded); after it, a pass per rendered frame
        const first = r === res.results[0];
        T.ok(`${r.camera}: the LOD pass' wall time${first ? ' (its pipelines compiled in it)' : ''}`, first || r.passMs < 100,
            `${r.passMs.toFixed(2)} ms (with its submit and wait); the frame ${r.frameMs.toFixed(0)} ms`);
        T.ok(`${r.camera}: the plants draw (indirect, headless): the frame changes where they stand`, r.share >= 0.01,
            `${(100 * r.share).toFixed(1)} % of the pixels`);
    }
}
for (let k = 0; k < nFrames; k++) {
    const a = `${work}/${name}_at${k.toFixed(2)}s.png`;
    if (S.W.exists(a)) Deno.copyFileSync(a, `${out}/${name}_${['eye', 'off120', 'over400'][k]}.png`);
}
Deno.exit(S.finish(T, 'instances_test', { case: name, result: res }));
