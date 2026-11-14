// Where things are, for the terrain port's tests and tools (PORT_PLAN.md 6.2), so that no file in the repository
// carries one machine's paths: the counterpart of the Blender branch's blender/tests/_where.py.
//
//     import * as W from '../_where.mjs';                 // from eidoverse/terrain/tests/<package>/
//     W.REPO, W.TERRAIN, W.TESTS                          // this checkout's root, eidoverse/terrain/, its tests/
//     W.out('masks')                                      // tests/out/masks/ (git-ignored; made on first use)
//     W.parityOut()                                       // the parity fixtures and dumps (5.1): $EIDO_PARITY_OUT,
//                                                         // else tests/out/parity/
//     W.fixtures('kernels')                               // a fixture folder of tests/parity/fixtures.py, or null
//     W.floorRun('dunes', 1, 'base')                      // a finished run of the floor (5.4), or null
//     W.blenderEdition()                                  // the Blender edition's root, or null (see below)
//     W.blenderPython()                                   // Blender's bundled Python (C6), or null
//     W.blenderCmd(script, ...args)                       // argv: headless Blender through run_blender.sh, after
//                                                         // $EIDO_GPU_WRAP's words when that is set
//     W.denoCmd(script, ...args)                          // argv: a Deno WebGPU job, after $EIDO_GPU_WRAP's words
//     W.pythonCmd(script, ...args)                        // argv: Blender's Python -I (numpy only: not a GPU job)
//     W.dem('lauterbrunnen')                              // { json, png, water, context } of a reference DEM
//     W.external('EIDO_X_DIR', 'what it is')              // an outside input, or null after saying what to set
//     await W.run(argv, { cwd, env, log })                // run a command (no console window), its exit code
//
// The rules, as the Blender branch's _where.py and PORT_PLAN.md 6.2 have them:
//   - The Blender edition: blender/ in this checkout when it is a checkout of the blender branch (that branch merges
//     main, so after the merge one checkout holds both editions), else $EIDO_BLENDER_EDITION, the root of a checkout
//     of the blender branch (a worktree, say). Read-only: nothing here writes into it.
//   - Blender's Python (every fixture and the judge, plan 5.1 and C6: Python 3.13, numpy 2.3.4, zlib 1.3.1):
//     $EIDO_BLENDER_PYTHON, else the Python bundled beside the Blender executable that run_blender.sh finds ($BLENDER,
//     then `blender` on the path, then the usual install folders, newest first) as <version>/python/bin/python(.exe);
//     run with -I. Never the system Python: its numpy and zlib are others (plan risk 13).
//   - DEMs for real_place and the metrics: the folders of $EIDO_TERRAIN_DEMS (the Blender edition's variable,
//     separated by the platform's path separator), then the Blender edition's blender/tests/terrain/reference/data.
//     A name in neither raises, naming both and the fetch command.
//   - GPU jobs: $EIDO_GPU_WRAP (a command prefix, split as Python's shlex.split splits it) goes in front of every
//     Deno or Blender job a test starts, as blender/tests/_where.blender_cmd puts it; unset, the job runs directly.
//   - The checkout with the untracked shared folders (node_modules/, eidoverse/assets/cache/): $EIDO_MAIN_CHECKOUT,
//     else the repository's main worktree when this checkout is a linked worktree, else this checkout.
//   - A missing input makes a test skip the checks that need it, printing the variable to set and how to make the
//     input, as _where.external() does. Nothing has a default path of one machine.

const IS_WIN = Deno.build.os === 'windows';

/** A file URL as a path with '/' separators (C:/x/y on Windows), no trailing separator. */
export function urlPath(url) {
    const p = decodeURIComponent(new URL(url).pathname).replace(/^\/([A-Za-z]:)/, '$1');
    return p.length > 1 ? p.replace(/\/+$/, '') : p;
}

/** A path with '/' separators and without a trailing one; '.' and '..' segments resolved. */
export function norm(p) {
    p = String(p).replace(/\\/g, '/');
    const drive = /^[A-Za-z]:/.test(p) ? p.slice(0, 2) : '';
    const abs = p.slice(drive.length).startsWith('/');
    const out = [];
    for (const s of p.slice(drive.length).split('/')) {
        if (s === '' || s === '.') continue;
        if (s === '..' && out.length && out[out.length - 1] !== '..') out.pop();
        else if (s !== '..' || !abs) out.push(s);
    }
    return drive + (abs ? '/' : '') + out.join('/');
}

