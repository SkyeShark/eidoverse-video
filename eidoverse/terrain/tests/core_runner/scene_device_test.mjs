// The scene's device and the terrain runner (PORT_PLAN.md 4.2, 4.7, 8.2 P1): eidoverse/render_common.mjs
// setupRenderer (the device render_scene.mjs installs as GPU_DEVICE) asks for the limits the runner needs; the runner
// takes that device as GPU_DEVICE and passes its self test there; the 46 kernel fixture cases and a u32(0) kernel run
// on it through GPUDevice.prototype.createShaderModule (past render_common's wrapper); and the runner's kernels and a
// three.js WebGPURenderer's frames interleave on it.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/core_runner/scene_device_test.mjs
//
// (the repository's deno.json and lock, which pin render_common.mjs's packages; --frozen never rewrites the lock).
// On a shared machine put $EIDO_GPU_WRAP in front of the deno command.

import { setupRenderer } from '../../../render_common.mjs';
import * as G from '../../core/gpu.js';
import { prims } from '../../core/prims.js';
import { Checks } from './_common.mjs';
import { twinChecks, twinFixtures, u32ZeroCheck } from './_twins.mjs';

const T = new Checks('core_runner/scene_device');
const S = await setupRenderer(64, 48);
const lim = S.device.limits, offer = S.adapter.limits;
T.extra.limits = { maxStorageBuffersPerShaderStage: lim.maxStorageBuffersPerShaderStage, maxComputeWorkgroupStorageSize: lim.maxComputeWorkgroupStorageSize };
T.ok('render_common: the scene device has the adapter\'s storage buffers per stage (9 or more)',
    lim.maxStorageBuffersPerShaderStage === offer.maxStorageBuffersPerShaderStage && lim.maxStorageBuffersPerShaderStage >= G.MIN_STORAGE_BUFFERS,
    `${lim.maxStorageBuffersPerShaderStage} of ${offer.maxStorageBuffersPerShaderStage}`);
T.ok('render_common: the scene device has the adapter\'s workgroup storage',
    lim.maxComputeWorkgroupStorageSize === offer.maxComputeWorkgroupStorageSize, `${lim.maxComputeWorkgroupStorageSize} bytes`);

globalThis.GPU_DEVICE = S.device;                          // what render_scene.mjs does
const R = await G.init();
T.ok('init: the runner takes GPU_DEVICE (and passes its self test there)', R.device === S.device);
T.ok("render_common: the scene device's createShaderModule is render_common's wrapper (what the runner steps round)",
    Object.prototype.hasOwnProperty.call(S.device, 'createShaderModule'));

// the kernel fixtures and a u32(0) kernel on this device, as runner_test.mjs runs them on a plain one (plan 4.7, C7)
await u32ZeroCheck(R, T, 'the render_common device');
const FIX = twinFixtures(Deno.args[0]);
if (FIX) {
    const r = await twinChecks(R, T, FIX, 'the render_common device');
    T.extra.twin_cases_worst = r.worst;
    T.extra.world_noise_ratio = r.worldNoise;
    T.extra.twin_fixture_versions = r.versions;
}

const THREE = S.THREE;
const renderer = new THREE.WebGPURenderer({ canvas: S.canvas, adapter: S.adapter, device: S.device, antialias: false });
await renderer.init();
renderer.setSize(64, 48, false);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 64 / 48, 0.1, 100);
camera.position.set(0, 1, 4);
camera.lookAt(0, 0, 0);
scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicNodeMaterial({ color: 0xff8800 })));

// a frame, then the runner's kernels (the fill and a blur through prims), then another frame, then the kernels again
const P = prims(R);
const n = 64, h = new Float32Array(n * n);
for (let i = 0; i < n * n; i++) {                          // test data: a bowl with a lip (JS per cell: tests only)
    const x = (i % n) - n / 2, y = Math.floor(i / n) - n / 2, r = Math.hypot(x, y);
    h[i] = r < 20 ? 100 - 30 * Math.cos(r / 20 * Math.PI) : 130 + 0.1 * r;
}
renderer.render(scene, camera);
const hf = R.field(n, n, 1, h);
const a = await P.fillDepressions(hf);
renderer.render(scene, camera);
const b = await P.fillDepressions(hf);
const blur = P.gaussianBlur(a.filled, 2.0);
const [fa, fb] = await R.readAll([a.filled, b.filled]);
await R.idle();
let filled = 0;
for (let i = 0; i < n * n; i++) if (fa[i] > h[i]) filled++;
T.ok('interleaved with three.js frames on one device: the fill fills the bowl, the same both times',
    filled > 900 && fa.every((v, i) => v === fb[i]), `${filled} cells filled`);
for (const f of [hf, a.filled, b.filled, blur]) f.destroy();
renderer.dispose();

const code = T.done('scene_device_test.json');
Deno.exit(code);
