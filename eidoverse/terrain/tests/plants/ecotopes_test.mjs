// build/ecotopes.js against the Blender edition's ecotopes.py (PORT_PLAN.md 3.5, 8.2 row P15: "data: species tables
// per palette, recipe and place, ecotope_hash, JSON-equal"), on tests/plants/plants_fixtures.py --ecotopes:
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/plants/ecotopes_test.mjs
//
// Per ecotope, and per recipe's and place's 'auto' resolution: get() JSON-equal; Python's canonical text of it
// (json.dumps(sort_keys=True), ecotope_hash's input) equal character for character, and the hash; check() clean;
// masksUsed() and every species' sourceDict() equal; describe() equal; resolveName equal. Also: the data block
// equals ecotopes.py at the fixtures' commit (tests/plants/ecotopes_port.py --check, when Blender's Python is here).

import * as S from './_plants.mjs';
import * as E from '../../build/ecotopes.js';
import * as registry from '../../recipes/index.js';

const T = new S.C.Checks('plants: ecotopes.js against ecotopes.py');
const root = S.fixtureRoot('the ecotope fixtures');
if (!root || !S.W.exists(`${root}/ecotopes/ecotopes.json`)) {
    S.W.skip('ecotopes', 'run tests/plants/plants_fixtures.py --ecotopes');
    Deno.exit(0);
}
const fx = JSON.parse(Deno.readTextFileSync(`${root}/ecotopes/ecotopes.json`));
const json = (v) => JSON.parse(JSON.stringify(v));

function compare(label, eco, want) {
    const d = S.jsonDiff(json(eco), want.json);
    let ok = !d;
    const text = E.pyJsonSorted(Object.fromEntries(Object.entries(eco).filter(([k]) => k !== 'title')));
    let at = -1;
    if (text !== want.canonical) for (at = 0; at < text.length && text[at] === want.canonical[at]; at++);
    ok = ok && at < 0;
    const hash = E.ecotopeHash(eco);
    ok = ok && hash === want.hash && eco.name === want.name;
    const problems = E.check(eco);
    ok = ok && S.jsonDiff(problems, want.check) === null;
    const used = [...E.masksUsed(eco)].sort();
    ok = ok && S.jsonDiff(used, want.masks_used) === null;
    const srcs = json(eco.species.map((s) => E.sourceDict(s.source)));
    ok = ok && S.jsonDiff(srcs, want.sources) === null;
    return { ok, detail: d ? `JSON ${d}` : at >= 0 ? `canonical text differs at ${at}: ...${text.slice(Math.max(0, at - 40), at + 40)}... vs ` +
        `...${want.canonical.slice(Math.max(0, at - 40), at + 40)}...` : hash !== want.hash ? `hash ${hash} != ${want.hash}` :
        `${eco.name}#${hash}, ${eco.species.length} species` };
}

let all = 0, good = 0;
const tally = (r) => { all++; if (r.ok) good++; return r; };

for (const n of fx.names) {
    const r = tally(compare(n, E.get(n), fx.by_name[n]));
    const desc = E.describe(n);
    T.ok(`ecotope ${n}: get() JSON-equal, canonical text and hash equal, check clean`, r.ok, r.detail);
    T.ok(`ecotope ${n}: describe() equal`, desc === fx.by_name[n].describe,
        desc === fx.by_name[n].describe ? '' : `got:\n${desc}\nwant:\n${fx.by_name[n].describe}`);
}
T.eq('names()', E.names(), fx.names);

for (const rn of Object.keys(fx.by_recipe)) {
    const R = registry.get(rn);
    const a = tally(compare(rn, E.get('auto', R), fx.by_recipe[rn]));
    const b = tally(compare(rn, E.get('auto', rn), fx.by_recipe_name[rn]));
    T.ok(`recipe ${rn}: the 'auto' ecotope of its Recipe and of its name`, a.ok && b.ok, a.ok ? b.detail : a.detail);
    const [base, over] = E.resolveName('auto', R);
    T.ok(`recipe ${rn}: resolveName`, S.jsonDiff([base, json(over)], fx.resolve[`recipe:${rn}`]) === null,
        `${base} with ${over.length} overrides`);
}

const RP = registry.get('real_place');
for (const [pl, want] of Object.entries(fx.by_place)) {
    const a = tally(compare(pl, E.get('auto', RP, pl, want.palette), want.with_palette));
    const b = tally(compare(pl, E.get('auto', RP, pl), want.without));
    const names = [E.resolveName('auto', RP, pl, want.palette)[0], E.resolveName('auto', RP, pl)[0]];
    T.ok(`place ${pl}: the 'auto' ecotope with its palette and without; resolveName`,
        a.ok && b.ok && S.jsonDiff(names, fx.resolve[`place:${pl}`]) === null, a.ok ? b.detail : a.detail);
}
const dfr = E.describe('auto', 'fluvial_range');
T.ok("describe('auto', recipe='fluvial_range') equal", dfr === fx.describe_auto_fluvial, dfr === fx.describe_auto_fluvial ? '' : dfr);
T.throws('an unknown ecotope names the nearest', () => E.get('alpin'), "nearest: alpine");

// the candidates' Poisson tables (build/plants.js poissonThresholds) against numpy's cdf: the thresholds
// ceil(cdf_k 2^53), made in doubles here and there, differ only by the two libms' last ulps of exp and log (summed
// over the table), so a count by inversion is numpy's except for a 53-bit uniform in the gap between the two:
// graded by the gap's share of the unit interval (under 2^-40: one draw in 10^12)
{
    const PL = await import('../../build/plants.js');
    let tables = 0, entries = 0, differ = 0, gap = 0, bad = [];
    for (const [k, v] of Object.entries(fx.poisson ?? {})) {
        tables++;
        const got = PL.poissonThresholds(v.mean);
        const exp = v.cdf.map((c) => Math.ceil(c * 9007199254740992.0));
        entries += exp.length;
        if (got.length !== exp.length) bad.push(k);
        let g = 0;
        for (let i = 0; i < exp.length; i++) {
            const d = Math.abs(got[i] - exp[i]);
            if (d) differ++;
            g += d;
        }
        gap = Math.max(gap, g / 9007199254740992.0);
    }
    T.ok('the Poisson thresholds against numpy\'s cdf: the counts differ only for a draw in a gap under 2^-40',
        tables > 0 && bad.length === 0 && gap < 2 ** -40,
        `${tables} tables, ${entries} entries, ${differ} differ by a libm's last ulps; the largest table's gap ${S.sci(gap, 2)} ` +
        'of the unit interval' + (bad.length ? `; lengths differ: ${bad.join(', ')}` : ''));
}

// the data block against ecotopes.py at the fixtures' commit (needs Blender's Python and the Blender edition)
const py = S.W.pythonCmd(`${S.W.TESTS}/plants/ecotopes_port.py`, '--check', '--commit', fixtureCommit());
if (py && S.W.blenderEdition()) {
    const code = await S.W.run(py, { log: `${S.W.out('plants')}/ecotopes_port_check.log` });
    T.ok('the data block equals ecotopes.py (ecotopes_port.py --check)', code === 0,
        Deno.readTextFileSync(`${S.W.out('plants')}/ecotopes_port_check.log`).trim());
} else {
    S.W.skip('the data block check', 'set EIDO_BLENDER_EDITION and EIDO_BLENDER_PYTHON (or BLENDER)');
}

function fixtureCommit() {
    return S.fixtureKey()?.commit ?? 'unknown';
}

Deno.exit(S.finish(T, 'ecotopes_test', { resolutions: all, equal: good }));