const isAbs = (p) => /^([A-Za-z]:)?[\\/]/.test(p);

/** A path made absolute against the working directory (or `base`). */
export function absPath(p, base = Deno.cwd()) {
    return norm(isAbs(p) ? p : `${base}/${p}`);
}

export const TESTS = urlPath(new URL('./', import.meta.url));
export const TERRAIN = urlPath(new URL('../', import.meta.url));
export const REPO = urlPath(new URL('../../../', import.meta.url));

export function exists(p) {
    try {
        Deno.statSync(p);
        return true;
    } catch (_e) {
        return false;
    }
}

export function isDir(p) {
    try {
        return Deno.statSync(p).isDirectory;
    } catch (_e) {
        return false;
    }
}

const env = (name) => {
    const v = Deno.env.get(name);
    return v === undefined || v === '' ? null : v;
};

// ----------------------------------------------------------------------------------------------- outputs ---

/** tests/out/<name>/ (git-ignored), made on first use. */
export function out(name) {
    const p = `${TESTS}/out/${name}`;
    Deno.mkdirSync(p, { recursive: true });
    return p;
}

/** Where the parity fixtures, dumps, logs and snapshots go (plan 5.1): $EIDO_PARITY_OUT, else tests/out/parity/.
 * Made on first use. */
export function parityOut() {
    const e = env('EIDO_PARITY_OUT');
    if (e) {
        const p = norm(e);
        Deno.mkdirSync(p, { recursive: true });
        return p;
    }
    return out('parity');
}

/** The folders of parityOut() that hold the Blender edition's fixtures and runs, one per Blender commit and code hash
 * (blender_<commit>_<hash>, plan 5.1), newest first by their manifest's time. */
export function parityKeys() {
    const root = parityOut(), found = [];
    for (const e of Deno.readDirSync(root)) {
        if (!e.isDirectory || !e.name.startsWith('blender_')) continue;
        let t = 0;
        try {
            t = Deno.statSync(`${root}/${e.name}/manifest.json`).mtime?.getTime() ?? 0;
        } catch (_e) { /* a folder without a manifest sorts last */ }
        found.push({ name: e.name, dir: `${root}/${e.name}`, t });
    }
    return found.sort((a, b) => b.t - a.t);
}

/** The folder of the parity outputs for one Blender code state: $EIDO_PARITY_KEY (a folder name of parityOut()),
 * else the newest. null when there is none. */
export function parityKeyDir() {
    const keys = parityKeys(), want = env('EIDO_PARITY_KEY');
    const k = want ? keys.find((x) => x.name === want) : keys[0];
    return k ? k.dir : null;
}

/** A fixture folder made by tests/parity/fixtures.py ('kernels', 'functions/hydro', 'plans', 'twin_probe',
 * 'np_random', 'core_inputs'), or null after saying how to make it. */
export function fixtures(kind) {
    const key = parityKeyDir();
    const dir = key ? `${key}/fixtures/${kind}` : null;
    if (dir && exists(`${dir}/manifest.json`)) return dir;
    const flag = { kernels: '--kernels', twin_probe: '--kernels', plans: '--plans', np_random: '--plans',
        core_inputs: '--recipes' }[kind] ?? `--functions --only ${kind.split('/').pop()}`;
    console.log(`[skip] no ${kind} fixtures${key ? ` in ${key}` : ''}: make them with <Blender's python> -I ` +
        `eidoverse/terrain/tests/parity/fixtures.py ${flag}`);
    return null;
}

/** A run of the floor (plan 5.4): <key>/<recipe>_s<seed>_<quality>/<base | p1..p5>, or null when it is not done. */
export function floorRun(recipe, seed = 1, which = 'base', quality = 'draft') {
    const key = parityKeyDir();
    const dir = key ? `${key}/${recipe}_s${seed}_${quality}/${which}` : null;
    return dir && exists(`${dir}/done.json`) ? dir : null;
}

// -------------------------------------------------------------------------------------- the main checkout ---

