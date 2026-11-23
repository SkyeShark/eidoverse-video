// weather_ground_test.mjs — the splash ground (weather_system.js GROUND):
// where rain rings stand. CPU half only — the baked window, its re-centring,
// invalidation and the "no ground here" answer; the shader that samples it
// needs a GPU and is checked in a render.
//   deno run --allow-all --node-modules-dir=auto eidoverse/weather_ground_test.mjs
import * as THREE from 'three/webgpu';
import * as TSL from 'three/tsl';
import { readFileSync } from 'node:fs';

globalThis.THREE = { ...THREE, ...TSL };
(0, eval)(readFileSync(new URL('./weather_system.js', import.meta.url), 'utf8'));

let failures = 0;
function check(name, cond, detail = '') {
    if (cond) console.log(`  ok   ${name}`);
    else { console.log(`  FAIL ${name} ${detail}`); failures++; }
}
const near = (a, b, eps) => Math.abs(a - b) <= eps;

const camera = new THREE.PerspectiveCamera(60, 16 / 9, 0.1, 5000);
const at = (x, y, z) => { camera.position.set(x, y, z); camera.updateMatrixWorld(true); return camera; };

async function weatherWith(opts) {
    const scene = new THREE.Scene();
    const wx = await globalThis.makeWeatherSystem({ scene, sky: null, opts });
    return { wx, scene };
}
// The baked window, decoded the way the shader reads it: R + G = height,
// B = ground present. Sample (i, j) sits at origin + (i, j) * spacing.
function decode(wx) {
    const g = wx.diagnostics.ground;
    const data = findGroundTexture(wx).image.data;
    const N = g.resolution, f = THREE.DataUtils.fromHalfFloat;
    const [cx, cz] = g.windowCenter;
    const ox = cx - g.windowHalfExtent, oz = cz - g.windowHalfExtent;
    return {
        N, ox, oz, step: g.spacingMeters,
        height: (i, j) => f(data[(j * N + i) * 4]) + f(data[(j * N + i) * 4 + 1]),
        present: (i, j) => f(data[(j * N + i) * 4 + 2]),
    };
}
// The ground texture is the one HalfFloat RGBA DataTexture the splash material samples.
function findGroundTexture(wx) {
    const seen = new Set();
    const walk = (node, depth = 0) => {
        if (!node || typeof node !== 'object' || seen.has(node) || depth > 60) return null;
        seen.add(node);
        if (node.isTextureNode && node.value?.isDataTexture && node.value.type === THREE.HalfFloatType) return node.value;
        for (const k of Object.keys(node)) {
            const v = node[k];
            if (v && typeof v === 'object') {
                if (Array.isArray(v)) { for (const e of v) { const r = walk(e, depth + 1); if (r) return r; } }
                else { const r = walk(v, depth + 1); if (r) return r; }
            }
        }
        return null;
    };
    const t = walk(wx.pipelineWarmupObjects()[1].material.positionNode);
    if (!t) throw new Error('ground texture not found in the splash positionNode');
    return t;
}

// --- 1. no ground named: the flat plane, nothing baked ----------------------
{
    console.log('1. flat default');
    const { wx } = await weatherWith({ groundY: 0.5 });
    wx.setWeather('rain', 1);
    wx.update(0, at(3, 1.7, -2));
    check('mode flat', wx.diagnostics.ground.mode === 'flat');
    check('splashes stand on groundY (groundOn 0)', wx.uniforms.groundOn.value === 0);
    check('splashes visible (groundVis 1)', wx.uniforms.groundVis.value === 1);
    check('nothing baked', wx.diagnostics.ground.bakes === 0);
    wx.dispose();
}

// --- 2. a named ground: the first frame of rain bakes, and it reads back ----
const slope = (x, z) => 40 + 0.35 * x - 0.2 * z + 2 * Math.sin(x * 0.3) * Math.cos(z * 0.2);
{
    console.log('2. heightfield bake');
    const { wx } = await weatherWith({ groundHeightAt: slope });
    check('mode heightfield', wx.diagnostics.ground.mode === 'heightfield');
    check('hidden before any bake', wx.uniforms.groundVis.value === 0);
    wx.update(0, at(3, 50, -2));
    check('no rain, no bake', wx.diagnostics.ground.bakes === 0);
    wx.setWeather('rain', 1);
    wx.update(0.016, at(3, 50, -2));
    const g = wx.diagnostics.ground;
    check('baked on the first rainy frame', g.bakes === 1 && g.lastBakeUrgent === true, JSON.stringify(g));
    check('groundOn 1, groundVis 1', wx.uniforms.groundOn.value === 1 && wx.uniforms.groundVis.value === 1);
    const d = decode(wx);
    check('origin uniform = window min corner',
        near(wx.uniforms.groundOrigin.value.x, d.ox, 1e-9) && near(wx.uniforms.groundOrigin.value.y, d.oz, 1e-9));
    check('window centred on the camera (within a sample)', near(g.windowCenter[0], 3, d.step) && near(g.windowCenter[1], -2, d.step));
    check('window covers the splash tile (45 m) plus margin', g.windowHalfExtent > 45);
    let worst = 0;
    for (let j = 0; j < d.N; j += 7) for (let i = 0; i < d.N; i += 5) {
        worst = Math.max(worst, Math.abs(d.height(i, j) - slope(d.ox + i * d.step, d.oz + j * d.step)));
    }
    check('hi+lo half pair reads back the height to < 2 mm (heights ~10-80 m)', worst < 0.002, `worst ${worst}`);
    check('every sample present', d.present(0, 0) === 1 && d.present(d.N - 1, d.N - 1) === 1 && g.absentSamples === 0);
    wx.dispose();
}

