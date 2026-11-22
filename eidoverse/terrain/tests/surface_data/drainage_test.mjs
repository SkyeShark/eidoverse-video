// Hero drainage (PORT_PLAN.md 8.2 row P14: "the hero drainage within 15 %"; SURFACING_DESIGN.md 5.4, package 1,
// item 4), Blender's blender/tests/terrain/surface_data/test_drainage.py on the port's bakes: the trunk's catchment
// stays within 15 % from the main level to the finest hero level, for fluvial_range at its canyon_road focus and
// lauterbrunnen's valley trunk. The trunk: on the main level, the largest flux across a 10 m section inside the
// finest hero window less its border band; on each finer level, the largest flux across a 10 m section within 30 m of
// that point, from the runner's drainage area (the terrain's A) and from the bake's own routing ('area') on the levels
// the bake re-routed (option reroute_hero). What the maps read is compared with the main level's.
//
// The Blender edition at d67f19e (its fix-round report): lauterbrunnen passes; fluvial_range fails on the runner's
// own drainage area (its finest hero level's trunk falls to a fraction of the main level's: the fluvial package's
// known defect, which the bake reads and does not make). The cases' fields are Blender's (the snapshots), so the
// port reproduces that result: the check passes when the port's numbers equal Blender's design result case by case.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/drainage_test.mjs
//
// Writes tests/out/surface_data/drainage_test.json. JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const T = new S.C.Checks('surface_data: hero drainage');
const TOL = 0.15, CROSS_M = 10.0, NEAR_M = 30.0, FOCUS_M = 150.0;
const EXPECT = { fluvial_range: false, lauterbrunnen: true };       // Blender's result at d67f19e

/** The largest flux across a CROSS_M section inside a world box: [flux, x, y] or null (test_drainage.trunk). */
function trunk(A, lv, box) {
    const n = lv.n, cell = Number(lv.cell);
    const k = Math.max(1, Math.round(CROSS_M / cell));
    const c = new Float64Array((n + 1) * (n + 1));
    for (let j = 0; j < n; j++) {
        let row = 0;
        for (let i = 0; i < n; i++) {
            row += A[j * n + i];
            c[(j + 1) * (n + 1) + i + 1] = c[j * (n + 1) + i + 1] + row;
        }
    }
    let best = -1, bx = 0, by = 0, found = false;
    for (let j = 0; j + k <= n; j++) {
        for (let i = 0; i + k <= n; i++) {
            const s = (c[(j + k) * (n + 1) + i + k] - c[j * (n + 1) + i + k] - c[(j + k) * (n + 1) + i] + c[j * (n + 1) + i]) / k;
            const x = Number(lv.x0) + (i + 0.5) * cell + 0.5 * (k - 1) * cell, y = Number(lv.y0) + (j + 0.5) * cell + 0.5 * (k - 1) * cell;
            if (x < box[0] || x > box[2] || y < box[1] || y > box[3]) continue;
            found = true;
            if (s > best) { best = s; bx = x; by = y; }
        }
    }
    return found ? [best, bx, by] : null;
}
const km2 = (r) => (r === null ? null : +(r[0] / 1e6).toFixed(3));

const R = await G.init();
const results = {};
for (const name of Object.keys(EXPECT)) {
    const got = await S.portSurface(name);
    if (!got) {
        T.ok(`${name}: the case is there`, false, S.skipped[name] ?? 'no snapshot or Blender bake');
        continue;
    }
    const { t, sd } = got;
    const [fx, fy] = t.info.focus[0];
    const roles = t.levels.map((lv) => lv.role);
    const mainI = roles.indexOf('main');
    const fin = t.levels[t.levels.length - 1];
    const b = Number(fin.band) * Number(fin.cell);
    const box = [Number(fin.x0) + b, Number(fin.y0) + b, Number(fin.x0) + Number(fin.side) - b, Number(fin.y0) + Number(fin.side) - b];
    const focus = [fx - FOCUS_M, fy - FOCUS_M, fx + FOCUS_M, fy + FOCUS_M];
    const rows = [];
    let near = box;
    for (let i = mainI; i < t.levels.length; i++) {
        const lv = t.levels[i];
        const A = t.fields(i).A;
        const runner = trunk(A, lv, near);
        const area = (await sd.maps(i)).area;
        const bake = area ? trunk(area, lv, near) : null;
        rows.push({ level: i, role: lv.role, cell: Number(lv.cell), runner_km2: km2(runner), bake_km2: km2(bake),
            at: bake ? bake.slice(1) : runner.slice(1), focus_km2: km2(trunk(A, lv, focus)) });
        if (i === mainI) near = [runner[1] - NEAR_M, runner[2] - NEAR_M, runner[1] + NEAR_M, runner[2] + NEAR_M];
    }
    const ref = rows[0].runner_km2;
    let ok = true;
    for (const r of rows.slice(1)) {
        const used = r.bake_km2 ?? r.runner_km2;
        r.source = r.bake_km2 !== null ? 'bake' : 'runner';
        r.ratio = used !== null ? +(used / ref).toFixed(3) : null;
        r.ok = r.ratio !== null && Math.abs(r.ratio - 1.0) <= TOL;
        ok = ok && r.ok;
    }
    results[name] = { main_km2: ref, levels: rows, ok, blender_d67f19e: EXPECT[name] };
    T.ok(`${name}: the trunk within 15 % of the main level's on every hero level: ${ok ? 'yes' : 'no'}, as Blender's d67f19e ` +
        `(${EXPECT[name] ? 'passes' : 'fails, its runner\'s drainage'})`, ok === EXPECT[name],
        `main ${ref} km2; ` + rows.slice(1).map((r) => `L${r.level} ${r.ratio} x (${r.source})`).join(', '));
    t.dispose?.();
}
G.shutdown();
Deno.exit(S.finish(T, 'drainage_test', { results }));
