// Port of blender/eidoblend/terrain/bake.py at f90c6fc.
//
// Bake a terrain from the command line (design section 8): fill the cache and write the preview PNGs, so an agent can
// try a recipe without building a scene. From the repository root:
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/bake.mjs --recipe dunes --size 6000 --seed 3 --out <dir>
//     deno run ... eidoverse/terrain/bake.mjs --recipe real_place --param dem=lauterbrunnen --focus 480,-1640 --out <dir>
//     deno run ... eidoverse/terrain/bake.mjs --describe real_place
//
// Options: --recipe NAME (or a recipe .json), --size M, --resolution N, --seed N, --quality draft|film|hero,
// --focus X,Z[;X,Z...], --hero-cell M, --context K, --param KNOB=VALUE (repeatable; numbers parsed) or --params JSON,
// --no-cache, --save (also write the terrain: <out>/<name>.npz + .json, the Terrain.save format both editions read),
// --name NAME, --out DIR, --list, --describe NAME. Writes <out>/<name>_main_hillshade.png, _hero_hillshade.png,
// _mask_<name>.png and <name>_bake.json (the plan, the timings, the cache key, the main tile's metrics). The kernels
// need a WebGPU device: on a shared machine put $EIDO_GPU_WRAP in front (--list and --describe need none).
//
// Where this differs from bake.py, and why:
//   - --focus takes three.js ground coordinates, x east and z south, as makeTerrain's focus does (PORT_PLAN.md 2.2:
//     one spelling of a call's options, in the edition's frame), so a scene's focus and its pre-bake are the same
//     numbers and hit the same cache entry. Blender's `bake.py --focus x,y` is `bake.mjs --focus x,-y`. The record
//     keeps both: the bake JSON's focus as given and the levels in Blender's frame (Level's text), as every saved
//     file of both editions is.
//   - The arguments are parsed as argparse parses bake.py's (long options, --opt=value, unique prefixes, the same
//     types and choices, exit code 2 on a usage error), by a few lines here: Deno has no argparse.
//   - A terrain that is not in the cache needs the level runner (run.js, another package of the port): until it is
//     in the checkout, generate() says so and this exits 1 with that message, where bake.py would bake.

import * as A from './api.js';
import * as G from './core/gpu.js';
import { plain } from './core/cache.js';
import { pyStr } from './core/levels.js';

const PROG = 'bake.mjs';

// [name, kind, metavar or choices, default, help]; kind: str, float, int, flag, append
const OPTIONS = [
    ['--recipe', 'str', 'RECIPE', null, 'a recipe name (--list shows them), or a recipe .json (recipe.toDict(), edited)'],
    ['--size', 'float', 'SIZE', null, 'metres, the main tile\'s side (default: the recipe\'s)'],
    ['--resolution', 'int', 'RESOLUTION', null, 'cells across the main tile (default: the quality\'s)'],
    ['--seed', 'int', 'SEED', 0, 'the random seed of every stage'],
    ['--quality', 'choice', ['draft', 'film', 'hero'], 'film', 'draft | film | hero'],
    ['--focus', 'str', 'FOCUS', null, 'x,z or x,z;x,z;... in metres, three.js ground coordinates (z south): hero levels there'],
    ['--hero-cell', 'float', 'HERO_CELL', null, 'metres, the finest cell around the focus'],
    ['--context', 'float', 'CONTEXT', null, 'the horizon levels\' extent multiplier'],
    ['--param', 'append', 'PARAM', [], 'knob=value (repeatable)'],
    ['--params', 'str', 'PARAMS', null, 'the knobs as a JSON object'],
    ['--no-cache', 'flag', null, false, 'neither read nor write the cache'],
    ['--save', 'flag', null, false, 'also write the terrain: <out>/<name>.npz + .json'],
    ['--name', 'str', 'NAME', null, 'the files\' base name (default <recipe>[_<dem>]_s<seed>)'],
    ['--out', 'str', 'OUT', '.', 'the folder written to'],
    ['--list', 'flag', null, false, 'list the recipes'],
    ['--describe', 'str', 'DESCRIBE', null, 'a recipe\'s stages, knobs and references'],
];

class UsageError extends Error {}

const dest = (opt) => opt.slice(2).replace(/-/g, '_');
const metavar = (o) => (o[1] === 'choice' ? `{${o[2].join(',')}}` : o[2]);

