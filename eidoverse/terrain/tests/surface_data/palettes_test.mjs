// build/palettes.js against build/palettes.py (PORT_PLAN.md 8.2 rows P14 and P18: "palettes.js JSON-equal to
// palettes.py"): every module-level table, and every function's result on palettes.py's data: get() of every palette
// and of 'auto' for every recipe (the looks applied, the ramps and the satmap written out as patches, validated),
// materialMasks and masksUsed, rampRows (the LUT's rows and index), resolveName, forPlace for every place, knownMask
// over the registry's names and a few wrong ones, parse() trees and namesIn, climateSun, columnLayers of every column
// with and without the formation looks, hexLinear. No GPU.
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surface_data/palettes_test.mjs
//
// Reads tests/surface_data/surface_fixtures.py --palettes's palettes.json (palettes.py run by Blender's Python).
// Numbers both sides compute in doubles (colours, ramp ratios) are equal within 1e-12 relative; everything else
// exactly. Writes tests/out/surface_data/palettes_test.json.

import * as P from '../../build/palettes.js';
import * as S from './_surface.mjs';

const T = new S.C.Checks('surface_data: the palettes');
const root = S.fixtureRoot();
const path = root ? `${root}/palettes/palettes.json` : null;
if (!path || !S.W.exists(path)) {
    T.ok('palettes fixture present', false, 'make it: tests/surface_data/surface_fixtures.py --palettes');
    Deno.exit(S.finish(T, 'palettes_test'));
}
const want = JSON.parse(Deno.readTextFileSync(path)).data;

/** The differences between two JSON-like values: paths, numbers within rel (and 1e-15 absolute). */
function diff(a, b, at = '', rel = 1e-12, out = []) {
    if (out.length > 8) return out;
    if (typeof a === 'number' && typeof b === 'number') {
        if (!(a === b || Math.abs(a - b) <= rel * Math.max(Math.abs(a), Math.abs(b)) + 1e-15)) out.push(`${at}: ${a} against ${b}`);
        return out;
    }
    if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
        if (a !== b) out.push(`${at}: ${JSON.stringify(a)?.slice(0, 80)} against ${JSON.stringify(b)?.slice(0, 80)}`);
        return out;
    }
    if (Array.isArray(a) !== Array.isArray(b)) {
        out.push(`${at}: an ${Array.isArray(a) ? 'array' : 'object'} against an ${Array.isArray(b) ? 'array' : 'object'}`);
        return out;
    }
    if (Array.isArray(a)) {
        if (a.length !== b.length) out.push(`${at}: ${a.length} items against ${b.length}`);
        for (let k = 0; k < Math.min(a.length, b.length); k++) diff(a[k], b[k], `${at}[${k}]`, rel, out);
        return out;
    }
    const ka = Object.keys(a), kb = Object.keys(b);
    const extra = ka.filter((k) => !(k in b)), missing = kb.filter((k) => !(k in a));
    if (extra.length || missing.length) out.push(`${at}: keys ${extra.length ? '+' + extra.join(',') : ''} ${missing.length ? '-' + missing.join(',') : ''}`);
    if (ka.join('\0') !== kb.join('\0') && !extra.length && !missing.length) out.push(`${at}: the keys' order differs`);
    for (const k of ka) if (k in b) diff(a[k], b[k], `${at}.${k}`, rel, out);
    return out;
}
const plain = (v) => JSON.parse(JSON.stringify(v, (k, x) => (x instanceof Set ? [...x].sort() : ArrayBuffer.isView(x) ? Array.from(x) : x)));

// ---- the tables
const tables = Object.keys(want).filter((k) => /^[A-Z_][A-Z0-9_]*$/.test(k) && k in P);
const tableBad = [];
for (const k of tables) {
    const d = diff(plain(P[k]), want[k], k, 0);
    if (d.length) tableBad.push(...d.slice(0, 2));
}
const notPorted = Object.keys(want).filter((k) => /^[A-Z_][A-Z0-9_]*$/.test(k) && !(k in P));
T.ok(`the ${tables.length} module-level tables equal palettes.py's exactly`, tableBad.length === 0 && notPorted.length === 0,
    tableBad.slice(0, 3).join('; ') + (notPorted.length ? ` not in the port: ${notPorted.join(', ')}` : ''));
T.ok('names() equals', JSON.stringify(P.names()) === JSON.stringify(want.names));

