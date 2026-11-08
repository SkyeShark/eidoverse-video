// inline_art_reference.mjs: the canvases quiet_room.js and showroom.js draw INSIDE build() (the essay, the register,
// the pulpit fall, the booklet, the hazard stripes, the stencils, the label, the sign, the slogan, the EXIT signs, the
// platter, the toast), captured from the ORIGINAL builds for the Blender port's parity test (test_art_parity.py).
// Each build runs with the real three r184 (webgpu + tsl; no renderer is made, so no GPU) whose DataTexture records
// every texture it is handed; the canvases go back to canvas orientation (dataTexture flipped the rows) and are saved
// as <set>_<width>x<height>.png (the sRGB ones; every inline canvas has a size of its own). The AmbientCG sets are not
// loaded (fetchPBR answers with no files): only the canvases matter here.
//
//   deno run --no-config --no-lock --cached-only --import-map=inline_import_map.json -A inline_art_reference.mjs <dir>
import * as W from 'npm:three@0.184.0/webgpu';
import * as TSL from 'npm:three@0.184.0/tsl';

const out = Deno.args[0] || './out/ref';
Deno.mkdirSync(out, { recursive: true });
const captured = [];
class RecordingDataTexture extends W.DataTexture {
    constructor(...a) { super(...a); captured.push(this); }
}
const T = { ...W, ...TSL, DataTexture: RecordingDataTexture };
globalThis.fetchPBR = async () => ({ files: {} });
globalThis.loadImageTexture = async () => null;
const warn = console.warn;
console.warn = (...a) => { if (!String(a[0]).includes('missing texture')) warn(...a); };

const N = await import('npm:@napi-rs/canvas@0.1.69');
async function dump(tag) {
    const seen = new Set();
    for (const t of captured) {
        if (t.colorSpace !== W.SRGBColorSpace || !t.image?.data) continue;
        const { data, width: w, height: h } = t.image;
        const key = `${w}x${h}`;
        if (seen.has(key)) continue;                 // the first texture of a size (boards repeat sizes; not used)
        seen.add(key);
        const rows = new Uint8ClampedArray(w * h * 4);
        for (let y = 0; y < h; y++) {                // every canvasTexture flipped its rows: flip them back
            rows.set(data.subarray((h - 1 - y) * w * 4, (h - y) * w * 4), y * w * 4);
        }
        const cv = N.createCanvas(w, h);
        const ctx = cv.getContext('2d');
        const img = ctx.createImageData(w, h);
        img.data.set(rows);
        ctx.putImageData(img, 0, 0);
        Deno.writeFileSync(`${out}/${tag}_${key}.png`, await cv.encode('png'));
        console.log(`${tag}_${key}`);
    }
}

const QR = await import('../../../eidoverse/sets/unknown_force/quiet_room.js');
captured.length = 0;
await QR.build(T, {});
await dump('inline_qr');
const SR = await import('../../../eidoverse/sets/unknown_force/showroom.js');
captured.length = 0;
await SR.build(T, {});
await dump('inline_sr');
console.log('INLINE REFERENCES DONE');
