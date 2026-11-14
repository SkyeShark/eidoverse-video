// Which port files are behind the Blender edition (PORT_PLAN.md 5.6). Every port file starts with
// `// Port of blender/eidoblend/terrain/<file> at <commit>.`; this lists, per port file, the Blender files it names
// that changed since that commit (committed changes, and uncommitted ones in the Blender checkout's working tree),
// the port files with no such header, and the Blender terrain files no port file names yet.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/parity/sync_status.mjs [--json] [--all]
//
// Reads the Blender edition's git history (`git -C <edition> log`, read-only); the edition is found by
// tests/_where.mjs ($EIDO_BLENDER_EDITION, or blender/ in this checkout). Writes tests/out/parity/sync_status.json
// and prints the table; --all also lists the port files that are up to date. Exit code 0 when nothing is behind,
// 1 when a port file is, 2 without a Blender edition.

import * as W from '../_where.mjs';

const edition = W.needBlenderEdition('sync_status');
if (!edition) Deno.exit(2);
const ALL = Deno.args.includes('--all');

async function git(...args) {
    const r = await new Deno.Command('git', { args: ['-C', edition, ...args], stdout: 'piped', stderr: 'piped' }).output();
    return r.code === 0 ? new TextDecoder().decode(r.stdout).trim() : null;
}

// the port's source files: everything under eidoverse/terrain/ but the tests' outputs and the plan's probes
function* walk(dir, rel = '') {
    for (const e of Deno.readDirSync(dir)) {
        const p = `${dir}/${e.name}`, r = rel ? `${rel}/${e.name}` : e.name;
        if (e.isDirectory) {
            if (r === 'tests/out' || r === 'tests/design_probes' || e.name === 'node_modules' || e.name === '__pycache__') continue;
            yield* walk(p, r);
        } else if (/\.(js|mjs|wgsl)$/.test(e.name)) {
            yield r;
        }
    }
}

// "Port of <paths> at <commit>": the Blender paths a header names (a folder counts for everything under it)
function header(text) {
    const lines = text.split('\n').slice(0, 60).join('\n');
    const m = /Port of ([\s\S]{0,400}?)\bat ([0-9a-f]{7,40})\b/.exec(lines);
    if (!m) return null;
    const paths = [...m[1].matchAll(/blender\/[A-Za-z0-9_./-]*[A-Za-z0-9_]/g)].map((x) => x[0]);
    return paths.length ? { paths: [...new Set(paths)], commit: m[2] } : null;
}

const head = await git('rev-parse', '--short', 'HEAD');
const branch = await git('rev-parse', '--abbrev-ref', 'HEAD');
const rows = [], noHeader = [], named = new Set();
const cache = new Map();
async function changed(path, commit) {
    const key = `${commit} ${path}`;
    if (!cache.has(key)) {
        const log = await git('log', '--format=%h %ad %s', '--date=short', `${commit}..HEAD`, '--', path);
        const dirty = await git('status', '--porcelain', '--', path);
        cache.set(key, { commits: log === null ? null : log.split('\n').filter(Boolean),
            dirty: (dirty ?? '').split('\n').filter(Boolean).map((l) => l.trim()) });
    }
    return cache.get(key);
}

for (const rel of [...walk(W.TERRAIN)].sort()) {
    const h = header(Deno.readTextFileSync(`${W.TERRAIN}/${rel}`));
    if (!h) {
        if (!rel.startsWith('tests/')) noHeader.push(rel);
        continue;
    }
    const row = { port: `eidoverse/terrain/${rel}`, commit: h.commit, blender: [] };
    for (const p of h.paths) {
        named.add(p);
        const c = await changed(p, h.commit);
        row.blender.push({ path: p, exists: W.exists(`${edition}/${p}`), commits: c.commits, uncommitted: c.dirty });
    }
    row.behind = row.blender.some((b) => b.commits === null || b.commits.length || b.uncommitted.length || !b.exists);
    rows.push(row);
}

// the Blender terrain files no port file names
const tracked = ((await git('ls-files', 'blender/eidoblend/terrain')) ?? '').split('\n').filter((f) => /\.(py|glsl)$/.test(f));
const unported = tracked.filter((f) => !named.has(f));     // a folder a header names (core/prims.js: the whole
                                                           // package) does not count as porting its files

const behind = rows.filter((r) => r.behind);
const out = { date: new Date().toISOString(), blender_edition: { head, branch }, port_files: rows.length, behind: behind.length,
    rows, port_files_without_a_header: noHeader, blender_files_no_port_file_names: unported };
Deno.writeTextFileSync(`${W.out('parity')}/sync_status.json`, JSON.stringify(out, null, 1));
if (Deno.args.includes('--json')) {
    console.log(JSON.stringify(out, null, 1));
} else {
    console.log(`Blender edition at ${head} (${branch}); ${rows.length} port files name a Blender file and commit.`);
    for (const r of rows) {
        if (!r.behind && !ALL) continue;
        console.log(`${r.behind ? 'BEHIND' : 'ok    '} ${r.port} (at ${r.commit})`);
        for (const b of r.blender) {
            if (!b.exists) console.log(`         ${b.path}: no longer in the Blender edition`);
            if (b.commits === null) console.log(`         ${b.path}: commit ${r.commit} is not in the Blender edition's history`);
            const what = /\.(py|glsl)$/.test(b.path) ? b.path : `${b.path}/ (a folder: any file under it)`;
            for (const c of b.commits ?? []) console.log(`         ${what}: ${c}`);
            for (const d of b.uncommitted) console.log(`         ${b.path}: uncommitted in the working tree: ${d}`);
        }
    }
    console.log(`${behind.length} port file(s) behind the Blender edition.`);
    if (noHeader.length) console.log(`No "Port of ... at <commit>" header (${noHeader.length}): ${noHeader.join(', ')}`);
    console.log(`Blender terrain files no port file names yet: ${unported.length}` + (ALL ? `: ${unported.join(', ')}` : ' (--all lists them)'));
}
Deno.exit(behind.length ? 1 : 0);
