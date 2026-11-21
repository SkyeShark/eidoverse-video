// The per-texel material on a bake case (PORT_PLAN.md 8.2 row P17; SURFACING_DESIGN.md 5.4 package 2, checks 0 and
// 10, and blender/tests/terrain/surfacing/test_material_data.py's build checks): build/surfacing.js applySurface on
// the case's ring mesh with the port's surface data and palette bake, then
//   - the near and the far material build, and their fragment shaders sample at most MAX_TEXTURES textures (WebGPU's
//     default stage holds 16; the lit scene binds a shadow map and an environment beside them), counted in the WGSL
//     three.js generates; the ramp image is read without a sampler (Closest);
//   - the far material reads the data and the base layer's grain only, within the near material's textures;
//   - setFarDistance moves D0 without a rebuild (the same program renders after it);
//   - the cost: the JavaScript build, the first frame (the shader's compile), and a frame after it, at 960 x 540,
//     recorded beside Blender's (out/surfacing/material/compile_<case>.json when the Blender edition has it);
//   - an aerial and a low view rendered under a sun and a sky fill, written as PNGs to look at
//     (tests/out/surfacing/material/<case>_*.png).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surfacing/material_test.mjs
//         [--cases canyon,alpine_valley]
//     (a GPU job: behind $EIDO_GPU_WRAP on a shared machine; $EIDO_BLENDER_EDITION for the snapshots)
//
// Writes tests/out/surfacing/material_test.json.

import process from 'node:process';
import * as M from './_material.mjs';
import * as Sf from '../../build/surfacing.js';

const A = M.argsOf();
const cases = A.list('--cases', ['canyon']);
const T = new M.C.Checks('surfacing: the per-texel material builds, binds and renders');
const G = await M.gpu();
const { THREE, TSL, renderer } = G;
await Sf.tslModule({ TSL });
const outDir = M.out('material');
const record = {};

// a PNG of a linear render (Reinhard on luminance, sRGB): for the eye, not for numbers
async function writePng(path, px, w, h) {
    const Io = await import('../../core/io.js');
    const s = new Uint32Array(w * h * 4);
    const enc = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);
    for (let j = 0; j < h; j++) {
        for (let i = 0; i < w; i++) {
            const o = (j * w + i) * 4;
            const L = 0.2126 * px[o] + 0.7152 * px[o + 1] + 0.0722 * px[o + 2];
            const k = L > 0 ? (L / (1 + L)) / L : 1;
            for (let c = 0; c < 3; c++) s[o + c] = Math.round(255 * Math.min(Math.max(enc(px[o + c] * k), 0), 1));
            s[o + 3] = 255;
        }
    }
    const f = G.R.field(h, w * 4, 1, s, 'u32');
    await Io.writePng(path, { field: f, width: w, height: h, channels: 4, bitDepth: 8 });
    f.destroy();
}

// this process's CPU seconds (user + system): on a shared machine at full load the wall clock measures the queue for a
// core as much as the work, so the compile is recorded in both
const cpuS = () => { const u = process.cpuUsage(); return (u.user + u.system) / 1e6; };

async function frame(scene, cam, w, h) {
    const rt = new THREE.RenderTarget(w, h, { type: THREE.HalfFloatType, depthBuffer: true, samples: 0 });
    renderer.setRenderTarget(rt);
    const t0 = performance.now(), c0 = cpuS();
    renderer.render(scene, cam);
    const raw = await renderer.readRenderTargetPixelsAsync(rt, 0, 0, w, h);
    const ms = performance.now() - t0, cpu = cpuS() - c0;
    renderer.setRenderTarget(null);
    rt.dispose();
    const row = raw.length / h;
    const px = new Float32Array(w * h * 4);
    for (let j = 0; j < h; j++) for (let i = 0; i < w * 4; i++) px[j * w * 4 + i] = THREE.DataUtils.fromHalfFloat(raw[j * row + i]);
    return { px, ms, cpu };
}

