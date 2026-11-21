// A probe for the material (PORT_PLAN.md 10.3, P17): does three r184's mipmap generation fill the mips of a
// THREE.DataArrayTexture on this edition's device (RGBA8, RGBA8 sRGB, RGBA16F), and does a TSL read of one texture
// in two places bind it once? The reader (build/surfacing.js) reads every data family through its mips; the edition's
// render_scene.mjs notes that the auto-mipmap pass gave zero-sampled mips on wgpu + Mesa.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surfacing/probe_mips.mjs
//
// Prints one line per case: the mean of a 16 x 16 x 2 checker of 8-texel squares read at mip 0 (the squares), mip 4
// (every texel the mean of four squares: 0.5 linear) and mip 7 (the whole layer's mean).

import { setupRenderer } from '../../../render_common.mjs';

const RS = await setupRenderer(64, 64);
const THREE = RS.THREE;
const TSL = await import('three/tsl');
const renderer = new THREE.WebGPURenderer({ canvas: RS.canvas, adapter: RS.adapter, device: RS.device, antialias: false });
await renderer.init();
const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 2);
cam.position.set(0, 0, 1);

const S = 256;
function makeTex(kind, mips = true) {
    const n = S * S * 4 * 2;
    const half = kind === 'half';
    const data = half ? new Uint16Array(n) : new Uint8Array(n);
    const ONE = half ? 0x3C00 : 255;
    for (let l = 0; l < 2; l++) {
        for (let y = 0; y < S; y++) {
            for (let x = 0; x < S; x++) {
                const on = l === 1 ? ((x >> 3) + (y >> 3)) % 2 : 1;
                const o = ((l * S + y) * S + x) * 4;
                data[o] = on ? ONE : 0;
                data[o + 1] = on ? 0 : ONE;
                data[o + 2] = l === 0 ? ONE : 0;
                data[o + 3] = ONE;
            }
        }
    }
    const t = new THREE.DataArrayTexture(data, S, S, 2);
    t.format = THREE.RGBAFormat;
    t.type = half ? THREE.HalfFloatType : THREE.UnsignedByteType;
    t.colorSpace = kind === 'srgb' ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.magFilter = THREE.LinearFilter;
    t.minFilter = mips ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
    t.generateMipmaps = mips;
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    t.flipY = false;
    t.anisotropy = 16;
    t.needsUpdate = true;
    return t;
}

async function readLevel(tex, level, layer) {
    const s0 = TSL.texture(tex, TSL.uv());
    const s = (level === null ? s0 : s0.level(TSL.float(level))).depth(TSL.int(layer));
    const mat = new THREE.MeshBasicNodeMaterial();
    mat.colorNode = TSL.vec4(s.rgb, 1.0);
    mat.toneMapped = false;
    const scene = new THREE.Scene();
    const geo = new THREE.PlaneGeometry(2, 2);
    scene.add(new THREE.Mesh(geo, mat));
    // (a FloatType target is downgraded to rgba16float by render_common.mjs's device patch: half it is)
    const rt = new THREE.RenderTarget(32, 32, { type: THREE.HalfFloatType, depthBuffer: false });
    renderer.setRenderTarget(rt);
    renderer.render(scene, cam);
    const raw = await renderer.readRenderTargetPixelsAsync(rt, 0, 0, 32, 32);
    const px = Float32Array.from(raw, (h) => THREE.DataUtils.fromHalfFloat(h));
    renderer.setRenderTarget(null);
    rt.dispose();
    mat.dispose();
    geo.dispose();
    let r = 0, g = 0, b = 0, n = 0, lo = Infinity, hi = -Infinity;
    const row = px.length / 32;
    for (let y = 0; y < 32; y++) {
        for (let x = 0; x < 32; x++) {
            const o = y * row + x * 4;
            r += px[o]; g += px[o + 1]; b += px[o + 2]; n++;
            lo = Math.min(lo, px[o]); hi = Math.max(hi, px[o]);
        }
    }
    return `r ${(r / n).toFixed(4)} (${lo.toFixed(3)}..${hi.toFixed(3)}) g ${(g / n).toFixed(4)} b ${(b / n).toFixed(4)}`;
}

RS.device.addEventListener?.('uncapturederror', (e) => console.log('[probe_mips] uncaptured', e.error?.message?.slice(0, 300)));
for (const mips of [false, true]) {
    for (const kind of ['u8', 'srgb', 'half']) {
        const tex = makeTex(kind, mips);
        for (const [lv, ly] of [[null, 1], [null, 0], [0, 1], [4, 1], [7, 1], [7, 0]]) {
            console.log(`[probe_mips] mips ${mips} ${kind} level ${lv} layer ${ly}: ${await readLevel(tex, lv, ly)}`);
        }
        tex.dispose();
    }
}

// one texture read twice in a material: how many bindings does three make?
{
    const tex = makeTex('u8');
    const a = TSL.texture(tex, TSL.uv()).depth(TSL.int(0));
    const b = TSL.texture(tex, TSL.uv().mul(0.5)).depth(TSL.int(1));
    const mat = new THREE.MeshBasicNodeMaterial();
    mat.colorNode = TSL.vec4(a.rgb.add(b.rgb), 1.0);
    const scene = new THREE.Scene();
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
    scene.add(mesh);
    renderer.render(scene, cam);
    try {
        const code = await renderer.debug.getShaderAsync(scene, cam, mesh);
        const frag = code.fragmentShader;
        const tex2 = (frag.match(/texture_2d_array<f32>/g) ?? []).length;
        const samp = (frag.match(/: sampler;/g) ?? []).length;
        console.log(`[probe_mips] two reads of one DataArrayTexture: ${tex2} texture_2d_array bindings, ${samp} samplers in the fragment shader`);
    } catch (e) {
        console.log(`[probe_mips] could not read the shader: ${e.message}`);
    }
}
renderer.dispose();
Deno.exit(0);
