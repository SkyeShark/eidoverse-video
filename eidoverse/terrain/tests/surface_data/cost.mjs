// The surface data's cost against the design's budget (PORT_PLAN.md 8.2 row P14: "cost within the design's 7";
// SURFACING_DESIGN.md 5.4, package 1, item 5; section 7), Blender's blender/tests/terrain/surface_data/cost.py on what
// the port's tests recorded: per case the cold bake in all (budget 90 s for a seven-level film terrain) and per level
// (s per 1024^2 cells: budget 15 s), the palette bake (C and P: budget 30 s), the textures made (layers_test: the
// design's "a cache hit with its images" budget, 10 s), and the disk the case's cache folder holds (budget 1.2 GB per
// terrain), beside Blender's own seconds for the same case where its records have them. The numbers are recorded, not
// enforced (cost.py's rule: on a shared machine they say as much about the other jobs as about the bake).
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surface_data/cost.mjs
//
// Reads tests/out/surface_data/{bake_test,palette_test,layers_test}.json; writes tests/out/surface_data/cost.json and
// prints a table. No GPU.

import * as S from './_surface.mjs';

const BUDGET = { per_1024_s: 15.0, film_cold_s: 90.0, hit_with_images_s: 10.0, palette_s: 30.0, disk_gb: 1.2 };
const out = S.W.out('surface_data');
const read = (n) => (S.W.exists(`${out}/${n}.json`) ? JSON.parse(Deno.readTextFileSync(`${out}/${n}.json`)) : null);
const bake = read('bake_test'), pal = read('palette_test'), lay = read('layers_test');
const disk = (dir) => {
    let s = 0;
    try {
        for (const e of Deno.readDirSync(dir)) if (e.isFile) s += Deno.statSync(`${dir}/${e.name}`).size;
    } catch (_e) {
        return null;
    }
    return s;
};
const rows = {};
for (const name of S.CASES) {
    const b = bake?.results?.[name];
    const p = pal?.results?.[name];
    const levels = b?.port_levels ?? [];
    const per = levels.map((lv) => {
        const n = lv.n ?? lv.cells ?? null;
        const total = lv.total ?? lv.seconds ?? null;
        return { n, total, per_1024: n && total !== null ? +(total * (1024 / n) ** 2).toFixed(2) : null };
    });
    const d = disk(`${out}/bakes/${name}`);
    rows[name] = {
        levels: levels.length, cold_s: b?.seconds ?? null, blender_cold_s: b?.blender_seconds ?? null,
        max_per_1024_s: per.reduce((m, x) => Math.max(m, x.per_1024 ?? 0), 0) || null, per_level: per,
        palette_s: p?.port_seconds ?? null, palette_C_s: p?.port?.C_seconds ?? null, palette_P_s: p?.port?.P_seconds ?? null,
        blender_palette_s: p?.blender_seconds ?? null, blender_palette_C_s: p?.blender?.C_seconds ?? null,
        blender_palette_P_s: p?.blender?.P_seconds ?? null,
        textures_s: lay?.case === name ? lay.seconds : null, disk_gb: d === null ? null : +(d / 1e9).toFixed(3),
    };
}
Deno.writeTextFileSync(`${out}/cost.json`, JSON.stringify({ budget: BUDGET, cases: rows }, null, 1));
const f = (v, w = 8, d = 1) => (v === null || v === undefined ? '-' : Number(v).toFixed(d)).padStart(w);
console.log(`${'case'.padEnd(18)} ${'levels'.padStart(6)} ${'cold s'.padStart(8)} ${'Blender'.padStart(8)} ${'max/1024^2'.padStart(10)} ` +
    `${'palette s'.padStart(9)} ${'Blender'.padStart(8)} ${'tex s'.padStart(6)} ${'disk GB'.padStart(7)}`);
for (const [name, r] of Object.entries(rows)) {
    console.log(`${name.padEnd(18)} ${String(r.levels).padStart(6)} ${f(r.cold_s)} ${f(r.blender_cold_s)} ${f(r.max_per_1024_s, 10)} ` +
        `${f(r.palette_s, 9)} ${f(r.blender_palette_s)} ${f(r.textures_s, 6)} ${f(r.disk_gb, 7, 2)}`);
}
console.log(`budget: cold ${BUDGET.film_cold_s} s (film), ${BUDGET.per_1024_s} s per 1024^2 cells, palette ${BUDGET.palette_s} s, ` +
    `a cache hit with its textures ${BUDGET.hit_with_images_s} s, disk ${BUDGET.disk_gb} GB`);
