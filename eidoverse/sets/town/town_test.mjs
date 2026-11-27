// eidoverse/sets/town/town_test.mjs — the town's plan is the Blender edition's, draw for draw:
//   deno test -A eidoverse/sets/town/town_test.mjs
// The numbers on the right are the Blender edition's (eidoblend.sets.town, seed 7, 840 x 300 m, intact) and Python's own
// random module's.
import { PyRandom, pyRound } from './pyrandom.js';
import { plan } from './layout.js';

const assert = (x, m = 'Assertion failed') => { if (!x) throw Error(m); };
const near = (a, b, e, m = '') => assert(Math.abs(a - b) <= e, `${m} ${a} versus ${b}`);

Deno.test('PyRandom draws what Python random draws from the same seed', () => {
    const r = new PyRandom(); r.seed(7);
    [0.32383276483316237, 0.15084917392450192, 0.6509344730398537].forEach((x) => assert(r.random() === x, 'random()'));
    r.seed(7);
    near(r.uniform(-2.5, 4.0), -0.3950870285844448, 1e-15, 'uniform');
    assert(r.randrange(3, 17) === 5, 'randrange');
    assert(r.choice(['a', 'b', 'c', 'd', 'e']) === 'd', 'choice');
    r.seed(12345);
    const x = [...Array(10).keys()];
    r.shuffle(x);
    assert(x.join() === [8, 7, 3, 5, 1, 2, 9, 4, 0, 6].join(), `shuffle ${x}`);
    assert(r.getrandbits(31) === 347221957, 'getrandbits');
});

Deno.test('pyRound rounds half to even, as Python does', () => {
    assert(pyRound(0.125, 2) === 0.12 && pyRound(2.5) === 2 && pyRound(-0.5) === 0 && pyRound(2.675, 2) === 2.67, 'pyRound');
});

Deno.test('the plan places what the Blender edition places', () => {
    const P = plan({ seed: 7, extent: [840, 300], log: () => {} });
    assert(P.placements.length === 3396, `${P.placements.length} placings`);
    assert(P.placements.every((p) => P.designs.has(p.mesh)), 'every placing is of a design');
    let sum = 0;
    for (const p of P.placements) sum += p.loc[0] + p.loc[1] + p.loc[2];
    near(sum, -7329.657, 0.05, 'the sum of every placing\'s coordinates');
    const first = P.placements.find((p) => p.name === 'bld.0000');
    assert(first, 'bld.0000');
    near(first.loc[0], -416.04974, 1e-4, 'bld.0000 x');
    near(first.loc[1], -141.5, 1e-4, 'bld.0000 y');
});
