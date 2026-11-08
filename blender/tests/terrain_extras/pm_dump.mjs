// Runs the engine's eidoverse/procedural_materials.js on the engine's own 2D canvas (@napi-rs/canvas, Skia: the
// canvas render_common.mjs shims in) and dumps every case of pm_cases.json as raw RGBA, for test_pm_parity.py.
//   deno run --no-config --no-lock --cached-only -A pm_dump.mjs <procedural_materials.js> <pm_cases.json> <out dir>
import { createCanvas } from 'npm:@napi-rs/canvas@0.1.69';

const [SRC, CASES, OUT] = Deno.args;
Deno.mkdirSync(OUT, { recursive: true });

globalThis.window = globalThis;
globalThis.document = { createElement: () => createCanvas(300, 150) };
class CanvasTexture { constructor(canvas) { this.image = canvas; this.isCanvasTexture = true; } }
class Mat { constructor(o) { this.opts = o; } }
globalThis.THREE = {
    CanvasTexture, RepeatWrapping: 1000, SRGBColorSpace: 'srgb',
    MeshPhysicalMaterial: class extends Mat { get kind() { return 'physical'; } },
    MeshStandardMaterial: class extends Mat { get kind() { return 'standard'; } },
    Vector2: class { constructor(x, y) { this.x = x; this.y = y; } },
};
(0, eval)(Deno.readTextFileSync(SRC));
const PM = globalThis.ProceduralMaterials;
const cases = JSON.parse(Deno.readTextFileSync(CASES));
const index = {};

function dump(name, tex) {
    const c = tex.image;
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    Deno.writeFileSync(`${OUT}/${name}.rgba`, new Uint8Array(d.buffer, d.byteOffset, d.byteLength));
    index[name] = { w: c.width, h: c.height, colorSpace: tex.colorSpace ?? null };
}

const made = {};
for (const [name, fn, args] of cases.generators) {
    const t = PM[fn](...args);
    made[name] = t;
    dump(name, t);
}
// derived cases may reference each other: resolve in dependency order
const pending = [...cases.derived];
let guard = 0;
while (pending.length && guard++ < 100) {
    const [name, fn, args] = pending.shift();
    const refs = fn === 'heightToNormal' ? [args[0]] : [args[0], args[1]];
    if (refs.some(r => !made[r])) { pending.push([name, fn, args]); continue; }
    const t = fn === 'heightToNormal' ? PM.heightToNormal(made[args[0]], args[1])
        : PM.composite(made[args[0]], made[args[1]], args[2], args[3]);
    made[name] = t;
    dump(name, t);
}
const facts = {};
for (const [name, fn, opts] of cases.factories) {
    const m = PM[fn](opts);
    const rec = { kind: m.kind, scalars: {}, maps: {} };
    for (const [k, v] of Object.entries(m.opts)) {
        if (v && v.isCanvasTexture) { dump(`${name}__${k}`, v); rec.maps[k] = `${name}__${k}`; }
        else if (v && v.x !== undefined && v.y !== undefined) rec.scalars[k] = [v.x, v.y];
        else rec.scalars[k] = v;
    }
    facts[name] = rec;
}
Deno.writeTextFileSync(`${OUT}/index.json`, JSON.stringify({ textures: index, factories: facts }, null, 1));
console.log(`[pm_dump] ${Object.keys(index).length} textures, ${Object.keys(facts).length} factories -> ${OUT}`);
