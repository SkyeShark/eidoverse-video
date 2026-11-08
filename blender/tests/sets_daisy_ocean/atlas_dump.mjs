// Dumps the WebGPU edition's face atlas (eidoverse/sets/ocean/faces_atlas.js, drawn with @napi-rs/canvas as in the
// engine) as raw RGBA, for parity_atlas.py:  deno run --no-config --no-lock -A atlas_dump.mjs <out.rgba>
const here = new URL('.', import.meta.url);
const ocean = new URL('../../../eidoverse/sets/ocean/', here);
const util = await import(new URL('util.js', ocean).href);
const { drawFaceAtlas } = await import(new URL('faces_atlas.js', ocean).href);
await util.initCanvas();
const t0 = performance.now();
const a = drawFaceAtlas(util.makeCanvas, { n: 8, cell: 256, seed: 11 });
console.log(`atlas ${a.w}x${a.h} in ${Math.round(performance.now() - t0)} ms`);
Deno.writeFileSync(Deno.args[0], a.data);
