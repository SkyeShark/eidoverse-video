// Run Ekigar's terrain_mesh.js display-grid policy (terrainVertexSide, terrainGeometryCost, buildTerrainGeometry)
// and dump the results for display_grid.py to be compared against.
//
//   deno run --no-config --no-lock -A --import-map=blender/tests/terrain_ekigar/import_map_mesh.json \
//       blender/tests/terrain_ekigar/mesh_dump.mjs <out.json> [ekigar_root]
const [outPath, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');
const tm = await import(new URL(`file:///${ROOT}/src/nodes/terrain_mesh.js`).href);
const sides = [0, null, 1, 100.7, 255, 256, 300, 1024, 2048, 2049, 4096, 8192];
const out = {
    VERT_CAP: tm.VERT_CAP, VERT_FLOOR: tm.VERT_FLOOR,
    side: sides.map((r) => tm.terrainVertexSide(r)),
    sideCapped: sides.map((r) => tm.terrainVertexSide(r, 512)),
    cost: [2, 3, 255, 256, 257, 1024, 2048, 4096].map((n) => tm.terrainGeometryCost(n)),
    geometry: [[2, {}], [3, { side: 3 }], [5, { side: 5, withNormal: true }], [256, {}], [257, { side: 257 }],
               [100, { side: 7 }], [4096, { cap: 300 }]].map(([res, opts]) => {
        const g = tm.buildTerrainGeometry(res, opts);
        const n = g.attributes.normal;
        return { res, opts, side: g.userData.terrain.side, terrain: g.userData.terrain,
                 position: Array.from(g.attributes.position.array.slice(0, 3 * 40)),
                 positionLast: Array.from(g.attributes.position.array.slice(-6)),
                 uv: Array.from(g.attributes.uv.array.slice(0, 2 * 40)),
                 uvLast: Array.from(g.attributes.uv.array.slice(-4)),
                 index: Array.from(g.index.array.slice(0, 60)), indexLast: Array.from(g.index.array.slice(-12)),
                 indexKind: g.index.array.constructor.name, indexCount: g.index.array.length,
                 normal: n ? Array.from(n.array.slice(0, 9)) : null };
    }),
};
await Deno.writeTextFile(outPath, JSON.stringify(out));
console.log('mesh dump ok');
