// Shared by the runner package's tests (PORT_PLAN.md section 8.2, P1): where things are, the checks, the result file.
//
// Paths are found from this file (import.meta.url) and from the environment, never from a machine:
//     the package             ../../            (eidoverse/terrain/)
//     outputs                 ../out/core_runner/   (git-ignored; made on first use)
//     the Blender edition     $EIDO_BLENDER_EDITION, the root of a checkout of the blender branch (only the Python
//                             fixture makers need it; they also find blender/ beside eidoverse/ in a merged checkout)
// tests/_where.mjs (the parity package's) will own these lookups for the whole port; until it exists this file is
// the runner package's own.

export const TERRAIN = new URL('../../', import.meta.url);
export const OUT = new URL('../out/core_runner/', import.meta.url);
export const PROBES = new URL('../design_probes/', import.meta.url);

export function outUrl(name) {
    Deno.mkdirSync(OUT, { recursive: true });
    return new URL(name, OUT);
}

/** A fixture folder: the first argument, else out/core_runner/<name>/. Returns a URL ending in '/', or null (and
 * says how to make the fixtures) when its manifest is missing. */
/** A folder path (absolute, or relative to the working directory) as a file URL ending in '/'. */
export function dirUrl(path) {
    const abs = (p) => {
        p = p.replace(/\\/g, '/').replace(/\/+$/, '');
        return 'file://' + (p.startsWith('/') ? '' : '/') + encodeURI(p) + '/';
    };
    const p = path.replace(/\\/g, '/');
    return /^([a-zA-Z]:)?\//.test(p) ? new URL(abs(p)) : new URL(encodeURI(p.replace(/\/+$/, '')) + '/', abs(Deno.cwd()));
}

export function fixtureDir(name, arg, how) {
    const url = arg ? dirUrl(arg) : new URL(name + '/', OUT);
    try {
        Deno.statSync(new URL('manifest.json', url));
        return url;
    } catch (_e) {
        console.log(`SKIP: no fixtures at ${arg ?? 'tests/out/core_runner/' + name}. Make them with:\n    ${how}\n` +
            '(the Blender edition is found beside eidoverse/ or at $EIDO_BLENDER_EDITION)');
        return null;
    }
}

export function loadBin(dir, a) {
    const bytes = Deno.readFileSync(new URL(a.file, dir));
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    if (a.dtype === 'u32') return new Uint32Array(buf);
    if (a.dtype === 'i32') return new Int32Array(buf);
    if (a.dtype === 'f64') return new Float64Array(buf);
    if (a.dtype === 'i64') return new BigInt64Array(buf);
    return new Float32Array(buf);
}

/** A test's checks: t.ok(name, condition, detail), t.eq(name, got, want), t.throws(name, fn, part), then
 * t.done(fileName) writes the JSON and sets the exit code. */
export class Checks {
    constructor(title) {
        this.title = title;
        this.rows = [];
        this.extra = {};
        this.t0 = performance.now();
    }

    ok(name, cond, detail = '') {
        this.rows.push({ check: name, passed: !!cond, detail: String(detail) });
        console.log(`${cond ? 'ok  ' : 'FAIL'} ${name}${detail !== '' ? '  ' + detail : ''}`);
        return !!cond;
    }

    eq(name, got, want) {
        const same = JSON.stringify(got) === JSON.stringify(want);
        return this.ok(name, same, same ? '' : `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
    }

    throws(name, fn, part) {
        try {
            fn();
        } catch (e) {
            return this.ok(name, e.message.includes(part), e.message.includes(part) ? '' : `message: ${e.message}`);
        }
        return this.ok(name, false, 'did not throw');
    }

    async rejects(name, fn, part) {
        try {
            await fn();
        } catch (e) {
            return this.ok(name, e.message.includes(part), e.message.includes(part) ? '' : `message: ${e.message.slice(0, 300)}`);
        }
        return this.ok(name, false, 'did not throw');
    }

    done(file) {
        const failed = this.rows.filter((r) => !r.passed);
        const res = { test: this.title, deno: Deno.version.deno, date: new Date().toISOString(), seconds: +((performance.now() - this.t0) / 1000).toFixed(2),
            checks: this.rows.length, failed: failed.map((r) => r.check), ...this.extra, rows: this.rows };
        if (file) Deno.writeTextFileSync(outUrl(file), JSON.stringify(res, null, 1));
        console.log(`RESULT ${this.title}: ${this.rows.length - failed.length} of ${this.rows.length} checks passed` +
            (failed.length ? `; FAILED: ${failed.map((r) => r.check).join(' | ')}` : ''));
        return failed.length ? 1 : 0;
    }
}

export const bitsEqual = (a, b) => {
    if (a.length !== b.length) return false;
    const x = new Uint32Array(a.buffer, a.byteOffset, a.byteLength / 4), y = new Uint32Array(b.buffer, b.byteOffset, b.byteLength / 4);
    for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return false;
    return true;
};

/** A reproducible pseudo-random source for test data (a 32-bit LCG; tests only). */
export function lcg(seed) {
    let s = seed >>> 0;
    return () => {
        s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
        return s / 4294967296;
    };
}
