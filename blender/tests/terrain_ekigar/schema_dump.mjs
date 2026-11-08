// Dump Ekigar's operator registry as JSON: every operator's label, category, doc, flags, parameter schema and ports,
// plus the landform contract fixture and the graph-port answers. The Python test compares the port against it.
//
//   deno run --no-config --no-lock -A --import-map=blender/tests/terrain_ekigar/import_map.json \
//       blender/tests/terrain_ekigar/schema_dump.mjs <out.json> [ekigar_root]
const [outPath, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');
const url = (rel) => new URL(`file:///${ROOT}/${rel}`).href;

const reg = await import(url('src/core/registry.js'));
const model = await import(url('src/graph/model.js'));
const fixture = await import(url('test/landform_library_fixture.js'));
const masks = await import(url('src/export/terrain_masks.js'));
const heightmap = await import(url('src/export/heightmap.js'));

const ops = {};
for (const [id, o] of Object.entries(reg.OPERATORS)) {
    const params = {};
    for (const [k, v] of Object.entries(o.params)) params[k] = { ...v };
    ops[id] = {
        label: o.label, category: o.category, doc: o.doc ?? null, generator: !!o.generator,
        hidden: !!o.hidden, optionalInput: o.optionalInput ?? null, needsResample: !!o.needsResample,
        warpsPosition: !!o.warpsPosition, visualFixture: o.visualFixture ?? null,
        hasSnap: typeof o.snap === 'function', hasWarpPosition: typeof o.warpPosition === 'function',
        params, ports: reg.portsOf(id),
        structural: reg.structuralParams(id),
    };
}
const out = {
    order: Object.keys(reg.OPERATORS),
    list: reg.listOperators(),
    blendModes: reg.BLEND_MODES, combineModes: reg.COMBINE_MODES,
    ops,
    landformContract: fixture.LANDFORM_CONTRACT,
    portTypes: model.PORT_TYPES, projectFormat: model.PROJECT_FORMAT,
    canConnect: Object.fromEntries(['field', 'mask', 'colour', 'material'].flatMap((a) =>
        ['field', 'mask', 'colour', 'material'].map((b) => [`${a}>${b}`, model.canConnect(a, b)]))),
    maskNames: masks.MASK_NAMES,
    heightmapFormats: heightmap.HEIGHTMAP_FORMATS,
};
await Deno.writeTextFile(outPath, JSON.stringify(out, null, 1));
console.log(`schema: ${out.order.length} operators`);
