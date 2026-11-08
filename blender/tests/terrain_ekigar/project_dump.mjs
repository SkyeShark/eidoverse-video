// Run Ekigar's project migration and graph serializer over a list of documents and dump the results, for the port
// to be compared against: migrateProject(doc) and toJSON(fromJSON(doc.graph)).
//
//   deno run --no-config --no-lock -A --import-map=blender/tests/terrain_ekigar/import_map.json \
//       blender/tests/terrain_ekigar/project_dump.mjs <docs.json> <out.json> [ekigar_root]
const [inPath, outPath, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');
const model = await import(new URL(`file:///${ROOT}/src/graph/model.js`).href);
const docs = JSON.parse(await Deno.readTextFile(inPath));
const out = docs.map((doc) => {
    const { project, warnings } = model.migrateProject(doc);
    const g = model.fromJSON(doc.graph ?? { nodes: [], edges: [] });
    return { project, warnings, roundTrip: model.toJSON(g) };
});
await Deno.writeTextFile(outPath, JSON.stringify(out, null, 1));
console.log(`projects: ${out.length}`);