/** The checkout holding the untracked shared folders: $EIDO_MAIN_CHECKOUT, else the main worktree of this
 * repository when REPO is a linked worktree (its .git is a file "gitdir: <main>/.git/worktrees/<name>"), else REPO. */
export function mainCheckout() {
    const e = env('EIDO_MAIN_CHECKOUT');
    if (e) return norm(e);
    try {
        if (Deno.statSync(`${REPO}/.git`).isFile) {
            const line = Deno.readTextFileSync(`${REPO}/.git`).trim();
            if (line.startsWith('gitdir:')) {
                // git 2.48+ can write the gitdir relative to the worktree: join it to REPO, never to the cwd
                const gitdir = absPath(line.slice('gitdir:'.length).trim(), REPO);
                return norm(`${gitdir}/../../..`);
            }
        }
    } catch (_e) { /* not a worktree */ }
    return REPO;
}

// ------------------------------------------------------------------------------------ the Blender edition ---

/** The Blender edition's root (a checkout of the blender branch): REPO itself when it holds
 * blender/eidoblend/terrain, else $EIDO_BLENDER_EDITION when that does; null otherwise. */
export function blenderEdition() {
    if (isDir(`${REPO}/blender/eidoblend/terrain/core`)) return REPO;
    const e = env('EIDO_BLENDER_EDITION');
    if (e && isDir(`${norm(e)}/blender/eidoblend/terrain/core`)) return norm(e);
    return null;
}

/** The Blender edition's root, or null after printing how to point at one (the caller skips what needs it). */
export function needBlenderEdition(what = 'the Blender edition') {
    const root = blenderEdition();
    if (!root) {
        const e = env('EIDO_BLENDER_EDITION');
        console.log(`[skip] ${what}: set EIDO_BLENDER_EDITION to the root of a checkout of the blender branch` +
            (e ? ` (${e} holds no blender/eidoblend/terrain)` : ''));
    }
    return root;
}

/** blender/eidoblend/terrain and blender/tests/terrain of the Blender edition (null without one). */
export const blenderTerrain = () => (blenderEdition() ? `${blenderEdition()}/blender/eidoblend/terrain` : null);
export const blenderTests = () => (blenderEdition() ? `${blenderEdition()}/blender/tests/terrain` : null);

// version sort, as `sort -V` orders paths: digit runs compare as numbers
function versionCompare(a, b) {
    const ta = a.match(/\d+|\D+/g) ?? [], tb = b.match(/\d+|\D+/g) ?? [];
    for (let i = 0; i < Math.min(ta.length, tb.length); i++) {
        const x = ta[i], y = tb[i];
        if (x === y) continue;
        const dx = /^\d/.test(x), dy = /^\d/.test(y);
        if (dx && dy) return Number(x) - Number(y) || x.length - y.length;
        return x < y ? -1 : 1;
    }
    return ta.length - tb.length;
}

function globDirs(parent, test) {
    const outp = [];
    try {
        for (const e of Deno.readDirSync(parent)) if (test(e)) outp.push(`${norm(parent)}/${e.name}`);
    } catch (_e) { /* no such folder */ }
    return outp;
}

/** An executable on the path, or null. */
export function which(name) {
    const sep = IS_WIN ? ';' : ':';
    const exts = IS_WIN ? ['.exe', '.cmd', '.bat', ''] : [''];
    for (const d of (env('PATH') ?? '').split(sep)) {
        if (!d) continue;
        for (const x of exts) {
            const p = `${norm(d)}/${name}${x}`;
            try {
                if (Deno.statSync(p).isFile) return p;
            } catch (_e) { /* not here */ }
        }
    }
    return null;
}

/** The Blender executable run_blender.sh would run: $BLENDER, then `blender` on the path, then the usual install
 * folders (newest first, as its `sort -rV`), or null. */
export function blenderExecutable() {
    const b = env('BLENDER');
    if (b && exists(b)) return norm(b);
    const onPath = which('blender');
    if (onPath) return onPath;
    const home = env('HOME') ?? env('USERPROFILE');
    const cands = [];
    if (home) {
        for (const d of globDirs(`${norm(home)}/Blender`, (e) => e.isDirectory)) {
            if (exists(`${d}/blender.exe`)) cands.push(`${d}/blender.exe`);
        }
    }
    const pf = env('ProgramFiles') ?? (IS_WIN ? 'C:/Program Files' : null);
    if (pf) {
        for (const d of globDirs(`${norm(pf)}/Blender Foundation`, (e) => e.isDirectory)) {
            if (exists(`${d}/blender.exe`)) cands.push(`${d}/blender.exe`);
        }
    }
    for (const p of ['/Applications/Blender.app/Contents/MacOS/Blender', '/usr/bin/blender', '/snap/bin/blender']) {
        if (exists(p)) cands.push(p);
    }
    cands.sort((x, y) => versionCompare(y, x));
    return cands[0] ?? null;
}

