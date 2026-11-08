// Run Ekigar's local_area.js and the field side of mixed.js over a list of cases and dump every result, for the
// port (eidoblend/terrain/ekigar/local_area.py) to be compared against.
//
//   deno run --no-config --no-lock -A --import-map=blender/tests/terrain_ekigar/import_map.json \
//       blender/tests/terrain_ekigar/local_area_dump.mjs <cases.json> <out.json> [ekigar_root]
const [inPath, outPath, rootArg] = Deno.args;
const ROOT = (rootArg ?? 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace(/\\/g, '/');
const la = await import(new URL(`file:///${ROOT}/src/export/local_area.js`).href);
const mixed = await import(new URL(`file:///${ROOT}/src/export/mixed.js`).href);
const cases = JSON.parse(await Deno.readTextFile(inPath));

const arr = (a) => Array.from(a);
const out = cases.map((c) => {
    const field = { data: Float64Array.from(c.field.data), width: c.field.width, height: c.field.height };
    if (c.field.aux) field.aux = Float64Array.from(c.field.aux);
    const r = { name: c.name };
    try {
        const G = la.resolveGeometry(c.geometry);
        r.geometry = G;
        const rc = la.resolveCut(c.cut, G);
        r.cut = rc;
        const wf = la.weightField(rc);
        r.weight = { data: arr(wf.data), coverage: wf.coverage, coreCoverage: wf.coreCoverage,
                     annulusCoverage: wf.annulusCoverage, surroundCoverage: wf.surroundCoverage };
        const wf2 = la.weightField(rc, { width: 17, height: 13 });
        r.weightSmall = { data: arr(wf2.data), coverage: wf2.coverage };
        const crop = la.cropLocal(field, rc);
        r.crop = { data: arr(crop.data), mask: arr(crop.mask), maskF: arr(crop.maskF), w: crop.w, h: crop.h,
                   x0: crop.x0, y0: crop.y0 };
        r.seam = la.seamRing(field, rc, 48);
        r.samples = c.points.map(([x, y]) => [la.sampleFieldMetres(field, G, x, y),
                                              la.sampleFieldNearestMetres(field, G, x, y),
                                              la.weightAtMetres(rc, x, y)]);
        r.texelWeights = c.texels.map(([i, j]) => la.weightAtTexel(rc, i, j));
        r.down = c.down.map(([w, h]) => { const d = la.areaDownsample(field, w, h); return arr(d.data); });
        const split = mixed.splitField({ data: field.data, width: field.width, height: field.height },
                                       c.cut, { worldSize: c.geometry.worldSize, tile: c.geometry.tile,
                                                seamSamples: 32 });
        r.split = { weight: arr(split.weight), local: { ...split.local, data: arr(split.local.data) },
                    localMask: { ...split.localMask, data: arr(split.localMask.data) },
                    coverage: split.coverage, coreCoverage: split.coreCoverage,
                    annulusCoverage: split.annulusCoverage, surroundCoverage: split.surroundCoverage,
                    seam: split.seam, warnings: split.warnings };
        if (c.masks) {
            const m = mixed.rasteriseLocalMasks({ field, cut: rc, names: c.masks, verticalScale: 0.3 });
            r.masks = Object.fromEntries(Object.entries(m).map(([k, v]) => [k, arr(v)]));
        }
        r.driver = {
            number: arr(mixed.resolveDriverField(0.25, field).data),
            implicit: arr(mixed.resolveDriverField(null, field).data),
            array: arr(mixed.resolveDriverField(Float64Array.from(field.data).map((v) => v * 2), field).data),
        };
    } catch (e) {
        r.error = String(e.message ?? e);
    }
    return r;
});
const lw = [
    [], [{ maskStack: [{ type: 'terrain', params: { source: 'curvPlan' } }, { type: 'noise' }] }],
    [{ legacy: { maskStack: [{ type: 'terrain' }, { type: 'terrain', enabled: false, params: { source: 'x' } }] } },
     { maskStack: [{ type: 'terrain', params: { source: 'aspect' } }] }],
];
const usedBy = lw.map((l) => mixed.masksUsedBy(l));
const lw0 = { localWeight: [[0, 0, 10, 2], [8.5, 0, 10, 2], [9, 0, 10, 2], [10, 0, 10, 2], [3, 4, 5, 0], [6, 8, 10, 0]]
    .map(([dx, dy, r, f]) => la.localWeight(dx, dy, r, f)),
    wrapDelta: [[350, 400], [-350, 400], [199, 400], [201, 400], [-201, 400], [5, 0], [1234.5, 400]]
    .map(([d, p]) => la.wrapDelta(d, p)) };
await Deno.writeTextFile(outPath, JSON.stringify({ cases: out, usedBy, scalars: lw0 }));
console.log(`local area cases: ${out.length}`);
