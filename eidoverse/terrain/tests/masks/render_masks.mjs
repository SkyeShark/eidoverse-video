// The masks as a material in the three.js edition: the port's counterpart of the Blender masks package's
// render_masks.py (blender/tests/terrain/masks/render_masks.py). Each sheet reference's main tile, pinned to its
// context as the Blender masks tests pin it, drawn by the port's own ring mesh (P4's Terrain.load with meshMasks: the
// masks as point attributes eido_<mask>) with the Blender preview material's rules in a NodeMaterial, from the
// reference's 45-degree aerial camera on the judge's rig (P3's tests/judge/views.mjs viewSpec and sceneScript, as they
// are: the same sky, sun, exposure and shadows as its clay views), beside Blender's render of the same view.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/masks/render_masks.mjs [--only a,b]
//         (a Deno WebGPU job per view, each behind $EIDO_GPU_WRAP)
//
// Reads the port's main-tile masks (tests/out/masks/sheets/<name>_port_masks.npz, masks_test.mjs --only refs --sheets)
// and the stack's float32 inputs (tests/out/masks/fixtures/ref_<name>.npz). Writes tests/out/masks/renders/:
//     <name>_masks_save.npz / .json        a one-level Terrain.save of the main tile with its masks
//     <name>_masks_port_aerial_45deg.png   the port's render
//     masks_aerials_compare.png            per reference: Blender's clay reference, Blender's masks render, the
//                                          port's masks render (tests/masks/sheets_port.py --aerials composes it)
//
// The material (render_masks.py mask_material, transcribed): a principled surface of roughness 0.9 and no specular
// whose base colour starts as the palette's soil, darkened by 0.25 x wetness, then mixed toward vegetation (x 1.2 x the
// palette's veg_k, clamped), scree by rock_toe, rock by rock, water by 0.8 x channels and snow by snow; the palettes
// are the masks fixtures' PREVIEW_PALETTES (blender/tests/terrain/masks/fixtures.py), sRGB to linear as ** 2.2. A mask
// the terrain has not got reads 0, as Blender's Attribute node reads a missing attribute.

import * as Io from '../../core/io.js';
import { Level } from '../../core/levels.js';
import * as W from '../_where.mjs';
import * as V from '../judge/views.mjs';

const args = [...Deno.args];
const arg = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : null;
};
const REFS = ['lauterbrunnen', 'grand_canyon_toroweap', 'mount_fuji', 'badlands_sd', 'great_sand_dunes'];
const only = arg('--only') ? arg('--only').split(',') : REFS;
const READ = ['rock', 'rock_toe', 'snow', 'vegetation', 'wetness', 'channels'];
// blender/tests/terrain/masks/fixtures.py PREVIEW_PALETTES and PREVIEW_PALETTE_OF (display sRGB)
const PALETTES = {
    alpine: { soil: [0.42, 0.36, 0.27], veg: [0.22, 0.38, 0.13], rock: [0.52, 0.51, 0.50], scree: [0.63, 0.60, 0.55],
        snow: [0.95, 0.97, 1.0], water: [0.10, 0.22, 0.30], veg_k: 1.0 },
    volcanic: { soil: [0.30, 0.25, 0.22], veg: [0.18, 0.33, 0.12], rock: [0.22, 0.21, 0.21], scree: [0.40, 0.30, 0.26],
        snow: [0.95, 0.97, 1.0], water: [0.10, 0.22, 0.30], veg_k: 1.0 },
    desert_sandstone: { soil: [0.72, 0.52, 0.36], veg: [0.45, 0.47, 0.30], rock: [0.70, 0.40, 0.27],
        scree: [0.78, 0.60, 0.45], snow: [1, 1, 1], water: [0.10, 0.22, 0.30], veg_k: 0.25 },
    badlands: { soil: [0.78, 0.72, 0.60], veg: [0.55, 0.55, 0.35], rock: [0.70, 0.62, 0.52], scree: [0.80, 0.72, 0.60],
        snow: [1, 1, 1], water: [0.10, 0.22, 0.30], veg_k: 0.6 },
    dunes: { soil: [0.80, 0.68, 0.50], veg: [0.55, 0.52, 0.35], rock: [0.60, 0.52, 0.42], scree: [0.72, 0.62, 0.48],
        snow: [1, 1, 1], water: [0.10, 0.22, 0.30], veg_k: 0.15 },
};
const PALETTE_OF = { lauterbrunnen: 'alpine', grand_canyon_toroweap: 'desert_sandstone', mount_fuji: 'volcanic',
    badlands_sd: 'badlands', great_sand_dunes: 'dunes' };

const OUT = W.out('masks/renders');
const SHEETS = `${W.TESTS}/out/masks/sheets`;
const FIX = `${W.TESTS}/out/masks/fixtures`;

/** The material's code, put into the view's scene script after the mesh is in the world (t is the Terrain). */
function materialCode(palette, have) {
    const P = PALETTES[palette];
    const lin = (c) => c.map((v) => v ** 2.2);
    return `
    {   // the masks as a material (tests/masks/render_masks.mjs: render_masks.py mask_material's rules)
        const { attribute, mix, vec3, float, clamp } = THREE;
        const have = ${JSON.stringify(have)};
        const a = (n) => (have.includes(n) ? attribute('eido_' + n, 'float') : float(0.0));
        const c3 = (c) => vec3(c[0], c[1], c[2]);
        let col = c3(${JSON.stringify(lin(P.soil))});
        col = mix(col, vec3(0.0, 0.0, 0.0), clamp(a('wetness').mul(0.25), 0.0, 1.0));
        col = mix(col, c3(${JSON.stringify(lin(P.veg))}), clamp(a('vegetation').mul(${Math.min(1.2 * P.veg_k, 1.0)}), 0.0, 1.0));
        col = mix(col, c3(${JSON.stringify(lin(P.scree))}), clamp(a('rock_toe'), 0.0, 1.0));
        col = mix(col, c3(${JSON.stringify(lin(P.rock))}), clamp(a('rock'), 0.0, 1.0));
        col = mix(col, c3(${JSON.stringify(lin(P.water))}), clamp(a('channels').mul(0.8), 0.0, 1.0));
        col = mix(col, c3(${JSON.stringify(lin(P.snow))}), clamp(a('snow'), 0.0, 1.0));
        const mm = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.9, metalness: 0.0 });
        mm.colorNode = col;
        mm.specularIntensity = 0.0;
        mm.name = 'eido_mask_preview';
        t.mesh.material = Array.isArray(t.mesh.material) ? t.mesh.material.map(() => mm) : mm;
    }
`;
}

