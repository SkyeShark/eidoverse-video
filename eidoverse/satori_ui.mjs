// 3D scene + UI overlay via Satori (HTML+CSS → SVG → RGBA pixels).
// This mirrors production more honestly than deno_render_with_ui.mjs:
//   - Production: agent writes HTML+CSS in #ui-overlay, browser layouts it,
//     foreignObject + Image roundtrip rasterizes to CanvasTexture.
//   - Here: agent writes JSX-like tree (HTML+CSS), Satori layouts it to SVG
//     using Yoga + a real text shaper, then resvg rasterizes SVG → RGBA.
// The agent's authoring surface is HTML+CSS in BOTH cases.

import { DOMParser } from "jsr:@b-fuze/deno-dom";
import satori from "npm:satori@0.10.13";
import { Resvg } from "npm:@resvg/resvg-js@2.6.2";

const WIDTH = 1280;
const HEIGHT = 720;
const FPS = 30;
const DURATION_S = 4;
const TOTAL_FRAMES = FPS * DURATION_S;

// --- Font load (Satori needs a real font to shape text) ---
// Use the same Inter weights production ships; fall back to DejaVu in container.
async function loadFont(path) {
    const data = await Deno.readFile(path);
    return data.buffer;
}
const fontRegular = await loadFont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf');
const fontBold    = await loadFont('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf');
console.log('[satori] fonts loaded');

// --- WebGPU + three.js scaffolding (same as deno_render_with_dom.mjs) ---
const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const device = await adapter.requestDevice();

class FakeGPUCanvasContext {
    constructor(canvas) { this.canvas = canvas; this._texture = null; }
    configure(opts) {
        if (this._texture) try { this._texture.destroy(); } catch {}
        this._texture = opts.device.createTexture({
            size: [this.canvas.width, this.canvas.height, 1],
            format: opts.format,
            usage: opts.usage | GPUTextureUsage.COPY_SRC,
        });
    }
    unconfigure() { if (this._texture) try { this._texture.destroy(); } catch {}; this._texture = null; }
    getCurrentTexture() { return this._texture; }
}

const doc = new DOMParser().parseFromString(
    '<html><head></head><body><canvas id="c"></canvas></body></html>', 'text/html'
);
const canvas = doc.getElementById('c');
canvas.width = WIDTH;
canvas.height = HEIGHT;
canvas.style = {};
const fakeCtx = new FakeGPUCanvasContext(canvas);
canvas.getContext = (t) => t === 'webgpu' ? fakeCtx : null;

globalThis.window ??= globalThis;
globalThis.self ??= globalThis;
globalThis.document = doc;
globalThis.HTMLCanvasElement = canvas.constructor;
globalThis.GPUCanvasContext ??= FakeGPUCanvasContext;
globalThis.requestAnimationFrame ??= (cb) => setTimeout(() => cb(performance.now()), 16);
globalThis.cancelAnimationFrame ??= (id) => clearTimeout(id);

const THREE = await import('npm:three@0.170.0/webgpu');

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x224466);
const camera = new THREE.PerspectiveCamera(50, WIDTH/HEIGHT, 0.1, 100);
camera.position.set(2.5, 2, 3); camera.lookAt(0, 0, 0);
scene.add(new THREE.AmbientLight(0xffffff, 0.5));
const dl = new THREE.DirectionalLight(0xffffff, 2.5); dl.position.set(3, 5, 4); scene.add(dl);
const cube = new THREE.Mesh(
    new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshStandardMaterial({ color: 0xff2d95, metalness: 0.4, roughness: 0.3 })
);
cube.position.y = 0.5; scene.add(cube);
const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(8, 8),
    new THREE.MeshStandardMaterial({ color: 0x334455, roughness: 0.8 })
);
ground.rotation.x = -Math.PI/2; scene.add(ground);

const renderer = new THREE.WebGPURenderer({ canvas, antialias: false, adapter, device });
renderer.setSize(WIDTH, HEIGHT);
renderer.outputColorSpace = THREE.SRGBColorSpace;
await renderer.init();
console.log('[satori] renderer init OK');

