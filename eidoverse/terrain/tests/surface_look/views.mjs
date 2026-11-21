// The look package's renders (PORT_PLAN.md 8.2 row P18; SURFACING_DESIGN.md 5.4 package 3 and section 6): the
// surfacing judge's views (blender/tests/terrain/surfacing_judge/views.json) of every recipe, rendered by this edition
// from the same saved terrains Blender's final check rendered (its out/surfacing/review/<recipe>/<recipe>_final2_
// record.json names each view's terrain and the views built together), so a port frame lies beside Blender's frame
// of the same ground and camera and beside the photograph. The orchestrator (this file, no GPU) picks the terrains
// and runs the scene side (_scene.js, the port of review_views.py's render_group) as render jobs.
//
//     EIDO_BLENDER_EDITION=<a checkout of the blender branch> EIDO_GPU_WRAP='<the GPU queue>' \
//         deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surface_look/views.mjs
//         [--views canyon,real_place/ridge_schynige,...] [--snap <folder>[,<folder>...]] [--label port]
//         [--ref final2] [--palettes <palettes.js>] [--k 2] [--per-job 3] [--no-layers] [--no-plants] [--no-rocks]
//         [--backend vulkan] [--memcap 20] [--clay] [--force] [--dry]
//
//   --views     recipes, or recipe/view, of views.json (default: every view the --ref state rendered)
//   --snap      folders of saved terrains (Terrain.save: <recipe>_<view>[_j].npz for a view with a focus, as the
//               review's --snap; <recipe>.npz for the judge's terrain of a recipe). A view without a focus takes the
//               judge's out/surfacing_judge/terrains/<recipe>.npz only when that file is no newer than the --ref
//               render (a later round may have made it again: then the view looks in --snap, else it is skipped)
//   --palettes  a palettes module to render with in place of build/palettes.js (palettes_check.py --override: the
//               edition's data block), through an import map: Blender's review_views.py --palettes. The record names it
//   --k         the frames at k x 960 x 540, averaged k x k by develop.py (EEVEE's 16 samples a pixel)
//   --per-job   terrain groups per render job (one GPU-queue job each, run one after another)
//   --backend   $DENO_WEBGPU_BACKEND for the jobs (vulkan: the material's first compile in seconds, D3D12's in minutes)
//   --clay      a probe: each view again with the ground in grey clay (<view>_clay.f16), where the light falls
//   --shadow-near <m>  a probe: an eye view's sun shadow map over its first m metres only (EEVEE's virtual shadow
//               maps resolve a sward's own shadows; one map over a kilometre does not)
//   --log-material  the material's own log lines in the job's log (applySurface: textures, the far rings, a layer
//               falling back for a missing map)
//
// Writes tests/out/surface_look/states/<label>/<recipe>/<view>.f16 and .json (the scene-linear frame), <view>_layers.f16
// (the layer map), <view>_three.png (the canvas frame through three's AgX, as the edition renders a film), record.json
// (each view's record, the shape of review_views.py's: camera, heading, pitch, lens, levels, far edges, plants, rocks,
// seconds) and plan.json (which terrain each view took, and every view left out with the reason). Then
//     python eidoverse/terrain/tests/surface_look/develop.py --state <label>
// writes the state's <view>.png and <view>_layers.png, the frozen-state layout surfacing_judge/states.py reads.

import * as W from '../_where.mjs';
import * as M from '../surfacing/_material.mjs';

const A = M.argsOf();
const label = A.opt('--label', 'port');
const ref = A.opt('--ref', 'final2');
const want = A.list('--views', null);
const snapDirs = (A.opt('--snap', Deno.env.get('EIDO_VIEW_SNAPS') ?? '') ?? '').split(',').filter(Boolean).map((p) => W.norm(p));
const k = Number(A.opt('--k', '2'));
const perJob = Number(A.opt('--per-job', '3'));
const palettesFile = A.opt('--palettes', null);
const backend = A.opt('--backend', 'vulkan');
const memcap = A.opt('--memcap', '20');
const dry = A.flag('--dry');
const edition = W.needBlenderEdition('the judge\'s views, records and terrains');
if (!edition) Deno.exit(0);
const tests = W.blenderTests();
const judge = JSON.parse(Deno.readTextFileSync(`${tests}/surfacing_judge/views.json`));
const review = `${tests}/out/surfacing/review`;
const judgeTerrains = `${tests}/out/surfacing_judge/terrains`;
const root = `${W.out('surface_look')}/states/${label}`;
const work = `${W.out('surface_look')}/_jobs`;
Deno.mkdirSync(root, { recursive: true });
Deno.mkdirSync(work, { recursive: true });

const mtime = (p) => Deno.statSync(p).mtime?.getTime() ?? 0;
const records = {};
function refRecord(recipe) {
    if (!(recipe in records)) {
        const p = `${review}/${recipe}/${recipe}_${ref}_record.json`;
        records[recipe] = W.exists(p) ? JSON.parse(Deno.readTextFileSync(p)) : {};
    }
    return records[recipe];
}