const rel = (p) => {
    const a = W.norm(p), r = W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};

const RP = await import('../../recipes/real_place.js');
const results = {};
for (const name of only) {
    const masksFile = `${SHEETS}/${name}_port_masks.npz`, fix = `${FIX}/ref_${name}.npz`;
    if (!W.exists(masksFile) || !W.exists(fix)) {
        console.log(`[render_masks] ${name}: no port masks or fixture (masks_test.mjs --only refs --sheets first)`);
        continue;
    }
    const meta = JSON.parse(Deno.readTextFileSync(`${SHEETS}/${name}_port_masks.json`));
    const lvd = meta.level;
    const n = lvd.nx;
    const masks = await Io.readNpz(masksFile);
    const inputs = await Io.readNpz(fix, { names: ['L1__in__h', 'L1__in__water'] });
    // a one-level Terrain.save of the main tile: its pinned height (absolute metres: base_elevation_m 0, as the
    // reference views' datum wants), its water, and the port's masks
    const level = new Level(0, 'main', lvd.x0, lvd.y0, n * lvd.cell, lvd.cell, n, null, 2, [], 16, 0);
    const arrays = [['L0__f__h', () => inputs.L1__in__h]];
    if (inputs.L1__in__water) arrays.push(['L0__f__water', () => inputs.L1__in__water]);
    for (const [k, v] of Object.entries(masks)) arrays.push([`L0__m__${k}`, () => v]);
    const base = `${OUT}/${name}_masks_save`;
    await Io.writeNpz(`${base}.npz`, arrays);
    const info = { name: `${name}_masks`, recipe_name: 'real_place', size: n * lvd.cell, resolution: n, seed: 0, quality: 'film',
        focus: null, hero_cell: null, context: null, sea_level: null, base_elevation_m: 0.0, palette: null, place: name,
        mesh_res: 512, recipe: RP.REAL_PLACE.toDict(), knobs: {}, plan: [level.toDict()], api_version: 1,
        note: 'the masks tests\' pinned main tile of the reference with the port\'s masks (tests/masks/render_masks.mjs)' };
    Deno.writeTextFileSync(`${base}.json`, JSON.stringify(info, null, 1));
    const loaded = V.loadViews(name);
    if (!loaded?.views?.aerial) {
        console.log(`[render_masks] ${name}: no reference views (the Blender edition's reference/renders)`);
        continue;
    }
    const spec = V.viewSpec('aerial', loaded.views.aerial, info, info.plan, loaded.datum);
    spec.save = base;
    const work = `${OUT}/_scenes`;
    Deno.mkdirSync(work, { recursive: true });
    const label = `${name}_masks_port`;
    spec.usedJson = `${work}/${label}_aerial_used.json`;
    const have = READ.filter((k) => k in masks);
    let script = V.sceneScript(spec);
    const load = 'const t = await T.Terrain.load(V.save, { renderer, THREE, log: () => {} });';
    const add = '    world.add(t.mesh);\n';
    if (!script.includes(load) || !script.includes(add)) throw new Error('render_masks: views.mjs sceneScript changed: update the two hooks');
    script = script.replace(load, `const t = await T.Terrain.load(V.save, { renderer, THREE, log: () => {}, meshMasks: ${JSON.stringify(have)} });`)
        .replace(add, add + materialCode(PALETTE_OF[name], have));
    const file = `${work}/${label}_aerial.js`, config = `${work}/${label}_aerial.json`, video = `${work}/${label}_aerial.mp4`;
    Deno.writeTextFileSync(file, script);
    Deno.writeTextFileSync(config, JSON.stringify({ width: spec.width, height: spec.height, fps: 30, duration: 1 / 30,
        script: rel(file), outputVideo: rel(video), capture: { at: [0], jump: true } }, null, 1));
    const argv = W.gpuArgv([W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
        'eidoverse/render_scene.mjs', rel(config)], { cwd: W.REPO });
    const t0 = performance.now();
    const code = await W.run(argv, { cwd: W.REPO, log: `${work}/${label}_aerial.log`,
        env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
    const shot = `${work}/${label}_aerial_at0.00s.png`, png = `${OUT}/${label}_aerial_45deg.png`;
    const ok = code === 0 && W.exists(shot);
    if (ok) Deno.renameSync(shot, png);
    results[name] = { ok, png: ok ? png : null, code, seconds: +((performance.now() - t0) / 1000).toFixed(1), read: have,
        palette: PALETTE_OF[name], log: `${work}/${label}_aerial.log` };
    console.log(`[render_masks] ${name}: ${ok ? png : `FAILED (exit ${code}): see ${work}/${label}_aerial.log`} (${results[name].seconds} s)`);
}
Deno.writeTextFileSync(`${OUT}/render_masks.json`, JSON.stringify(results, null, 1));