/** Blender's bundled Python (plan 5.1, C6): $EIDO_BLENDER_PYTHON, else <version>/python/bin/python(.exe) beside the
 * Blender executable (on macOS under Contents/Resources), the newest version folder first; null when there is none
 * (a Blender built against the system's Python has no bundled one: set EIDO_BLENDER_PYTHON). */
export function blenderPython() {
    const e = env('EIDO_BLENDER_PYTHON');
    if (e && exists(e)) return norm(e);
    const exe = blenderExecutable();
    if (!exe) return null;
    const dir = norm(`${exe}/..`);
    for (const base of [dir, norm(`${dir}/../Resources`)]) {
        const versions = globDirs(base, (x) => x.isDirectory && /^\d+\.\d+$/.test(x.name))
            .sort((x, y) => versionCompare(y, x));
        for (const v of versions) {
            const bin = `${v}/python/bin`;
            const names = globDirs(bin, (x) => x.isFile && /^python(3(\.\d+)?)?(\.exe)?$/.test(x.name))
                .sort((x, y) => versionCompare(y, x));
            const exeName = names.find((p) => p.endsWith('/python.exe')) ?? names.find((p) => /python3\.\d+$/.test(p)) ??
                names[0];
            if (exeName) return exeName;
        }
    }
    return null;
}

/** Blender's Python, or null after printing how to name it. */
export function needBlenderPython(what = 'a fixture') {
    const p = blenderPython();
    if (!p) {
        console.log(`[skip] ${what}: needs Blender's own Python (numpy 2.3.4, zlib 1.3.1): set EIDO_BLENDER_PYTHON, ` +
            'or BLENDER to a Blender 5.2 whose folder holds <version>/python/bin');
    }
    return p;
}

/** The run_blender.sh that starts headless Blender: the Blender edition's own, else this checkout's. */
export function runBlenderSh() {
    const root = blenderEdition();
    if (root && exists(`${root}/run_blender.sh`)) return `${root}/run_blender.sh`;
    return `${REPO}/run_blender.sh`;
}

// ------------------------------------------------------------------------------------------------ GPU jobs ---

/** $EIDO_GPU_WRAP's words (Python shlex.split's POSIX rules: quotes, backslash escapes), or []. */
export function gpuWrap() {
    const s = env('EIDO_GPU_WRAP');
    if (!s) return [];
    const words = [];
    let cur = '', inWord = false, q = null;
    for (let i = 0; i < s.length; i++) {
        const c = s[i];
        if (q === "'") {
            if (c === "'") q = null;
            else cur += c;
        } else if (q === '"') {
            if (c === '"') q = null;
            else if (c === '\\' && i + 1 < s.length && '"\\$`\n'.includes(s[i + 1])) cur += s[++i];
            else cur += c;
        } else if (c === "'" || c === '"') {
            q = c;
            inWord = true;
        } else if (c === '\\' && i + 1 < s.length) {
            cur += s[++i];
            inWord = true;
        } else if (/\s/.test(c)) {
            if (inWord) words.push(cur);
            cur = '';
            inWord = false;
        } else {
            cur += c;
            inWord = true;
        }
    }
    if (q) throw new Error(`EIDO_GPU_WRAP: an unclosed ${q} quote`);
    if (inWord) words.push(cur);
    return words;
}

/** The argv that runs `script` in headless Blender through run_blender.sh (its args after Blender's `--`), with
 * $EIDO_GPU_WRAP's words in front when it is set (blender/tests/_where.blender_cmd). */
export function blenderCmd(script, ...args) {
    return [...gpuWrap(), 'bash', runBlenderSh(), String(script), ...args.map(String)];
}

