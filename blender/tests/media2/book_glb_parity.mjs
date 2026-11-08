// book_glb_parity.mjs — the engine's own makeBook(gltf) (eidoverse/book.js) measuring a book GLB, for the Blender
// edition's measure_book_glb parity check (test_book_glb.py runs it and compares).
//
//   deno run -A --no-config --node-modules-dir=none --cached-only book_glb_parity.mjs <book.glb>
//
// three's GLTFLoader parses the GLB with its images stripped (Deno decodes no images; the measure reads geometry and
// UVs only). book.js runs unchanged: its "[makeBook] case halfT=… uJoint=…" line is the engine's measurement. The
// last stdout line is JSON: { measured: {halfT, halfH, board, joint, lip, round, uJoint}, rig: {…metrics} }.
import * as WEBGPU from 'npm:three@0.184.0/webgpu';
import * as TSL from 'npm:three@0.184.0/tsl';
import { GLTFLoader } from 'npm:three@0.184.0/examples/jsm/loaders/GLTFLoader.js';
import { createCanvas, loadImage } from 'npm:@napi-rs/canvas@0.1.69';

globalThis.THREE = Object.assign({}, WEBGPU, TSL);           // the video renderer's THREE carries TSL merged
globalThis.document = { createElement: (tag) => (tag === 'canvas' ? createCanvas(1, 1) : null) };
globalThis.loadCanvasImage = (bytes) => loadImage(bytes);
globalThis.window = globalThis;
await import(new URL('../../../eidoverse/book_core.js', import.meta.url).href);
await import(new URL('../../../eidoverse/book.js', import.meta.url).href);

// strip images from the GLB: the JSON chunk loses images/textures/samplers and every texture reference
const bytes = await Deno.readFile(Deno.args[0]);
const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
const jsonLen = dv.getUint32(12, true);
const json = JSON.parse(new TextDecoder().decode(bytes.subarray(20, 20 + jsonLen)));
delete json.images; delete json.textures; delete json.samplers;
for (const m of json.materials || []) {
    delete m.normalTexture; delete m.occlusionTexture; delete m.emissiveTexture;
    if (m.pbrMetallicRoughness) { delete m.pbrMetallicRoughness.baseColorTexture; delete m.pbrMetallicRoughness.metallicRoughnessTexture; }
}
const binStart = 20 + jsonLen;
const binChunk = bytes.subarray(binStart);                       // [len][BIN\0][data]
let jtxt = new TextEncoder().encode(JSON.stringify(json));
const pad = (4 - (jtxt.length % 4)) % 4;
const jbuf = new Uint8Array(jtxt.length + pad).fill(0x20); jbuf.set(jtxt);
const total = 12 + 8 + jbuf.length + binChunk.length;
const out = new Uint8Array(total), ov = new DataView(out.buffer);
ov.setUint32(0, 0x46546C67, true); ov.setUint32(4, 2, true); ov.setUint32(8, total, true);
ov.setUint32(12, jbuf.length, true); ov.setUint32(16, 0x4E4F534A, true);
out.set(jbuf, 20); out.set(binChunk, 20 + jbuf.length);

const gltf = await new Promise((res, rej) => new GLTFLoader().parse(out.buffer, '', res, rej));
let line = '';
const log = console.log;
console.log = (...a) => { const s = a.join(' '); if (s.startsWith('[makeBook] case')) line = s; };
const book = globalThis.makeBook(gltf, {});
console.log = log;
const num = (k) => +(line.match(new RegExp(`${k}=(-?[\\d.]+)`)) || [])[1];
const measured = { halfT: num('halfT'), halfH: num('halfH'), board: num('board'), joint: num('joint'), lip: num('lip'),
    round: num('round'), uJoint: num('uJoint') };
const metrics = {};
for (const [k, v] of Object.entries(book.metrics || {})) if (typeof v === 'number') metrics[k] = v;
log(line);
log(JSON.stringify({ measured, metrics, maxPage: book.maxPage, spreadCount: book.spreadCount }));
Deno.exit(0);