// --- 3. "no ground here": null/NaN/throw → absent, filled with the mean ----
{
    console.log('3. absent ground');
    const edge = (x, z) => (x > 10 ? null : z > 30 ? NaN : x < -40 ? (() => { throw new Error('void'); })() : 7);
    const warn = console.warn; let warned = 0; console.warn = () => { warned++; };
    const { wx } = await weatherWith({ groundHeightAt: edge });
    wx.setWeather('rain', 1);
    wx.update(0, at(0, 2, 0));
    console.warn = warn;
    const d = decode(wx), g = wx.diagnostics.ground;
    const col = (x) => Math.round((x - d.ox) / d.step), row = (z) => Math.round((z - d.oz) / d.step);
    check('null past x=10 is absent', d.present(col(20), row(0)) === 0);
    check('NaN past z=30 is absent', d.present(col(0), row(40)) === 0);
    check('a throw is absent, warned once', d.present(col(-50), row(0)) === 0 && warned === 1 && g.heightFaults > 1);
    check('present ground present', d.present(col(0), row(0)) === 1 && near(d.height(col(0), row(0)), 7, 1e-3));
    check('absent texels carry the present mean (7), not 0', near(d.height(col(20), row(0)), 7, 1e-3));
    check('absentSamples counted', g.absentSamples > 0 && g.absentSamples < d.N * d.N);
    wx.dispose();
}

// --- 4. drifting: the window follows over a few frames, never mid-swap ------
{
    console.log('4. re-centre while walking');
    const { wx } = await weatherWith({ groundHeightAt: slope });
    wx.setWeather('rain', 1);
    wx.update(0, at(0, 50, 0));
    const g = wx.diagnostics.ground, margin = g.windowHalfExtent - 45;
    const c0 = [...g.windowCenter];
    wx.update(0.016, at(margin * 0.4, 50, 0));
    check('inside half the margin: no new bake', g.bakes === 1);
    let frames = 0;
    const x1 = margin * 0.6;
    do { wx.update(0.032 + frames * 0.016, at(x1, 50, 0)); frames++; } while (g.bakes === 1 && frames < 20);
    check('past half the margin: re-centred', g.bakes === 2 && g.lastBakeUrgent === false);
    check('spread over 4 frames', frames === 4, `took ${frames}`);
    check('kept the old window until the new one was whole', g.windowCenter[0] !== c0[0] && near(g.windowCenter[0], x1, g.spacingMeters));
    check('stayed visible throughout', wx.uniforms.groundVis.value === 1);
    // the lattice: re-centred windows sample the SAME world points
    const d = decode(wx);
    const shift = (d.ox - (c0[0] - g.windowHalfExtent)) / d.step;
    check('window origins share one lattice', near(shift, Math.round(shift), 1e-6), `shift ${shift} samples`);
    wx.dispose();
}

// --- 5. a teleport bakes at once ---------------------------------------------
{
    console.log('5. teleport');
    const { wx } = await weatherWith({ groundHeightAt: slope });
    wx.setWeather('rain', 1);
    wx.update(0, at(0, 50, 0));
    wx.update(0.016, at(800, 300, -650));
    const g = wx.diagnostics.ground;
    check('same frame, urgent', g.bakes === 2 && g.lastBakeUrgent === true);
    check('centred at the destination', near(g.windowCenter[0], 800, g.spacingMeters) && near(g.windowCenter[1], -650, g.spacingMeters));
    check('visible', wx.uniforms.groundVis.value === 1);
    wx.dispose();
}

// --- 6. deformable ground: invalidate re-reads the same function -------------
{
    console.log('6. invalidateGround / setGroundHeightAt');
    let lift = 0;
    const live = (x, z) => slope(x, z) + lift;
    const { wx } = await weatherWith({ groundHeightAt: live });
    wx.setWeather('rain', 1);
    wx.update(0, at(0, 50, 0));
    lift = 2.5;
    wx.invalidateGround();
    for (let f = 1; f <= 4; f++) wx.update(f * 0.016, at(0, 50, 0));
    const g = wx.diagnostics.ground;
    check('re-baked after invalidate', g.bakes === 2 && g.lastBakeUrgent === false);
    const d = decode(wx);
    check('new shape read back', near(d.height(10, 10), slope(d.ox + 10 * d.step, d.oz + 10 * d.step) + 2.5, 2e-3));
    // a different function bakes on the next frame
    wx.setGroundHeightAt(() => -12);
    wx.update(0.1, at(0, 50, 0));
    check('new function: urgent bake', g.bakes === 3 && g.lastBakeUrgent === true && near(decode(wx).height(5, 5), -12, 1e-3));
    wx.setGroundHeightAt(null);
    wx.update(0.2, at(0, 50, 0));
    check('null: back to flat', g.mode === 'flat' && wx.uniforms.groundOn.value === 0 && wx.uniforms.groundVis.value === 1);
    wx.dispose();
}

// --- 7. disposal releases the texture -----------------------------------------
{
    console.log('7. dispose');
    const { wx } = await weatherWith({ groundHeightAt: slope });
    const tex = findGroundTexture(wx);
    let disposed = false;
    tex.addEventListener('dispose', () => { disposed = true; });
    wx.dispose();
    check('ground texture disposed', disposed);
}

if (failures) {
    console.log(`\n${failures} FAILED`);
    (globalThis.Deno?.exit ?? process.exit)(1);
}
console.log('\nall ok');
