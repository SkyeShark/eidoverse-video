// Run Ekigar's own bake.js exportMaps over given fields, with the browser pieces it touches stood in (the render
// target readback returns the field, `download` is captured), and write every file it would download, for
// export.export_maps to be compared against byte for byte.
//
//   deno run --no-config --no-lock -A blender/tests/terrain_ekigar/bake_dump.mjs <cases.json> <out_dir> [ekigar_root]
const [inPath, outDir, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');

const store = new Map();
let nBlob = 0;
let current = null;
globalThis.Blob = class { constructor(parts) { this.parts = parts; } };
URL.createObjectURL = (b) => { const id = `blob:${nBlob++}`; store.set(id, b.parts); return id; };
URL.revokeObjectURL = () => {};
globalThis.document = {
    body: { appendChild() {} },
    createElement() {
        return {
            click() {
                const parts = store.get(this.href);
                current.set(this.download, parts.map((p) => (p instanceof Uint8Array ? p : new Uint8Array(p.buffer ?? p))));
            },
            remove() {},
        };
    },
};
const { exportMaps } = await import(new URL(`file:///${ROOT}/src/export/bake.js`).href);
const cases = JSON.parse(await Deno.readTextFile(inPath));
for (const c of cases) {
    current = new Map();
    const N = c.size;
    const px = new Float32Array(N * N * 4);
    for (let i = 0; i < N * N; i++) { px[i * 4] = c.height[i]; px[i * 4 + 3] = c.aux[i]; }
    const renderer = { readRenderTargetPixelsAsync: async () => px };
    const state = { tile: c.tile, worldSize: c.worldSize, verticalScale: c.verticalScale, stack: null, layers: null };
    await exportMaps(renderer, state, { resolution: N, target: null });
    await Deno.mkdir(`${outDir}/${c.name}`, { recursive: true });
    for (const [name, parts] of current) {
        const len = parts.reduce((s, p) => s + p.length, 0);
        const buf = new Uint8Array(len);
        let o = 0;
        for (const p of parts) { buf.set(p, o); o += p.length; }
        await Deno.writeFile(`${outDir}/${c.name}/${name}`, buf);
    }
}
console.log(`bake cases: ${cases.length}`);
