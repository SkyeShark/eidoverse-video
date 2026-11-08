// Evaluate Ekigar graphs with Ekigar's own compiler and operators, on the CPU, and dump every channel.
//
//   deno run --no-config --no-lock -A --import-map=blender/tests/terrain_ekigar/import_map.json \
//       blender/tests/terrain_ekigar/oracle_dump.mjs <spec.json> <out_dir> [ekigar_root]
//
// spec.json: { "probes": [ { "name", "graph": {nodes, edges}, "target", "port"?, "tile"?: {x,y},
//                            "resolution"?, "grid"?: [w, h], "dmode"?: "coarse" | "fine" | "central",
//                            "kind"?: "graph" | "field_cpu" | "ekigar_field", "config"? } ] }
// For every probe it writes <out_dir>/<name>.bin (float64 lanes, row-major, row j = v index) and
// <out_dir>/<name>.json ({channels: [...], grid, warnings, order, error}).
//
// The 'three/tsl' import is the CPU shim (tsl_cpu_shim.mjs), so nothing here touches a GPU.

const [specPath, outDir, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');
const url = (rel) => new URL(`file:///${ROOT}/${rel}`).href;

const shim = await import('three/tsl');
const { fromJSON } = await import(url('src/graph/model.js'));
const { compileGraph } = await import(url('src/graph/compile.js'));
const fieldCpu = await import(url('src/core/field_cpu.js'));
const { ekigarField } = await import(url('src/nodes/phacelle.js'));

const spec = JSON.parse(await Deno.readTextFile(specPath));
await Deno.mkdir(outDir, { recursive: true });

function lanesP(gw, gh, tile) {
    const n = gw * gh;
    const px = new Float64Array(n), py = new Float64Array(n);
    const tx = tile.x || 1, ty = tile.y || 1;
    for (let j = 0; j < gh; j++) {
        for (let i = 0; i < gw; i++) {
            px[j * gw + i] = ((i + 0.5) / gw) * tx;
            py[j * gw + i] = ((j + 0.5) / gh) * ty;
        }
    }
    return { px, py };
}

async function writeProbe(name, channels, meta) {
    const names = Object.keys(channels);
    const n = names.length ? channels[names[0]].length : 0;
    const buf = new Float64Array(n * names.length);
    names.forEach((k, i) => buf.set(channels[k], i * n));
    await Deno.writeFile(`${outDir}/${name}.bin`, new Uint8Array(buf.buffer));
    await Deno.writeTextFile(`${outDir}/${name}.json`, JSON.stringify({ channels: names, ...meta }, null, 1));
}

let failures = 0;
for (const pr of spec.probes) {
    const [gw, gh] = pr.grid ?? [64, 64];
    const tile = pr.tile ?? { x: 1, y: 1 };
    shim.__setGrid(gw, gh, pr.dmode ?? 'coarse');
    const { px, py } = lanesP(gw, gh, tile);
    const t0 = performance.now();
    try {
        const kind = pr.kind ?? 'graph';
        if (kind === 'field_cpu') {
            const f = fieldCpu.makeField(pr.config ?? fieldCpu.defaultConfig());
            const H = new Float64Array(gw * gh), DX = new Float64Array(gw * gh), DY = new Float64Array(gw * gh),
                R = new Float64Array(gw * gh), E = new Float64Array(gw * gh);
            for (let i = 0; i < gw * gh; i++) {
                const r = f.evaluate(px[i], py[i]);
                H[i] = r.height; DX[i] = r.dx; DY[i] = r.dy; R[i] = r.ridge; E[i] = r.erosionDelta;
            }
            await writeProbe(pr.name, { height: H, dx: DX, dy: DY, ridge: R, erosionDelta: E },
                { grid: [gw, gh], report: f.report, config: f.config });
        } else if (kind === 'ekigar_field') {
            const p = new shim.T([px, py], 'float');
            const cfg = pr.config ?? fieldCpu.defaultConfig();
            const v = ekigarField(p, cfg);
            await writeProbe(pr.name, {
                x: shim.__lanesOf(v, 0), y: shim.__lanesOf(v, 1), z: shim.__lanesOf(v, 2), w: shim.__lanesOf(v, 3),
            }, { grid: [gw, gh] });
        } else {
            const g = fromJSON(pr.graph);
            const p = new shim.T([px, py], 'float');
            const ctx = { p, tile, resolution: pr.resolution ?? gw };
            const res = compileGraph(g, pr.target, ctx, pr.port ?? 'out');
            const ch = {
                x: shim.__lanesOf(res.field, 0), y: shim.__lanesOf(res.field, 1),
                z: shim.__lanesOf(res.field, 2), w: shim.__lanesOf(res.field, 3),
            };
            for (const [k, v] of Object.entries(res.outs ?? {})) ch[`out:${k}`] = shim.__lanesOf(v, 0);
            await writeProbe(pr.name, ch, {
                grid: [gw, gh], warnings: res.warnings, order: res.order, resamples: res.resamples,
                missing: res.missing, ms: Math.round(performance.now() - t0),
            });
        }
    } catch (e) {
        failures++;
        await Deno.writeTextFile(`${outDir}/${pr.name}.json`,
            JSON.stringify({ channels: [], error: String(e?.stack ?? e) }, null, 1));
        console.log(`ERROR ${pr.name}: ${String(e?.message ?? e).slice(0, 200)}`);
    }
}
console.log(`oracle: ${spec.probes.length} probes, ${failures} errors`);
