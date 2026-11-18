// What the wind-and-sand package's tests share (PORT_PLAN.md 8.2 P8): where its outputs go, the result file, and
// the Blender edition's own files read in place (paths from tests/_where.mjs, never one machine's).

import * as W from '../_where.mjs';
import { Checks } from '../core_runner/_common.mjs';

export { Checks, W };

/** tests/out/wind_sand/ (git-ignored), made on first use. */
export const OUT = W.out('wind_sand');

/** Write a test's result to tests/out/wind_sand/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${OUT}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}

/** A Blender terrain file's text (blender/eidoblend/terrain/<rel>), or null when there is no Blender edition. */
export function blenderSource(rel) {
    const root = W.blenderEdition();
    if (!root) return null;
    const p = `${root}/blender/eidoblend/terrain/${rel}`;
    return W.exists(p) ? Deno.readTextFileSync(p) : null;
}

/** The `//!` declaration lines of a kernel text, trimmed (the interface both editions parse). */
export function headerLines(text) {
    return String(text).split(/\r?\n/).map((l) => l.trim()).filter((l) => l.startsWith('//!')).map((l) => l.replace(/\s+/g, ' '));
}

/** solvers/aeolian.py's AVALANCHE_SRC (the avalanche kernel Blender keeps as source text), or null. */
export function avalancheSource() {
    const py = blenderSource('solvers/aeolian.py');
    if (!py) return null;
    const m = /AVALANCHE_SRC = r'''([\s\S]*?)'''/.exec(py);
    return m ? m[1] : null;
}

export const sci = (x, d = 3) => (Number.isFinite(x) ? Number(x).toExponential(d) : String(x));
