// real_place Lauterbrunnen with hero levels through the port's whole generator (PORT_PLAN.md 8.2 row P12: "then on
// real_place Lauterbrunnen the hero levels add detail without moving the landform (main metrics within 1 %); eye
// views show rills, ribs and talus"), as the Blender detail package runs it (blender/tests/terrain/detail/
// run_real_place.py): film quality, seed 1, the focus its lauterbrunnen_truth.focus() gives (the reference's eye spot
// and the robot's spot 14 m along the view), in two variants of the registered recipe:
//   upsampled   the stage dem alone: the hero levels are the DEM upsampled
//   detail      dem, breakup and hydraulic: this package's ops on every hero level (4, 2, 1 and 0.5 m)
//   full        the registered recipe (dem, fluvial, talus, breakup, hydraulic: the fluvial package's refine and talus
//               before this package's ops on every hero level)
//   fluvial     the same without this package's ops (dem, fluvial, talus): the ground they start from in the full
//               variant, to tell a difference that enters before them from one that arises in them
// Each is made by api.js generate (the level runner, the ops, the masks when masks.js is in, the ring mesh) and saved
// (Terrain.save) under tests/out/detail/real_place/<variant>. Then, with Blender's Python, tests/detail/landform.py
// for each variant other than upsampled: the Blender package's own landform numbers (sheets.py landform_vs: each hero
// level at the main 8 m pixel, with and without the variant's hero stages, slope percentiles within max(1 %,
// 0.25 deg), relief within 1 %, the hypsometric integral within 0.01, the main level identical), the hero levels
// against Blender's own run of the same variant (tests/detail/blender_detail_runs.py: lauterbrunnen_film for detail,
// lauterbrunnen_film_full for full) when it is there, and the Blender package's hillshade sheets beside the real ground
// (real_place/sheets/<variant>_L<i>.png).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/detail/real_place_test.mjs
//         [--variants upsampled,detail] [--quality film] [--skip-generate]
//     (a GPU job: on a shared machine behind $EIDO_GPU_WRAP; needs the Lauterbrunnen DEM: $EIDO_TERRAIN_DEMS or
//     $EIDO_BLENDER_EDITION; with --skip-generate it judges the saves already made, no GPU)
//
// Writes tests/out/detail/real_place_test.json (real_place_<variant>.json for other variants, e.g. --variants full),
// and real_place/landform.json (the detail variant), real_place/landform_<variant>.json for the others. The eye views
// are tests/detail/views.mjs's.

import * as API from '../../api.js';
import * as G from '../../core/gpu.js';
import * as RG from '../../recipes/index.js';
import * as D from './_detail.mjs';

const { C, W } = D;
const A = D.argsOf();
const VARIANTS = A.list('--variants') ?? ['upsampled', 'detail'];
const QUALITY = A.opt('--quality', 'film');
const KEEP = { upsampled: ['dem'], detail: ['dem', 'breakup', 'hydraulic'], full: null, fluvial: ['dem', 'fluvial', 'talus'] };
const OUT = `${W.out('detail')}/real_place`;
const T = new C.Checks('detail: real_place Lauterbrunnen with hero levels');

/** lauterbrunnen_truth.focus(): the reference's eye spot and the robot's spot 14 m along the view, Blender frame. */
function focus() {
    const edition = W.blenderEdition();
    if (!edition) return null;
    const eye = JSON.parse(Deno.readTextFileSync(`${edition}/blender/tests/terrain/reference/renders/lauterbrunnen_views.json`)).eye;
    const [ex, ey] = eye.camera, [tx, ty] = eye.target;
    const L = Math.hypot(tx - ex, ty - ey), ux = (tx - ex) / L, uy = (ty - ey) / L;
    return [[ex, ey], [ex + 14.0 * ux + 1.6 * uy, ey + 14.0 * uy - 1.6 * ux]];
}