function usage() {
    return `usage: ${PROG} [-h] ` + OPTIONS.map((o) => (o[1] === 'flag' ? `[${o[0]}]` : `[${o[0]} ${metavar(o)}]`)).join(' ');
}

function help() {
    const lines = [usage(), '', 'bake a terrain: cache + preview PNGs', '', 'options:', '  -h, --help            show this help message and exit'];
    for (const o of OPTIONS) {
        const head = o[1] === 'flag' ? `  ${o[0]}` : `  ${o[0]} ${metavar(o)}`;
        lines.push(head.length <= 22 ? head.padEnd(24) + o[4] : head + '\n' + ' '.repeat(24) + o[4]);
    }
    return lines.join('\n');
}

// Python's int() and float() of a command-line string
function pyInt(s) {
    const t = s.trim();
    if (!/^[+-]?\d+(_\d+)*$/.test(t)) return null;
    return Number(t.replace(/_/g, ''));
}

function pyFloat(s) {
    const t = s.trim().toLowerCase();
    if (/^[+-]?(inf|infinity)$/.test(t)) return t.startsWith('-') ? -Infinity : Infinity;
    if (/^[+-]?nan$/.test(t)) return NaN;
    if (!/^[+-]?((\d+(_\d+)*)(\.(\d+(_\d+)*)?)?|\.\d+(_\d+)*)(e[+-]?\d+(_\d+)*)?$/.test(t)) return null;
    return Number(t.replace(/_/g, ''));
}

/** The arguments as argparse gives bake.py's: { recipe, size, ..., describe }. Throws UsageError. */
export function parse(argv) {
    const out = Object.fromEntries(OPTIONS.map((o) => [dest(o[0]), Array.isArray(o[3]) ? [...o[3]] : o[3]]));
    out.help = false;
    const extra = [];
    for (let k = 0; k < argv.length; k++) {
        const arg = argv[k];
        if (arg === '-h' || arg === '--help') {
            out.help = true;
            continue;
        }
        if (!arg.startsWith('--') || arg === '--') {
            extra.push(arg);
            continue;
        }
        const eq = arg.indexOf('=');
        const name = eq >= 0 ? arg.slice(0, eq) : arg;
        let o = OPTIONS.find((p) => p[0] === name);
        if (!o) {                                          // argparse's unique prefixes
            const hits = OPTIONS.filter((p) => p[0].startsWith(name));
            if (hits.length > 1) {
                throw new UsageError(`ambiguous option: ${name} could match ${hits.map((p) => p[0]).join(', ')}`);
            }
            o = hits[0] ?? null;
        }
        if (!o) {
            extra.push(arg);
            continue;
        }
        const key = dest(o[0]);
        if (o[1] === 'flag') {
            if (eq >= 0) throw new UsageError(`argument ${o[0]}: ignored explicit argument '${arg.slice(eq + 1)}'`);
            out[key] = true;
            continue;
        }
        let value;
        if (eq >= 0) {
            value = arg.slice(eq + 1);
        } else {
            if (k + 1 >= argv.length || (argv[k + 1].startsWith('--') && argv[k + 1].length > 2)) {
                throw new UsageError(`argument ${o[0]}: expected one argument`);
            }
            value = argv[++k];
        }
        if (o[1] === 'int') {
            const v = pyInt(value);
            if (v === null) throw new UsageError(`argument ${o[0]}: invalid int value: '${value}'`);
            out[key] = v;
        } else if (o[1] === 'float') {
            const v = pyFloat(value);
            if (v === null) throw new UsageError(`argument ${o[0]}: invalid float value: '${value}'`);
            out[key] = v;
        } else if (o[1] === 'choice') {
            if (!o[2].includes(value)) {
                throw new UsageError(`argument ${o[0]}: invalid choice: '${value}' (choose from ${o[2].map((c) => `'${c}'`).join(', ')})`);
            }
            out[key] = value;
        } else if (o[1] === 'append') {
            out[key].push(value);
        } else {
            out[key] = value;
        }
    }
    if (extra.length) throw new UsageError(`unrecognized arguments: ${extra.join(' ')}`);
    return out;
}

