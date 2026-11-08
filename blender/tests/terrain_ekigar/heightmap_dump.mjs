// Run Ekigar's heightmap.js exportHeightmap over given fields (its download sink captured) and write every file it
// emits, for export.export_heightmap to be compared against.
//
//   deno run --no-config --no-lock -A blender/tests/terrain_ekigar/heightmap_dump.mjs <cases.json> <out_dir> [root]
const [inPath, outDir, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');
const hm = await import(new URL(`file:///${ROOT}/src/export/heightmap.js`).href);
const cases = JSON.parse(await Deno.readTextFile(inPath));
for (const c of cases) {
    await Deno.mkdir(`${outDir}/${c.name}`, { recursive: true });
    const files = [];
    const download = (name, bytes) => files.push([name, bytes]);
    hm.exportHeightmap({
        field: { data: Float64Array.from(c.data), width: c.width, height: c.height },
        formats: c.formats, worldSize: c.worldSize, verticalScale: c.verticalScale,
        heightRangeMetres: c.heightRangeMetres ?? null, range: c.range ?? null, flipY: c.flipY ?? false,
        name: c.name, download,
    });
    for (const [name, bytes] of files) await Deno.writeFile(`${outDir}/${c.name}/${name}`, bytes);
}
console.log(`heightmap cases: ${cases.length}`);