const pts = focus();
if (!pts) {
    console.log('[skip] real_place: needs the Blender edition ($EIDO_BLENDER_EDITION) for the reference views and the DEMs');
    Deno.exit(0);
}
const records = {};
if (!A.flag('--skip-generate')) {
    await G.init();
    for (const v of VARIANTS) {
        const d = RG.get('real_place').toDict();
        if (KEEP[v]) d.stages = d.stages.filter((s) => KEEP[v].includes(s.op));
        const lines = [];
        const t0 = performance.now();
        const t = await API.generate({ recipe: d, params: { dem: 'lauterbrunnen' }, seed: 1, quality: QUALITY, cache: false,
            focus: pts.map(([x, y]) => [x, -y]), name: `real_place_${v}`, log: (m) => { lines.push(String(m)); console.log(m); } });
        const sec = (performance.now() - t0) / 1000;
        Deno.mkdirSync(`${OUT}/${v}`, { recursive: true });
        await t.save(`${OUT}/${v}/terrain`);
        records[v] = { seconds: +sec.toFixed(1), info_seconds: t.info.seconds, skipped: t.info.skipped_stages,
            levels: t.levels.map((lv) => String(lv)), log: lines.filter((l) => /terrain\.(hydraulic|detail|run)/.test(l)) };
        T.ok(`port ${v}: made and saved (${t.levels.length} levels, ${sec.toFixed(1)} s)`, t.levels.some((lv) => lv.role === 'hero'),
            `skipped stages: ${JSON.stringify(t.info.skipped_stages)}`);
        t.dispose?.();
    }
    G.shutdown();
}
// the Blender package's own numbers on the port's saves (and the Blender run's of the same variant, beside)
const BLENDER_RUN = { detail: 'lauterbrunnen_film', full: 'lauterbrunnen_film_full', fluvial: 'lauterbrunnen_film_fluvial' };
for (const variant of VARIANTS.filter((v) => v !== 'upsampled')) {
    if (!W.exists(`${OUT}/${variant}/terrain.npz`) || !W.exists(`${OUT}/upsampled/terrain.npz`)) {
        T.ok(`${variant}: landform numbers`, false, `no save of the ${variant} or the upsampled variant under ${OUT}`);
        continue;
    }
    const bsave = `${W.out('detail')}/runs/${BLENDER_RUN[variant] ?? variant}/base/terrain`;
    const json = `${OUT}/${variant === 'detail' ? 'landform' : `landform_${variant}`}.json`;
    const py = W.pythonCmd(`${W.TESTS}/detail/landform.py`, `${OUT}/${variant}/terrain`, `${OUT}/upsampled/terrain`,
        ...(W.exists(`${bsave}.npz`) ? ['--blender', bsave] : []), '--variant', variant, '--out', json, '--sheets', OUT);
    if (!py) {
        T.ok(`${variant}: landform numbers`, false, 'needs Blender\'s Python (EIDO_BLENDER_PYTHON)');
        continue;
    }
    await W.run(py, { env: { ...Deno.env.toObject(), PYTHONDONTWRITEBYTECODE: '1' } });
    const L = C.readJson(json);
    const lv = L?.port?.landform_vs, bl = L?.blender?.landform_vs ?? null;
    // the rule on the port, number by number; where the Blender edition's own run of the variant misses the rule
    // too, the port's change within 1.25 x Blender's (the source of truth's result is what the port reproduces)
    const misses = [];
    const fmt = (r) => r.diff ?? r.rel;
    for (const [i, row] of Object.entries(lv ?? {})) {
        if (typeof row !== 'object') continue;
        for (const [k, r] of Object.entries(row)) {
            if (typeof r !== 'object' || r === null || !('ok' in r) || r.ok) continue;
            const b = bl?.[i]?.[k];
            const within = b && b.ok === false && Math.abs(fmt(r)) <= 1.25 * Math.abs(fmt(b));
            misses.push(`L${i} ${k} ${fmt(r)} (Blender's run ${b ? fmt(b) : '?'}${b?.ok === false ? ', also over' : ''}): ${within ? 'as Blender' : 'OVER'}`);
            if (!within) row._over = true;
        }
    }
    const over = Object.values(lv ?? {}).some((r) => typeof r === 'object' && r?._over);
    const stages = { detail: 'breakup, hydraulic', fluvial: 'fluvial, talus' }[variant] ?? 'all the recipe\'s';
    const diagnostic = variant === 'detail' ? '' : ' [a diagnostic, not this package\'s acceptance: the registered recipe ' +
        'whole is P4\'s gate (PORT_PLAN.md 8.4); the fluvial variant shows what enters before this package\'s ops]';
    T.ok(`${variant}: the hero levels' stages (${stages}) add detail without moving the landform${diagnostic} ` +
        '(the Blender detail package\'s landform_vs rule: slope ' +
        'percentiles within max(1 %, 0.25 deg), relief within 1 %, hypsometric integral within 0.01, main level identical; ' +
        'a number Blender\'s own run misses too within 1.25 x Blender\'s change)',
    lv && lv.main_level_identical && !over, lv ? `main level identical ${lv.main_level_identical}; ` + Object.entries(lv).filter(([, r]) => typeof r === 'object')
        .map(([i, r]) => `L${i}: p50 ${r.slope_deg_p50.diff >= 0 ? '+' : ''}${r.slope_deg_p50.diff}, p99 ${r.slope_deg_p99.diff >= 0 ? '+' : ''}${r.slope_deg_p99.diff} deg, ` +
            `relief ${(r.relief_m.rel * 100).toFixed(2)} %, HI ${r.hypsometric_integral.diff}`).join('; ') +
        (misses.length ? `; outside the rule: ${misses.join('; ')}` : '') + (bl ? '' : '; (no Blender run of this variant to compare a miss with)') : 'no numbers');
    if (L?.vs_blender && typeof L.vs_blender === 'object') {
        const rows = Object.entries(L.vs_blender);
        T.ok(`${variant}: the port's run against Blender's, level by level (RMS of |dh| over relief)`, true,
            rows.map(([i, r]) => `L${i} ${r.role} ${r.cell} m ${C.sci(r.rms_over_relief, 2)}${r.bit_identical ? ' (identical)' : ''}`).join('; '));
    }
    records[variant === 'detail' ? 'landform' : `landform_${variant}`] = L;
}
T.extra.records = records;
const other = VARIANTS.filter((v) => !['upsampled', 'detail'].includes(v));
Deno.exit(D.finish(T, other.length ? `real_place_${other.join('_')}` : 'real_place_test'));