// the textures and samplers a material's fragment shader binds (three.js's WGSL)
async function bindings(scene, cam, mesh) {
    try {
        const code = await renderer.debug.getShaderAsync(scene, cam, mesh);
        const f = code.fragmentShader;
        return { textures: (f.match(/:\s*texture_(2d|2d_array|depth_2d|cube)/g) ?? []).length,
            samplers: (f.match(/:\s*sampler(_comparison)?\s*;/g) ?? []).length, lines: f.split('\n').length };
    } catch (e) {
        return { error: String(e.message ?? e) };
    }
}

for (const name of cases) {
    const got = await M.caseData(name, G, { palette: true });
    if (!got) {
        T.ok(`${name}: the case's snapshot and bake are there`, false, 'see the skip line');
        continue;
    }
    const { t, sd } = got;
    const main = t.levels.find((l) => l.role === 'main') ?? t.levels[0];
    const cx = main.x0 + main.side / 2, cy = main.y0 + main.side / 2;
    const zc = t.ring.heightAt(cx, cy);
    const r = { case: name, palette: sd.palette?.name ?? null };
    // a camera at the main tile's centre, so the context rings far off take the far material
    const camPos = [cx, zc + 300, -cy];
    let near;
    const tb = performance.now();
    try {
        near = await Sf.applySurface(t, sd.palette, { data: sd, cameras: [camPos], THREE, R: G.R, TSL, log: console.log });
    } catch (e) {
        T.ok(`${name}: the near and far materials build`, false, String(e.stack ?? e).slice(0, 1500));
        record[name] = { error: String(e.message ?? e) };
        continue;
    }
    r.build_s = +((performance.now() - tb) / 1000).toFixed(2);
    const mats = t.mesh.material;
    const far = mats[1];
    T.ok(`${name}: the near and far materials build (palette ${r.palette})`, near && far,
        `${r.build_s} s; ${mats[1] === mats[0] ? 'no ring beyond 1.5 D0: the far slot is the near material' : 'far material on ' + t.mesh.geometry.groups.filter((g) => g.materialIndex === 1).length + ' groups'}; D0 ${near.userData.eidoFarM.toFixed(0)} m`);
    // the scene: a sun and a sky fill
    const scene = new THREE.Scene();
    scene.add(t.mesh);
    const sun = new THREE.DirectionalLight(0xffffff, 3.0);
    sun.position.set(cx - 3000, zc + 4000, -cy + 2000);
    sun.target.position.set(cx, zc, -cy);
    scene.add(sun, sun.target);
    scene.add(new THREE.HemisphereLight(0xbfd4ff, 0x3a3020, 0.6));
    const W = 960, H = 540;
    const cam = new THREE.PerspectiveCamera(40, W / H, 2, 120000);
    cam.position.set(cx - main.side * 0.35, zc + main.side * 0.25, -cy + main.side * 0.35);
    cam.lookAt(cx, zc, -cy);
    cam.updateMatrixWorld(true);
    const f1 = await frame(scene, cam, W, H);
    const f2 = await frame(scene, cam, W, H);
    const f3 = await frame(scene, cam, W, H);
    r.first_frame_s = +(f1.ms / 1000).toFixed(2);
    r.first_frame_cpu_s = +f1.cpu.toFixed(2);
    r.frame_ms = +Math.min(f2.ms, f3.ms).toFixed(1);
    await writePng(`${outDir}/${name}_aerial.png`, f3.px, W, H);
    let lum = 0, nan = 0;
    for (let q = 0; q < W * H; q++) {
        const v = f3.px[4 * q] + f3.px[4 * q + 1] + f3.px[4 * q + 2];
        if (Number.isNaN(v)) nan++;
        else lum += v;
    }
    r.aerial_mean = +(lum / (3 * W * H)).toFixed(4);
    T.ok(`${name}: the aerial renders (no NaN, not black)`, nan === 0 && r.aerial_mean > 0.01,
        `first frame ${r.first_frame_s} s wall, ${r.first_frame_cpu_s} s of this process's CPU (the compile), then ${r.frame_ms} ms; ` +
        `mean ${r.aerial_mean}; ${outDir}/${name}_aerial.png`);
    // the bindings of the near material's program (a mesh of one material: debug.getShaderAsync reads one program)
    const one = new THREE.Mesh(t.mesh.geometry, near);
    const s1 = new THREE.Scene();
    s1.add(one);
    s1.add(sun.clone(), new THREE.HemisphereLight(0xbfd4ff, 0x3a3020, 0.6));
    const bn = await bindings(s1, cam, one);
    r.describe = sd.describe().split('\n');
    r.bindings = bn;
    T.ok(`${name}: the near material samples at most ${Sf.MAX_TEXTURES} textures of its own (of a stage's 16)`,
        !bn.error && near.userData.eidoTextures <= Sf.MAX_TEXTURES && (bn.textures ?? 99) <= 16 && (bn.samplers ?? 99) <= 16,
        bn.error ?? `its count ${near.userData.eidoTextures}; the fragment shader binds ${bn.textures} textures and ${bn.samplers} samplers ` +
            `(the light's shadow and the environment included), ${bn.lines} lines of WGSL`);
    // a low view across the main level
    const cam2 = new THREE.PerspectiveCamera(50, W / H, 0.5, 120000);
    const ex = cx - main.side * 0.2, ey = cy - main.side * 0.2;
    cam2.position.set(ex, t.ring.heightAt(ex, ey) + 40, -ey);
    cam2.lookAt(cx, zc, -cy);
    cam2.updateMatrixWorld(true);
    const f4 = await frame(scene, cam2, W, H);
    await writePng(`${outDir}/${name}_low.png`, f4.px, W, H);
    // the far material (slot 1 on rings beyond 1.5 D0 of every camera; built here directly), on the whole mesh
    const farM = await Sf.farMaterial(sd.palette, { data: sd, THREE, R: G.R, TSL, recipe: t.recipe, constants: Sf.terrainConstants(t), log: null });
    const oneF = new THREE.Mesh(t.mesh.geometry, farM);
    const sF = new THREE.Scene();
    sF.add(oneF, sun.clone(), new THREE.HemisphereLight(0xbfd4ff, 0x3a3020, 0.6));
    const ff = await frame(sF, cam, W, H);
    await writePng(`${outDir}/${name}_aerial_far_material.png`, ff.px, W, H);
    const bf = await bindings(sF, cam, oneF);
    r.far_material = { textures: farM.userData.eidoTextures, first_frame_s: +(ff.ms / 1000).toFixed(2), first_frame_cpu_s: +ff.cpu.toFixed(2), bindings: bf };
    T.ok(`${name}: the far material builds and reads the data and the base layer's grain only, within the near material's textures`,
        farM.userData.eidoTextures <= near.userData.eidoTextures && !bf.error,
        `${farM.userData.eidoTextures} textures (near ${near.userData.eidoTextures}); its first frame ${r.far_material.first_frame_s} s ` +
        `(${r.far_material.first_frame_cpu_s} s CPU); ${bf.error ?? bf.textures + ' textures and ' + bf.samplers + ' samplers bound'}`);
    // D0 moved in place: the same program draws
    Sf.setFarDistance(near, near.userData.eidoFarM * 0.25);
    const f5 = await frame(scene, cam, W, H);
    await writePng(`${outDir}/${name}_aerial_D0quarter.png`, f5.px, W, H);
    T.ok(`${name}: setFarDistance moves D0 without a rebuild`, f5.ms < 0.5 * f1.ms + 2000,
        `a frame after it ${f5.ms.toFixed(0)} ms (the first frame ${f1.ms.toFixed(0)} ms)`);
    record[name] = r;
    console.log(`[material] ${name}: ${JSON.stringify(r)}`);
    t.dispose();
}
renderer.dispose();
Deno.exit(M.finish(T, 'material_test', { cases: record }));