// the views asked for: recipes or recipe/view, each a view the --ref state rendered
const asked = [];
for (const recipe of Object.keys(judge)) {
    for (const v of judge[recipe].views) {
        const id = `${recipe}/${v.name}`;
        if (want && !want.includes(recipe) && !want.includes(id)) continue;
        asked.push([recipe, v]);
    }
}

// each view's terrain, as the --ref render took it
const skipped = [], groups = new Map();
for (const [recipe, v] of asked) {
    const rr = refRecord(recipe)[`${v.name}_${ref}`];
    const png = `${review}/${recipe}/${v.name}_${ref}.png`;
    if (!A.flag('--force') && W.exists(`${root}/${recipe}/${v.name}.f16`)) {
        skipped.push({ view: `${recipe}/${v.name}`, why: 'rendered in this state already (--force renders it again)', done: true });
        continue;
    }
    if (!rr || !W.exists(png)) {
        skipped.push({ view: `${recipe}/${v.name}`, why: `no ${ref} render or record in ${review}/${recipe}` });
        continue;
    }
    let snap = null, why = null;
    const names = v.focus ? [rr.terrain, `${recipe}_${v.name}_j.npz`, `${recipe}_${v.name}.npz`] : [`${recipe}.npz`];
    if (!v.focus) {
        const jt = `${judgeTerrains}/${recipe}.npz`;
        if (W.exists(jt) && mtime(jt) <= mtime(png)) snap = jt;
        else if (W.exists(jt)) why = `the judge's ${recipe}.npz was made again after the ${ref} render (${new Date(mtime(jt)).toISOString()})`;
        else why = `no judge terrain ${jt}`;
    }
    for (const dir of snap ? [] : snapDirs) {
        for (const nm of names) {
            if (!snap && nm && nm !== 'generated' && W.exists(`${dir}/${nm}`) && W.exists(`${dir}/${nm.replace(/\.npz$/, '.json')}`)) snap = `${dir}/${nm}`;
        }
    }
    if (!snap) {
        skipped.push({ view: `${recipe}/${v.name}`, why: why ?? `no saved terrain (${names.filter(Boolean).join(' or ')}) in --snap`,
            ref_terrain: rr.terrain });
        continue;
    }
    const together = (rr.views_built_together ?? [v.name]).map((n) => judge[recipe].views.find((x) => x.name === n)).filter(Boolean);
    const key = `${recipe}|${snap}`;
    if (!groups.has(key)) {
        groups.set(key, { recipe, snap, group: together, views: [], bakeDir: `${W.out('surface_look')}/bakes/${recipe}_${snap.split('/').pop().replace(/\.npz$/, '')}` });
    }
    groups.get(key).views.push(v);
}
const gl = [...groups.values()];
// plan.json keeps every view this state has rendered or left out, run after run: its terrain and the views built with it
const planPath = `${root}/plan.json`;
const plan = W.exists(planPath) ? JSON.parse(Deno.readTextFileSync(planPath)) : { label, ref, views: {}, skipped: {} };
Object.assign(plan, { ref, k, palettes: palettesFile, snap: snapDirs });
for (const g of gl) {
    for (const v of g.views) {
        plan.views[`${g.recipe}/${v.name}`] = { terrain: g.snap, built_together: g.group.map((x) => x.name) };
        delete plan.skipped[`${g.recipe}/${v.name}`];
    }
}
for (const s of skipped) if (!s.done) plan.skipped[s.view] = s;
Deno.writeTextFileSync(planPath, JSON.stringify(plan, null, 1));
console.log(`[look views] ${gl.reduce((a, g) => a + g.views.length, 0)} views on ${gl.length} terrains; ${skipped.length} left out:`);
for (const s of skipped) console.log(`  - ${s.view}: ${s.why}`);
for (const g of gl) console.log(`  + ${g.recipe} ${g.snap.split('/').pop()}: ${g.views.map((v) => v.name).join(', ')}` +
    (g.group.length > g.views.length ? ` (planted along ${g.group.map((v) => v.name).join(', ')})` : ''));
if (dry || !gl.length) Deno.exit(0);

// the import map of a --palettes render: this checkout's deno.json imports, and build/palettes.js -> the given file
let importMap = null;
if (palettesFile) {
    const cfg = JSON.parse(Deno.readTextFileSync(`${W.REPO}/deno.json`));
    const key = new URL('../../build/palettes.js', import.meta.url).href;
    const val = new URL('file:///' + W.norm(W.absPath(palettesFile)).replace(/^\/+/, '')).href;
    importMap = `${work}/${label}_import_map.json`;
    Deno.writeTextFileSync(importMap, JSON.stringify({ imports: { ...(cfg.imports ?? {}), [key]: val }, scopes: cfg.scopes ?? {} }, null, 1));
}
const rel = (p) => {
    const a = W.norm(p), r = W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};
