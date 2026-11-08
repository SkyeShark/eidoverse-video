// parity_dump.mjs: runs the WebGPU edition's createFlora (eidoverse/vegetation.js, untouched) headless in Deno and
// dumps, per case, the plant geometry (position, normal, uv, aH, index) and the per-instance attributes (aPosRot,
// aScaleVar, aPhase) to blender/tests/flora/out/parity/<case>.json, for parity_check.py to compare against the
// Blender port. Nothing renders: the TSL material graphs are built but never compiled.
//   cd <worktree> && deno run --no-config --no-lock -A blender/tests/flora/parity_dump.mjs <three build dir>
// (the three build dir: a node_modules/three/build folder, e.g. the main checkout's)
const threeDir = Deno.args[0];
if (!threeDir) throw new Error('usage: parity_dump.mjs <node_modules/three/build dir>');
const url = (p) => new URL('file:///' + p.replace(/\\/g, '/').replace(/^\/+/, ''));
const W = await import(url(threeDir + '/three.webgpu.js'));
globalThis.THREE = { ...W, ...W.TSL };     // three.tsl.js re-exports W.TSL through a bare 'three/webgpu' import
globalThis.loadImageTexture = async () => new W.Texture();
const veg = await import(url(Deno.cwd() + '/eidoverse/vegetation.js'));

const heightFn = (x, z) => 0.3 * Math.sin(0.4 * x) + 0.2 * Math.cos(0.3 * z);
const CASES = {
    grass_s7: { species: 'grass', size: 12, seed: 7 },
    grass_green_organic: { species: 'grass', size: 14, seed: 3, height: 0.45, color: 'green', footprint: 'organic', center: [2, -1] },
    grass_heightfn: { species: 'grass', width: 10, depth: 6, seed: 11, heightFn },
    galleta: { species: 'galleta_dry', size: 16, seed: 3, density: 1.3 },
    yucca: { species: 'yucca', size: 30, seed: 21, density: 0.7 },
    daisy_s5: { species: 'daisy', size: 6, seed: 5, color: 'orange' },
    daisy_heading: { species: 'daisy', size: 5, seed: 41, heading: [-0.5, 0.8, 0.3], density: 0.5 },
    daisy_toward: { species: 'daisy', size: 4, seed: 9, heading: { toward: [3, 1.5, 6] }, headScale: 2 },
    daisy_place: { species: 'daisy', seed: 4, placements: [[1, 2, 1.2], [-1, 0.5], [0, 0, 0.8]], heading: 1.1 },
    daisy_seed0: { species: 'daisy', size: 3, seed: 0, height: 0.6 },
    blackbrush: { species: 'blackbrush', size: 40, seed: 5, density: 0.85, footprint: 'organic' },
    creosote: { species: 'creosote', size: 40, seed: 8, variant: 1 },
    sagebrush: { species: 'sagebrush', size: 30, seed: 12 },
    corn_rows: { species: 'corn', width: 8, depth: 6, seed: 4, rows: { spacing: 0.9, angle: 0.3 } },
    corn_peel: { species: 'corn', width: 4, depth: 3, seed: 9, rows: { stride: 2, phase: 1 }, corn: { peel: true, ears: 3 } },
    sunflower_rows: { species: 'sunflower', width: 6, depth: 5, seed: 3, rows: { spacing: 0.85, plant: 0.5 }, density: 1.3 },
    sunflower_wild: { species: 'sunflower', size: 8, seed: 31 },
};
const only = Deno.args.slice(1);
const outDir = Deno.cwd() + '/blender/tests/flora/out/parity';
await Deno.mkdir(outDir, { recursive: true });
const arr = (a) => (a ? Array.from(a.array ?? a) : null);
for (const [name, opts] of Object.entries(CASES)) {
    if (only.length && !only.includes(name)) continue;
    veg.resetFloraOccupancy();
    const f = await veg.createFlora(opts);
    const g = f.mesh.geometry;
    const out = {
        opts: { ...opts, heightFn: opts.heightFn ? 'parity' : undefined },
        count: f.count,
        position: arr(g.attributes.position), normal: arr(g.attributes.normal), uv: arr(g.attributes.uv),
        aH: arr(g.attributes.aH), index: arr(g.index),
        aPosRot: arr(g.attributes.aPosRot), aScaleVar: arr(g.attributes.aScaleVar), aPhase: arr(g.attributes.aPhase),
    };
    if (f.stemMesh) {
        const s = f.stemMesh.geometry;
        out.stem = { position: arr(s.attributes.position), normal: arr(s.attributes.normal), uv: arr(s.attributes.uv),
            aH: arr(s.attributes.aH), index: arr(s.index) };
    }
    await Deno.writeTextFile(`${outDir}/${name}.json`, JSON.stringify(out));
    console.log(`[parity] ${name}: ${f.count} instances, ${g.attributes.position.count} verts`);
}