// --- UI authored as a JSX-like tree (what an agent would write) ---
// Satori accepts the same React-element shape that JSX compiles to.
// In production this would be the HTML+CSS the agent wrote into
// #ui-overlay; here we hand-build the same node tree.
function buildUiElement(t) {
    const seconds = t.toFixed(2);
    const accentAlpha = 0.5 + 0.5 * Math.sin(t * 4);
    return {
        type: 'div',
        props: {
            style: {
                display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                width: '100%', height: '100%',
            },
            children: [
                // top title bar
                {
                    type: 'div',
                    props: {
                        style: {
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            background: 'rgba(8,16,32,0.78)', padding: '20px 40px', height: '84px',
                        },
                        children: [
                            { type: 'div', props: { style: { color: '#ff2d95', fontSize: 36, fontWeight: 900 }, children: 'DENO + WEBGPU' } },
                            { type: 'div', props: { style: { color: '#00d4ff', fontSize: 28 }, children: `${seconds}s` } },
                        ],
                    },
                },
                // lower-third strip
                {
                    type: 'div',
                    props: {
                        style: {
                            display: 'flex', flexDirection: 'row',
                            background: 'rgba(8,16,32,0.7)', height: '120px', position: 'relative',
                        },
                        children: [
                            { type: 'div', props: { style: { width: '6px', height: '120px', background: '#ff2d95' } } },
                            {
                                type: 'div',
                                props: {
                                    style: { display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 34px', flexGrow: 1 },
                                    children: [
                                        { type: 'div', props: { style: { color: 'white', fontSize: 32, fontWeight: 700 }, children: 'three.js render via Deno + wgpu-rs' } },
                                        { type: 'div', props: { style: { color: '#aaaaaa', fontSize: 20, marginTop: 8 }, children: 'UI overlay laid out by Satori, rasterised by resvg, composited over 3D' } },
                                    ],
                                },
                            },
                            // accent dot — absolute positioned at bottom-right
                            {
                                type: 'div',
                                props: {
                                    style: {
                                        position: 'absolute', right: '40px', top: '40px',
                                        width: '40px', height: '40px', borderRadius: '20px',
                                        background: '#00d4ff', opacity: accentAlpha,
                                    },
                                },
                            },
                        ],
                    },
                },
            ],
        },
    };
}

// --- ffmpeg sink ---
const ffmpeg = new Deno.Command('ffmpeg', {
    args: ['-y', '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'rgba',
           '-s', `${WIDTH}x${HEIGHT}`, '-r', String(FPS), '-i', '-',
           '-c:v', 'h264_nvenc', '-preset', 'fast', '-pix_fmt', 'yuv420p',
           'work/deno_render_with_satori.mp4'],
    stdin: 'piped', stdout: 'inherit', stderr: 'piped',
}).spawn();
const ffmpegStdin = ffmpeg.stdin.getWriter();

const bytesPerRow = Math.ceil((WIDTH * 4) / 256) * 256;
const stageBuf = device.createBuffer({
    size: bytesPerRow * HEIGHT,
    usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
});
const sceneFrame = new Uint8Array(WIDTH * HEIGHT * 4);
const composite = new Uint8Array(WIDTH * HEIGHT * 4);

const tStart = performance.now();
for (let i = 0; i < TOTAL_FRAMES; i++) {
    const t = i / FPS;
    cube.rotation.x = t * 0.8; cube.rotation.y = t * 1.2;
    camera.position.x = Math.sin(t * 0.5) * 3;
    camera.position.z = Math.cos(t * 0.5) * 3;
    camera.lookAt(0, 0.5, 0);

    await renderer.renderAsync(scene, camera);

    // 3D pixels → sceneFrame
    const tex = fakeCtx.getCurrentTexture();
    const enc = device.createCommandEncoder();
    enc.copyTextureToBuffer({ texture: tex },
        { buffer: stageBuf, bytesPerRow, rowsPerImage: HEIGHT },
        [WIDTH, HEIGHT, 1]);
    device.queue.submit([enc.finish()]);
    await stageBuf.mapAsync(GPUMapMode.READ);
    const padded = new Uint8Array(stageBuf.getMappedRange());
    // WebGPU copyTextureToBuffer + resvg output are both top-down (row 0 = top).
    // Direct row copy. No flip on either side, no -vf vflip on ffmpeg.
    for (let y = 0; y < HEIGHT; y++) {
        sceneFrame.set(padded.subarray(y * bytesPerRow, y * bytesPerRow + WIDTH * 4), y * WIDTH * 4);
    }
    stageBuf.unmap();

    // UI tree → SVG via Satori, then SVG → RGBA via resvg
    const svg = await satori(buildUiElement(t), {
        width: WIDTH, height: HEIGHT,
        fonts: [
            { name: 'DejaVu Sans', data: fontRegular, weight: 400, style: 'normal' },
            { name: 'DejaVu Sans', data: fontBold,    weight: 900, style: 'normal' },
        ],
    });
    const uiPixmap = new Resvg(svg, { fitTo: { mode: 'width', value: WIDTH } }).render();
    const uiPixels = uiPixmap.pixels;  // RGBA, premultiplied

    // alpha-blend UI over scene
    for (let p = 0; p < composite.length; p += 4) {
        const ua = uiPixels[p + 3];
        if (ua === 0) {
            composite[p]   = sceneFrame[p];
            composite[p+1] = sceneFrame[p+1];
            composite[p+2] = sceneFrame[p+2];
            composite[p+3] = sceneFrame[p+3];
        } else {
            const inv = 1 - ua / 255;
            composite[p]   = (uiPixels[p]   + sceneFrame[p]   * inv) | 0;
            composite[p+1] = (uiPixels[p+1] + sceneFrame[p+1] * inv) | 0;
            composite[p+2] = (uiPixels[p+2] + sceneFrame[p+2] * inv) | 0;
            composite[p+3] = 255;
        }
    }

    await ffmpegStdin.write(composite);

    if (i % 15 === 0 || i === TOTAL_FRAMES - 1) {
        const elapsed = (performance.now() - tStart) / 1000;
        console.log(`[satori] frame ${i+1}/${TOTAL_FRAMES} — ${elapsed.toFixed(2)}s, ${((i+1)/elapsed).toFixed(1)} fps`);
    }
}

await ffmpegStdin.close();
const result = await ffmpeg.status;
console.log('[satori] ffmpeg exit:', result.code);
console.log('[satori] DONE — output: work/deno_render_with_satori.mp4');