// ---- get(), the masks it reads, its ramps
const getBad = [];
let ngot = 0;
for (const [key, w] of Object.entries(want.get)) {
    ngot++;
    const [nm, recipe] = key.startsWith('auto:') ? ['auto', key.slice(5)] : [key, null];
    let got;
    try {
        const pal = P.get(nm, recipe);
        const [rows, index] = P.rampRows(pal);
        got = { pal: plain(pal), material_masks: [...P.materialMasks(pal)].sort(), masks_used: [...P.masksUsed(pal)].sort(),
            ramp_rows: { rows: chunk(rows, 256 * 4).map((r) => chunk(r, 4)), index: plain(index) } };
        if (recipe) got.resolve_name = P.resolveName('auto', recipe);
    } catch (e) {
        got = { error: `${e.constructor.name}: ${e.message}` };
    }
    if ('error' in w || 'error' in got) {
        if (!('error' in w) || !('error' in got)) getBad.push(`${key}: ${got.error ?? 'no error'} against ${w.error ?? 'no error'}`);
        continue;
    }
    const d = diff({ ...got, ramp_rows: undefined }, { ...w, ramp_rows: undefined }, key);
    // the LUT rows: float32 in both; the fixture rounded them to 9 decimals
    const rd = diff(got.ramp_rows.rows, w.ramp_rows.rows.map((r) => r.map((t) => t)), `${key}.rows`, 0, []).filter((s) => {
        const m = /: (\S+) against (\S+)$/.exec(s);
        return !m || Math.abs(Number(m[1]) - Number(m[2])) > 2e-9;
    });
    const id = diff(got.ramp_rows.index, w.ramp_rows.index, `${key}.index`);
    getBad.push(...d.slice(0, 2), ...rd.slice(0, 2), ...id.slice(0, 2));
}
T.ok(`get() of every palette and of 'auto' for every recipe (${ngot}), with materialMasks, masksUsed, rampRows and resolveName, equals palettes.py's`,
    getBad.length === 0, getBad.slice(0, 4).join('; '));

function chunk(a, n) {
    const out = [];
    for (let k = 0; k < a.length; k += n) out.push(Array.from(a.slice(k, k + n)));
    return out;
}

// ---- forPlace, knownMask, parse, climateSun, columnLayers, hexLinear
const placeBad = [];
for (const [dem, w] of Object.entries(want.for_place)) {
    let got;
    try {
        const [pal, place] = P.forPlace(dem);
        got = { pal: plain(pal), place: plain(place) };
    } catch (e) {
        got = { error: e.message };
    }
    placeBad.push(...diff(got, w, dem).slice(0, 2));
}
T.ok(`forPlace() of every place (${Object.keys(want.for_place).length}) equals`, placeBad.length === 0, placeBad.slice(0, 3).join('; '));
// (the fixture holds bool(known_mask(name)): true where palettes.py gives a message, the name unknown)
const kmBad = Object.entries(want.known_mask).filter(([nm, w]) => (P.knownMask(nm) !== null) !== w).map(([nm]) => nm);
T.ok(`knownMask() agrees on ${Object.keys(want.known_mask).length} names`, kmBad.length === 0, kmBad.join(', '));
const parseBad = [];
for (const [e, w] of Object.entries(want.parse)) {
    let got;
    try {
        got = { tree: P.parse(e), names: [...P.namesIn(e)].sort() };
    } catch (err) {
        got = { error: err.message };
    }
    if ('error' in w) {
        if (!('error' in got)) parseBad.push(`${e}: no error, palettes.py: ${w.error}`);
    } else {
        parseBad.push(...diff(got, w, e).slice(0, 1));
    }
}
T.ok(`parse() trees and namesIn() of ${Object.keys(want.parse).length} expressions equal (errors where palettes.py errs)`,
    parseBad.length === 0, parseBad.join('; '));
const sunBad = want.climate_sun.filter(([c, w]) => diff(P.climateSun(c), w).length).map(([c]) => JSON.stringify(c));
T.ok('climateSun() equals', sunBad.length === 0, sunBad.join(', '));
const colBad = [];
for (const [key, w] of Object.entries(want.column_layers)) {
    const [nm, looks] = key.split(':');
    colBad.push(...diff({ layers: plain(P.columnLayers(nm, looks === 'True')), repeats: P.columnRepeats(nm) }, w, key).slice(0, 1));
}
T.ok(`columnLayers() of every column with and without the looks (${Object.keys(want.column_layers).length}) equals`, colBad.length === 0,
    colBad.slice(0, 3).join('; '));
const hexBad = Object.entries(want.hex_linear).filter(([h, w]) => diff(P.hexLinear(h), w).length).map(([h]) => h);
T.ok('hexLinear() equals', hexBad.length === 0, hexBad.join(', '));
T.ok('check() finds no problem in any palette (get() validates)', P.names().every((n) => P.check(P.get(n)).length === 0));
Deno.exit(S.finish(T, 'palettes_test'));
