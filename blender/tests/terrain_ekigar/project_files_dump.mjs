// Write ekigar-project/3 files exactly as Ekigar's Save button does (main.js: the same document keys, the graph
// through model.js toJSON, nodes made by addNode with the registry's defaultParams and wired with graphPorts), then
// evaluate each project's target with Ekigar's own compiler (CPU shim, 'coarse' quad derivatives) at its res.
//
//   deno run --no-config --no-lock -A --import-map=blender/tests/terrain_ekigar/import_map.json \
//       blender/tests/terrain_ekigar/project_files_dump.mjs <out_dir> [ekigar_root]
const [outDir, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');
const url = (rel) => new URL(`file:///${ROOT}/${rel}`).href;
const shim = await import('three/tsl');
const M = await import(url('src/graph/model.js'));
const { compileGraph } = await import(url('src/graph/compile.js'));
const { defaultParams, graphPorts } = await import(url('src/core/registry.js'));
await Deno.mkdir(outDir, { recursive: true });

const RES = 48;
const P = (op, over = {}) => ({ ...defaultParams(op), ...over });
const wire = (g, a, b, port = 'in', from = 'out') => {
    const r = M.connect(g, { node: a, port: from }, { node: b, port }, graphPorts);
    if (!r.ok) throw new Error(`wire ${from} -> ${port}: ${r.reason}`);
    return r.id;
};

function projects() {
    const out = [];
    {   // the guide's peaks: a range, erosion masked to the high ground, snow on top
        const g = M.createGraph();
        const base = M.addNode(g, 'mountainRange', { x: 0, y: 0 }, P('mountainRange', { style: 'alpine', relief: 0.8 }));
        const ero = M.addNode(g, 'phacelle', { x: 200, y: 0 }, P('phacelle', { strength: 0.3 }));
        const hm = M.addNode(g, 'heightMask', { x: 200, y: 150 }, P('heightMask', { lo: 0.55, hi: 2 }));
        const snow = M.addNode(g, 'snow', { x: 400, y: 0 }, P('snow', { line: 0.62 }));
        wire(g, base, ero); wire(g, base, hm); wire(g, hm, ero, 'mask'); wire(g, ero, snow);
        out.push({ name: 'peaks', g, target: snow, targetPort: 'out', worldSize: 2500 });
    }
    {   // a caldera on a smooth field, reached through a portal, with a group and a note; its floor mask previewed
        const g = M.createGraph();
        const f = M.addNode(g, 'fbm', { x: 0, y: 0 }, P('fbm', { frequency: 3, amplitude: 0.55, octaves: 3 }));
        const c = M.addNode(g, 'caldera', { x: 300, y: 0 }, P('caldera', { terraces: 4, domeRadius: 0.25 }));
        M.createPortal(g, { node: f, port: 'out' }, 'Base');
        M.connectViaPortal(g, 'Base', { node: c, port: 'in' }, graphPorts);
        M.addGroup(g, 'Volcanics', [c], { colour: '#b5643c' });
        M.addNote(g, '# caldera\nfloor for the lake', { x: 40, y: 200 });
        out.push({ name: 'caldera_floor', g, target: c, targetPort: 'floor', worldSize: 3000 });
    }
    {   // star dunes with a disabled blur in the chain (a disabled node passes its input through)
        const g = M.createGraph();
        const d = M.addNode(g, 'duneField', { x: 0, y: 0 }, P('duneField', { type: 'star' }));
        const b = M.addNode(g, 'blur', { x: 200, y: 0 }, P('blur', { radius: 6 }));
        const t = M.addNode(g, 'terrace', { x: 400, y: 0 }, P('terrace'));
        wire(g, d, b); wire(g, b, t);
        g.nodes.get(b).disabled = true;
        out.push({ name: 'dunes_disabled_blur', g, target: t, targetPort: 'out', worldSize: 3000 });
    }
    {   // two branches combined: a volcano and a canyon, max, the canyon behind a warp; a tab and a moved node
        const g = M.createGraph();
        const v = M.addNode(g, 'volcano', { x: 0, y: 0 }, P('volcano', { scale: 0.5 }));
        const f = M.addNode(g, 'fbm', { x: 0, y: 200 }, P('fbm'));
        const w = M.addNode(g, 'warp', { x: 200, y: 200 }, P('warp'));
        const cn = M.addNode(g, 'canyon', { x: 400, y: 200 }, P('canyon'));
        const cb = M.addNode(g, 'combine', { x: 600, y: 100 }, P('combine', { mode: 'max' }));
        wire(g, f, w); wire(g, w, cn); wire(g, v, cb, 'in'); wire(g, cn, cb, 'in2');
        const tab = M.addTab(g, 'Detail');
        M.moveToTab(g, cn, tab);
        out.push({ name: 'volcano_canyon_max', g, target: cb, targetPort: 'out', worldSize: 4000 });
    }
    {   // a terrain with a Texture Base driving a Material Map: the terrain target is the eroded field
        const g = M.createGraph();
        const f = M.addNode(g, 'fbm', { x: 0, y: 0 }, P('fbm'));
        const e = M.addNode(g, 'phacelle', { x: 200, y: 0 }, P('phacelle'));
        const tb = M.addNode(g, 'textureBase', { x: 200, y: 200 }, P('textureBase'));
        const mm = M.addNode(g, 'materialMap', { x: 400, y: 200 }, P('materialMap'));
        wire(g, f, e); wire(g, e, tb); wire(g, tb, mm, 'mask');
        out.push({ name: 'eroded_with_material_map', g, target: e, targetPort: 'wear', worldSize: 400,
                   materialTarget: mm });
    }
    {   // screen derivatives feeding heights: tower karst rebuilds its gradient with dFdx/dFdy, erosion steers by it,
        // and a slope mask of the karst gates the erosion (the graphs where the derivative mode changes the terrain)
        const g = M.createGraph();
        const f = M.addNode(g, 'fbm', { x: 0, y: 0 }, P('fbm'));
        const k = M.addNode(g, 'towerKarst', { x: 200, y: 0 }, P('towerKarst'));
        const e = M.addNode(g, 'phacelle', { x: 400, y: 0 }, P('phacelle'));
        const s = M.addNode(g, 'slopeMask', { x: 400, y: 200 }, P('slopeMask'));
        wire(g, f, k); wire(g, k, e); wire(g, k, s); wire(g, s, e, 'mask');
        out.push({ name: 'karst_eroded_slope_gated', g, target: e, targetPort: 'out', worldSize: 1000 });
    }
    return out;
}

const index = [];
for (const pr of projects()) {
    const doc = {
        format: M.PROJECT_FORMAT,
        tile: { x: 1, y: 1 }, worldSize: pr.worldSize, res: RES,
        cut: { cx: 0.5, cy: 0.5, radius: 0.28, fade: 0.07 },
        graph: M.toJSON(pr.g), target: pr.target, targetPort: pr.targetPort,
        materialTarget: pr.materialTarget ?? null,
        materials: [],
        conversionWarnings: [],
    };
    const path = `${outDir}/${pr.name}.ekigar.json`;
    await Deno.writeTextFile(path, JSON.stringify(doc, null, 2));
    // evaluate the saved document, reloaded, as Ekigar's Open would
    const back = JSON.parse(await Deno.readTextFile(path));
    const { project } = M.migrateProject(back);
    const g = M.fromJSON(project.graph);
    shim.__setGrid(RES, RES, 'coarse');
    const n = RES * RES, px = new Float64Array(n), py = new Float64Array(n);
    for (let j = 0; j < RES; j++) for (let i = 0; i < RES; i++) { px[j * RES + i] = (i + 0.5) / RES; py[j * RES + i] = (j + 0.5) / RES; }
    const res = compileGraph(g, project.target, { p: new shim.T([px, py], 'float'), tile: project.tile, resolution: RES },
        project.targetPort ?? 'out');
    const ch = { x: shim.__lanesOf(res.field, 0), y: shim.__lanesOf(res.field, 1), z: shim.__lanesOf(res.field, 2),
        w: shim.__lanesOf(res.field, 3) };
    for (const [k, v] of Object.entries(res.outs ?? {})) ch[`out:${k}`] = shim.__lanesOf(v, 0);
    const names = Object.keys(ch);
    const buf = new Float64Array(n * names.length);
    names.forEach((k, i) => buf.set(ch[k], i * n));
    await Deno.writeFile(`${outDir}/${pr.name}.bin`, new Uint8Array(buf.buffer));
    index.push({ name: pr.name, file: path, channels: names, warnings: res.warnings, order: res.order });
}
await Deno.writeTextFile(`${outDir}/index.json`, JSON.stringify(index, null, 1));
console.log(`project files: ${index.length}`);