const sets = M.useSets();
let failed = 0;
for (let j0 = 0; j0 < gl.length; j0 += perJob) {
    const jg = gl.slice(j0, j0 + perJob);
    const tag = `${label}_${String(j0 / perJob).padStart(2, '0')}`;
    const frames = [];
    jg.forEach((g, gi) => {
        const dir = `${root}/${g.recipe}`;
        Deno.mkdirSync(dir, { recursive: true });
        for (const v of g.views) frames.push({ g: gi, recipe: g.recipe, view: v.name, v, dir, focus: v.focus ? true : null });
    });
    const spec = { W: 960, H: 540, k, msaa: 4, exposureEv: -0.5, hours: 15.5, sunLeftDeg: 70.0, sunElevationDeg: 37.7, shadowMap: 4096,
        plants: !A.flag('--no-plants'), layers: !A.flag('--no-layers'), rocks: !A.flag('--no-rocks'), clay: A.flag('--clay'), second: true, sets,
        shadowNearM: Number(A.opt('--shadow-near', '0')) || null, logMaterial: A.flag('--log-material'),
        palettesFile: palettesFile ? W.norm(W.absPath(palettesFile)) : null, standM: 1.5, eyeCameraM: 50.0, vistaStepM: 2.0,
        vistaGapM: 4.0, vistaWiden: 1.1, recordPath: `${work}/${tag}_records.json`,
        groups: jg.map((g) => ({ recipe: g.recipe, snap: g.snap, bakeDir: g.bakeDir, group: g.group, views: g.views.map((v) => v.name) })),
        frames };
    const specPath = `${work}/${tag}_spec.json`, config = `${work}/${tag}.json`, video = `${work}/${tag}.mp4`;
    Deno.writeTextFileSync(specPath, JSON.stringify(spec, null, 1));
    Deno.writeTextFileSync(config, JSON.stringify({ width: spec.W, height: spec.H, fps: 1, duration: frames.length,
        script: rel(W.urlPath(new URL('./_scene.js', import.meta.url))), outputVideo: rel(video),
        capture: { at: frames.map((_f, i) => i), jump: true } }, null, 1));
    const deno = [W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
        ...(importMap ? ['--import-map', importMap] : []), 'eidoverse/render_scene.mjs', rel(config)];
    const argv = W.gpuArgv(deno, { cwd: W.REPO });
    const log = `${work}/${tag}.log`;
    const env = { ...Deno.env.toObject(), EIDO_LOOK_SPEC: specPath, RENDER_CODEC: 'libx264', RENDER_CQ: '0',
        GPU_MEMCAP_GB: memcap, HEAVY_VRAM_GB: Deno.env.get('HEAVY_VRAM_GB') ?? '8' };
    if (backend && backend !== 'default') env.DENO_WEBGPU_BACKEND = backend;
    const t0 = performance.now();
    console.log(`[look views] job ${tag}: ${frames.map((f) => f.recipe + '/' + f.view).join(', ')} (log ${log})`);
    const code = await W.run(argv, { cwd: W.REPO, log, env });
    // the canvas frames (three's AgX): render_scene's captures, else extracted from its video
    const shot = (i) => `${work}/${tag}_at${i.toFixed(2)}s.png`;
    if (!frames.every((_f, i) => W.exists(shot(i))) && W.exists(video)) {
        const base = video.replace(/\.mp4$/, '');
        const p = new Deno.Command(Deno.env.get('FFMPEG_PATH') || 'ffmpeg', { args: ['-y', '-loglevel', 'error', '-i', video,
            '-fps_mode', 'passthrough', `${base}_cap%d.png`], stdout: 'null', stderr: 'piped' }).outputSync();
        if (p.code === 0) frames.forEach((_f, i) => { if (W.exists(`${base}_cap${i + 1}.png`)) Deno.renameSync(`${base}_cap${i + 1}.png`, shot(i)); });
    }
    frames.forEach((f, i) => { if (W.exists(shot(i))) Deno.renameSync(shot(i), `${f.dir}/${f.view}_three.png`); });
    // the records, merged into each recipe's record.json ({view: record})
    const recs = W.exists(spec.recordPath) ? JSON.parse(Deno.readTextFileSync(spec.recordPath)) : [];
    const byRecipe = {};
    for (const r of recs) {
        if (!r.view || !r.record) continue;
        (byRecipe[r.recipe] ??= {})[r.view] = r.record;
    }
    for (const [recipe, rs] of Object.entries(byRecipe)) {
        const p = `${root}/${recipe}/record.json`;
        const old = W.exists(p) ? JSON.parse(Deno.readTextFileSync(p)) : {};
        Deno.writeTextFileSync(p, JSON.stringify({ ...old, ...rs }, null, 1));
    }
    const done = frames.filter((f) => W.exists(`${f.dir}/${f.view}.f16`)).length;
    const errs = recs.filter((r) => r.error);
    console.log(`[look views] job ${tag}: ${done} of ${frames.length} views written in ${((performance.now() - t0) / 1000).toFixed(0)} s ` +
        `(exit ${code})` + (errs.length ? `; errors: ${errs.map((e) => (e.view ?? e.views) + ': ' + String(e.error).split('\n')[0]).join(' | ')}` : ''));
    if (done < frames.length) failed += frames.length - done;
}
Deno.exit(failed ? 1 : 0);
