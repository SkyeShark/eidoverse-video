// parity_dump.mjs: the DAISY sets' pure functions, evaluated from their own WebGPU source text (eidoverse/sets/funeral.js,
// eidoverse/sets/corner.js), dumped as JSON for test_parity.py: the crowd, the candles, the motes, the festoon bulbs,
// the shots, the power curve, the phones; the march, the chant, the spark (its path, timing, births), the string-light
// bulbs and the corner's cameras. Blocks are cut out of the source by their own first and last lines, so a change in
// the JS changes what is compared.
//
//   deno run --no-config --no-lock -A parity_dump.mjs <eidoverse dir> <three.module.js> <bulb x,y,z (three room-local)>
const [EIDO, THREE_PATH, BULB] = Deno.args;
const T = await import('file:///' + THREE_PATH.replace(/\\/g, '/'));
const read = (p) => Deno.readTextFileSync(EIDO + '/' + p);
const cut = (src, a, b, incl = false) => {
    const i = src.indexOf(a);
    if (i < 0) throw new Error('marker not found: ' + a);
    const j = src.indexOf(b, i + a.length);
    if (j < 0) throw new Error('end marker not found: ' + b);
    return src.slice(i, incl ? j + b.length : j);
};
const out = {};

// ------------------------------------------------------------------------------------------------ the funeral
{
    const src = read('sets/funeral.js');
    const top = cut(src, 'const BAR = 1.875;', 'export async function build(ctx)')
        .split('\n').filter((l) => !/import\.meta|fsPath/.test(l)).join('\n').replace(/export const/g, 'const');
    const layout = JSON.parse(read('assets/sets/funeral/funeral_layout.json'));
    const anchors = JSON.parse(read('assets/sets/funeral/props_layout.json'));
    const body = [
        top,
        'const layout = LAYOUT, anchors = ANCHORS, LAMPS = layout.lamps, variants = { length: 4 };',
        cut(src, 'const lampRelight = ', '{\n        const pos = new Float32Array(nL * 3)'),
        cut(src, 'const candles = [];', '// ═════════════════════════════════ PROPS'),
        cut(src, 'const people = [];', 'const crowdMeshes = [];'),
        'const motes = [];',
        '{' + cut(src, 'const n = 520;', 'const g = new T.PlaneGeometry(1, 1);\n        g.setAttribute(\'iP\'')
            .replace('const P0 = new Float32Array(n * 4), V0 = new Float32Array(n * 4);', 'const P0 = new Float32Array(n * 4), V0 = new Float32Array(n * 4); motes.push(P0, V0);') + '}',
        'const strands = [-6.75, -2.25, 2.25, 6.75]; const festoon = [];',
        cut(src, 'for (const x of strands) {', '{\n        const wireMat = M.cord;'),
        'const bp = []; for (const pts of festoon) { const curve = new T.CatmullRomCurve3(pts.map((p) => new T.Vector3(...p)));' +
            ' const L = curve.getLength(); for (let d = 0.2; d < L; d += 0.48) { const p = curve.getPointAt(d / L); bp.push([p.x, p.y - 0.055, p.z]); } }',
        'const V3 = (a) => new T.Vector3(...a);',
        cut(src, 'const B = (p) => [p[0] + BRIDGE_AT[0]', 'function markAt(u)'),
        cut(src, 'const power = (u) => {', 'const tmpC = new T.Color();'),
        'return { BEATS, lampRelight, candles, people, motes, bp, shotAt, power, phoneFrac, SHOTS };',
    ].join('\n');
    const F = new Function('T', 'LAYOUT', 'ANCHORS', body)(T, layout, anchors);
    const us = [];
    for (let u = 0; u < 33.75; u += 0.37) us.push(u);
    out.funeral = {
        beats: F.BEATS, lampRelight: F.lampRelight, candles: F.candles,
        people: F.people.map((p) => [p.x, p.y, p.z, p.variant, p.yaw, p.scale, p.tOn, p.hold, p.tUp, p.up, p.seed, p.bowK, p.mezz ? 1 : 0]),
        motesP: Array.from(F.motes[0]), motesV: Array.from(F.motes[1]), festoon: F.bp,
        us, shots: us.map((u) => { const s = F.shotAt(u); return [s.pos.x, s.pos.y, s.pos.z, s.target.x, s.target.y, s.target.z, s.fov]; }),
        power: us.map((u) => F.power(u)), phone: us.map((u) => F.phoneFrac(u)),
    };
}

// ------------------------------------------------------------------------------------------------- the corner
{
    const src = read('sets/corner.js');
    const top = cut(src, 'const BAR = 1.875, BEAT = BAR / 4;', 'export async function build(ctx)')
        .split('\n').filter((l) => !/import\.meta|fsPath/.test(l)).join('\n').replace(/export const/g, 'const');
    const [bx, by, bz] = BULB.split(',').map(Number);
    const body = [
        top,
        'let seed = 1; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);',
        'const march = {}; const room = { bulbPos: new T.Vector3(BX, BY, BZ) }; const spark = {};',
        cut(src, 'seed = 909;', 'march.rows = rows;', true),
        'const camp = { poles: [] }; const G = null; const place = async () => null;',
        cut(src, 'const POLES = [', 'const SPANS = ['),
        cut(src, 'const SPANS = [', '// wires: black rubber'),
        cut(src, 'const fwd = new T.Vector3(Math.sin(MARK_LAMP.yaw)', 'spark.dest = dest;', true),
        'spark.t0 = B(26) + 1.17; spark.t1 = B(28) - 0.2; spark.N = 56; spark.trailAttr = { array: new Float32Array(56 * 4) };',
        cut(src, 'const sparkProgress = (u) => {', 'setSparkTiming(spark.t0, spark.t1);', true),
        cut(src, 'const areaAt = (u) =>', 'function markAt(u)'),
        cut(src, '// cameras: one shot per bar', '// ---- per-frame'),
        'return { rows: march.rows, bulbPts, poleYaw, spark, sparkProgress, camera, CHANT_ACCENTS, areaAt, moodAt };',
    ].join('\n');
    const fn = new Function('T', 'BX', 'BY', 'BZ', 'return (async () => {' + body + '})();');
    const C = await fn(T, bx, by, bz);
    const us = [];
    for (let u = 33.75; u < 56.25; u += 0.29) us.push(u);
    out.corner = {
        rows: C.rows.map((r) => [r.x, r.z, r.sx, r.sz, r.tStart, r.tArr, r.yaw, r.scale, r.phase, r.delay, r.amp, r.sign, r.variant, r.hasSign ? 1 : 0]),
        bulbPts: C.bulbPts.map((p) => [p.x, p.y, p.z]), poleYaw: C.poleYaw, chant: C.CHANT_ACCENTS,
        dest: [C.spark.dest.x, C.spark.dest.y, C.spark.dest.z],
        curve: [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1].map((s) => { const p = C.spark.curve.getPointAt(s); return [p.x, p.y, p.z]; }),
        births: Array.from(C.spark.trailAttr.array).filter((_, i) => i % 4 === 3),
        us, progress: us.map((u) => C.sparkProgress(u)),
        cams: us.map((u) => { const c = C.camera(u); return [c.pos.x, c.pos.y, c.pos.z, c.target.x, c.target.y, c.target.z, c.fov]; }),
        areas: us.map((u) => C.areaAt(u)), moods: us.map((u) => C.moodAt(u)),
    };
}
console.log(JSON.stringify(out));