// bake.py _value: a JSON value when the text is one (Python's json also reads NaN and the infinities), else the text
function value(s) {
    if (s === 'NaN') return NaN;
    if (s === 'Infinity') return Infinity;
    if (s === '-Infinity') return -Infinity;
    try {
        return JSON.parse(s);
    } catch (_e) {
        return s;
    }
}

const isFile = (p) => {
    try {
        return Deno.statSync(p).isFile;
    } catch (_e) {
        return false;
    }
};
const join = (a, b) => (a.endsWith('/') || a.endsWith('\\') ? a + b : `${a}/${b}`);
const round2 = (s) => Math.round(s * 100) / 100;

/** bake.py main: returns the exit code. */
export async function main(argv = Deno.args) {
    const k = argv.indexOf('--');
    if (k >= 0) argv = argv.slice(k + 1);
    let a;
    try {
        a = parse(argv);
    } catch (e) {
        if (!(e instanceof UsageError)) throw e;
        console.error(`${usage()}\n${PROG}: error: ${e.message}`);
        return 2;
    }
    if (a.help) {
        console.log(help());
        return 0;
    }
    if (a.list) {
        for (const [name, title] of Object.entries(A.recipes())) console.log(`${name.padEnd(22)} ${title}`);
        return 0;
    }
    if (a.describe) {
        await A.describe(a.describe);
        return 0;
    }
    if (!a.recipe) {
        console.error(`${PROG}: --recipe is required (--list shows them)`);
        return 2;
    }
    let recipe = a.recipe;
    if (recipe.toLowerCase().endsWith('.json') && isFile(recipe)) recipe = JSON.parse(Deno.readTextFileSync(recipe));
    const params = a.params ? JSON.parse(a.params) : {};
    for (const kv of a.param) {
        const eq = kv.indexOf('=');
        const key = (eq >= 0 ? kv.slice(0, eq) : kv).trim(), v = (eq >= 0 ? kv.slice(eq + 1) : '').trim();
        params[key] = value(v);
    }
    let focus = null;
    if (a.focus) {
        const pts = a.focus.split(';').filter((p) => p.trim()).map((p) => p.split(',').map((c) => {
            const v = pyFloat(c);
            if (v === null) throw new TypeError(`--focus: could not convert string to float: '${c}'`);
            return v;
        }));
        focus = pts.length === 1 ? pts[0] : pts;
    }
    const t0 = performance.now();
    let t;
    try {
        t = await A.generate({ recipe, size: a.size, resolution: a.resolution, seed: a.seed, params, focus,
            heroCell: a.hero_cell, context: a.context, quality: a.quality, cache: !a.no_cache });
    } catch (e) {
        if (e?.name !== 'NotPortedError') throw e;
        console.error(`${PROG}: ${e.name}: ${e.message}`);
        return 1;
    }
    try {
        const name = a.name || (t.recipe.name + ('dem' in params ? `_${pyStr(params.dem)}` : '') + `_s${a.seed}`);
        await Deno.mkdir(a.out, { recursive: true });
        const files = await t.preview(join(a.out, name));
        if (a.save) files.push(await t.save(join(a.out, name)));
        let m;
        try {
            m = await t.metrics();
        } catch (e) {                                    // the judge's numbers are a courtesy here
            m = { error: `${e?.name ?? 'Error'}: ${e?.message ?? e}` };
        }
        const rec = { recipe: t.recipe.name, knobs: t.knobs, seed: a.seed, quality: a.quality, focus,
            cache_key: t.info.cache_key, cache_hit: t.info.cache_hit,
            seconds: { ...t.info.seconds, bake: round2((performance.now() - t0) / 1000) },
            levels: t.levels.map(String), triangles: t.ring.triangleCount, skipped_stages: t.info.skipped_stages,
            warnings: t.info.warnings, metrics: m, files };
        await Deno.writeTextFile(join(a.out, name + '_bake.json'), JSON.stringify(plain(rec), null, 1));
        A.summary(t, console.log);
        console.log(`[bake] ${files.length} files in ${a.out}`);
        return 0;
    } finally {
        t.dispose();
    }
}

if (import.meta.main) {
    let code = 1;
    try {
        code = await main();
    } finally {
        G.shutdown();                                    // the device, so the process ends (main() leaves it to its caller)
    }
    Deno.exit(code);
}
