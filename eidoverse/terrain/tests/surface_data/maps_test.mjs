// surface/maps.js against surface/maps.py (PORT_PLAN.md 3.5: the registry, JSON-equal): every MapSpec field by field,
// the families, pairs and shader names, describe() line for line, spec() of scaled names and its errors' nearest
// names, decode_rule of every map at four cells and references, and encode / decode of sample values (float32 to the
// bit). No GPU.
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surface_data/maps_test.mjs
//
// Reads tests/surface_data/surface_fixtures.py --maps's maps.json. Writes tests/out/surface_data/maps_test.json.

import * as MP from '../../surface/maps.js';
import * as S from './_surface.mjs';

const T = new S.C.Checks('surface_data: the map registry');
const root = S.fixtureRoot();
const path = root ? `${root}/maps/maps.json` : null;
if (!path || !S.W.exists(path)) {
    T.ok('maps fixture present', false, 'make it: tests/surface_data/surface_fixtures.py --maps');
    Deno.exit(S.finish(T, 'maps_test'));
}
const want = JSON.parse(Deno.readTextFileSync(path)).data;
const js = (v) => JSON.stringify(v);

const order = Object.keys(MP.MAPS);
T.ok(`the registry lists maps.py's ${want.order.length} maps in its order`, js(order) === js(want.order),
    order.length + ' maps');
const bad = order.filter((k) => js(MP.MAPS[k].toDict()) !== js(want.MAPS[k]));
T.ok('every MapSpec equals maps.py\'s field by field', bad.length === 0, bad.length ? `differ: ${bad.join(', ')}` : '');
T.ok('FAMILIES, PAIRS and SHADER equal', js(MP.FAMILIES) === js(want.FAMILIES) && js(MP.PAIRS) === js(want.PAIRS) &&
    js(MP.SHADER) === js(want.SHADER));
T.ok('describe() equals maps.py\'s line for line', MP.describe() === want.describe);
const specBad = Object.entries(want.spec).filter(([k, v]) => js(MP.spec(k).toDict()) !== js(v)).map(([k]) => k);
T.ok('spec() of scaled names equals', specBad.length === 0, specBad.join(', '));
const errBad = [];
for (const [k, msg] of Object.entries(want.spec_errors)) {
    try {
        MP.spec(k);
        errBad.push(`${k}: no error`);
    } catch (e) {
        if (String(e.message).replace(/^["']|["']$/g, '') !== msg) errBad.push(`${k}: '${e.message}' against '${msg}'`);
    }
}
T.ok('spec() errors name the same nearest maps', errBad.length === 0, errBad.join('; '));
const knownBad = Object.entries(want.known).filter(([k, v]) => MP.known(k) !== v).map(([k]) => k);
T.ok('known() agrees', knownBad.length === 0, knownBad.join(', '));
const cells = [32.0, 8.0, 2.0, 0.5], refs = [501.2, 500.0, 499.5, 0.0];
const ruleBad = [];
for (const [k, v] of Object.entries(want.decode_rule)) {
    let got;
    try {
        got = MP.decodeRule(MP.MAPS[k], cells, refs);
    } catch (e) {
        got = { error: e.message };
    }
    if (js(got) !== js(v)) ruleBad.push(`${k}: ${js(got)} against ${js(v)}`);
}
T.ok('decode_rule of every map equals', ruleBad.length === 0, ruleBad.slice(0, 4).join('; '));
let n = 0, encBad = [];
for (const [k, v] of Object.entries(want.encode)) {
    const [nm, cell] = k.split('@');
    const s = MP.MAPS[nm];
    want.values.forEach((x, i) => {
        n++;
        const e = MP.encode1(s, x, Number(cell)), d = MP.decode1(s, v.encoded[i], Number(cell));
        if (e !== v.encoded[i] || d !== v.decoded[i]) encBad.push(`${k} ${x}: ${e}/${d} against ${v.encoded[i]}/${v.decoded[i]}`);
    });
}
T.ok(`encode1 and decode1 equal maps.py's float32 arithmetic to the bit (${n} values)`, encBad.length === 0,
    encBad.slice(0, 4).join('; '));
Deno.exit(S.finish(T, 'maps_test'));
