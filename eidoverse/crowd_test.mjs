// eidoverse/crowd_test.mjs — the crowd tool's clocks and points, against the Blender edition's test (its canon of two
// lines of five, starts 12 + 10 a line + 4 a unit, a hold from 64 for 24 frames, one body stopped alone on 50):
//   deno test -A eidoverse/crowd_test.mjs
import { clockOf, columnGroup, onceGroup, grid, canonStarts, formation } from './crowd.js';

const assert = (x, m = 'Assertion failed') => { if (!x) throw Error(m); };

Deno.test('the canon shows on every frame the pose its start asks for, through the hold and the lone stop', () => {
    const wave = { kind: 'once', poses: 24, every: 2 };
    const G = onceGroup(wave, { hold: [64, 24] });
    const g = grid({ lines: 2, units: 5, linePitch: 2.2, unitPitch: 1.25, origin: [0, 0, -14] });
    const starts = canonStarts(g, { first: 12, stepLine: 10, stepUnit: 4 });
    const pts = g.map((p, i) => ({ ...p, start: starts[i], stop: i === 3 ? 50 : 1e9 }));
    const shown = (f) => pts.map((p) => clockOf(G, p, f).pose).slice(0, 6).join(' ');
    // the Blender edition's numbers (tests/characters_crowd/test_crowd.py)
    assert(shown(30) === '9 7 5 3 1 4', shown(30));
    assert(shown(63) === '23 23 21 13 17 20', shown(63));
    assert(shown(70) === '23 23 22 13 18 21', shown(70));
    assert(shown(87) === '23 23 22 13 18 21', shown(87));
    assert(shown(100) === '23 23 23 13 23 23', shown(100));
    assert(clockOf(G, pts[3], 51).pose === 13 && clockOf(G, pts[3], 110).pose === 13, 'the lone stop holds');
});

Deno.test('a column carries each body S x k / N for the k-th pose, the pose k mod N', () => {
    const cyc = { kind: 'cycle', poses: 50, strideFrames: 25, stride: 1.5, every: 1 };
    const G = columnGroup(cyc, { refFrame: 1 });
    const pt = { dphase: 0 };
    for (let f = 1; f < 200; f++) {
        const { pose, travel } = clockOf(G, pt, f);
        const k = Math.floor(50 * (f - 1) / 25 + 0.5);
        assert(pose === k % 50 && Math.abs(travel - k * 1.5 / 50) < 1e-12, `frame ${f}`);
    }
});

Deno.test('a formation is files abreast and ranks behind, its head rank at the origin', () => {
    const pts = formation({ files: 3, ranks: 2, interval: 0.85, distance: 1.05, origin: [0, 0, 0], heading: 90 });
    assert(pts.length === 6, 'six bodies');
    // heading 90 marches toward +X: the head rank on x = 0, the second 1.05 behind it
    assert(pts.slice(0, 3).every((p) => Math.abs(p.p[0]) < 1e-12) && pts.slice(3).every((p) => Math.abs(p.p[0] + 1.05) < 1e-12), 'ranks');
});