/** The argv of a Deno WebGPU job (this Deno, this checkout's deno.json and lock), after $EIDO_GPU_WRAP's words. */
export function denoCmd(script, ...args) {
    return [...gpuWrap(), norm(Deno.execPath()), 'run', '--config', `${REPO}/deno.json`, '--frozen', '--unstable-webgpu',
        '--allow-all', String(script), ...args.map(String)];
}

/** The argv of a numpy-only job in Blender's Python (-I: isolated, no user site, no environment), or null. */
export function pythonCmd(script, ...args) {
    const py = blenderPython();
    return py ? [py, '-I', String(script), ...args.map(String)] : null;
}

/** Run argv (no console window: the child shares this process's console), its stdout and stderr to `log` (a path)
 * or to this process's; resolves to the exit code. */
export async function run(argv, opts = {}) {
    const [cmd, ...args] = argv;
    const toFile = opts.log ? await Deno.open(opts.log, { write: true, create: true, truncate: true }) : null;
    const child = new Deno.Command(cmd, {
        args, cwd: opts.cwd, env: opts.env, stdin: 'null',
        stdout: toFile ? 'piped' : 'inherit', stderr: toFile ? 'piped' : 'inherit',
    }).spawn();
    if (toFile) {
        const w = toFile.writable.getWriter();
        const pump = async (stream) => {
            for await (const chunk of stream) await w.write(chunk);
        };
        await Promise.all([pump(child.stdout), pump(child.stderr)]);
        await w.close();
    }
    const st = await child.status;
    return st.code;
}

// ------------------------------------------------------------------------------------------------- the DEMs ---

/** The folders a reference DEM is looked for in: $EIDO_TERRAIN_DEMS's, then the Blender edition's reference/data
 * (recipes/real_place.py dem_dirs, the same order). */
export function demDirs() {
    const e = env('EIDO_TERRAIN_DEMS');
    const dirs = e ? e.split(IS_WIN ? ';' : ':').filter(Boolean).map(norm) : [];
    const t = blenderTests();
    if (t && isDir(`${t}/reference/data`)) dirs.push(`${t}/reference/data`);
    return dirs.filter(isDir);
}

/** A reference DEM by name: { name, dir, json, png, water (or null), contextJson, contextPng (or null) }. Raises
 * naming both places and the fetch command when it is in neither. */
export function dem(name) {
    for (const d of demDirs()) {
        const json = `${d}/${name}.json`, png = `${d}/${name}.png`;
        if (exists(json) && exists(png)) {
            const w = `${d}/${name}_water.png`, cj = `${d}/${name}_context.json`, cp = `${d}/${name}_context.png`;
            return { name, dir: d, json, png, water: exists(w) ? w : null, contextJson: exists(cj) ? cj : null,
                contextPng: exists(cp) ? cp : null };
        }
    }
    const t = blenderTests();
    throw new Error(`no DEM '${name}' in $EIDO_TERRAIN_DEMS (${env('EIDO_TERRAIN_DEMS') ?? 'unset'}) or the Blender ` +
        `edition's reference/data (${t ? `${t}/reference/data` : 'no Blender edition: set EIDO_BLENDER_EDITION'}); ` +
        'fetch the references with <Blender\'s python> -I blender/tests/terrain/reference/fetch_references.py ' +
        '--downloads <an empty folder>');
}

/** The reference DEMs on this machine (recipes/real_place.py dem_names). */
export function demNames() {
    const names = new Set();
    for (const d of demDirs()) {
        for (const e of Deno.readDirSync(d)) {
            if (e.isFile && e.name.endsWith('.json') && !e.name.endsWith('_context.json')) names.add(e.name.slice(0, -5));
        }
    }
    return [...names].sort();
}

// ---------------------------------------------------------------------------------------- outside inputs ---

/** An input that lives outside this repo, named by the environment variable `name`: its path when it exists, else
 * null after printing which variable to set (and `how` to make it), so the caller skips the checks that need it. */
export function external(name, what, how = '') {
    const p = env(name);
    if (p && exists(p)) return norm(p);
    console.log(`[skip] ${what}: set ${name} to it` + (p ? ` (${p} does not exist)` : '') + (how ? `; ${how}` : ''));
    return null;
}

/** A skip line, as the tests print one: what is skipped and how to provide it. */
export function skip(what, how) {
    console.log(`[skip] ${what}: ${how}`);
}
