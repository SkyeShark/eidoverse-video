// Port of blender/eidoblend/terrain/solvers/impact.py at f90c6fc.
//
// Impact craters for the new makeTerrain (design section 4.8): the analytic crater stamp.
//
//     craterDimensions(D, gravity)   Pike 1977's morphometry: simple craters depth 0.2 D and rim 0.036 D; complex craters
//                                    the lunar fits at the lunar-equivalent diameter, the simple-to-complex transition
//                                    (10.6 km on the Moon) scaled by 1/g (about 1.75 km on Earth)
//     impact crater                  the crater as a height change over the pre-impact surface (kernels/impact/
//                                    crater.wgsl): a parabolic bowl, an infilled floor, or with cliffs the concave
//                                    debris apron under the target's bedded face (Meteor Crater's); the rim crest
//                                    rounded; the ejecta (r/R)^-3 out to 2-3 R with hummocks, blocks and rays; a polygonal
//                                    planform; complex craters' floor, terraces and central peak cluster
//     boulders                       blocks on a hashed lattice (kernels/impact/blocks.wgsl)
//
// Reference preset: METEOR_CRATER. Stage ops: OPS = { impact_crater, crater_blocks } (the op contract is volcanic.js's).
//
// Where this differs from impact.py, and why (PORT_PLAN.md 2.4, 3.2): the crater and the blocks are evaluated per
// point by the port's own kernels (float32, graded against numpy, tests/volcanoes_craters/); their 1D tables (the
// polygon's planform, the azimuth noises) and the plans over objects (the terraces, the peaks) stay JavaScript in
// doubles, as numpy computes them. With cliffs the strength (Sc) is the layered face's step function of a point's
// float32 run, as caldera_collapse's (volcanic.js says how it is graded). The rest as volcanic.js says.

import * as Gd from '../core/grid.js';
import { ValueError, pyFormat } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import * as VO from './volcanic.js';

export const G_EARTH = 9.81;
export const G_MOON = 1.62;
export const MOON_TRANSITION_M = 10600.0;       // Pike 1977: where the simple and complex depth fits meet
const TAU = VO.TAU;
const DEG = Math.PI / 180.0;
const num = (v, d) => (v === undefined || v === null ? d : Number(v));
const has = (o, k) => o !== null && o !== undefined && Object.prototype.hasOwnProperty.call(o, k);

/** Pike's numbers for a fresh crater of diameter D (rim crest to rim crest), metres (impact.py crater_dimensions). */
export function craterDimensions(diameterM, gravity = G_EARTH, depthRatio = 0.2, rimRatio = 0.036) {
    const D = Number(diameterM);
    const s = G_MOON / Number(gravity);
    const Dt = MOON_TRANSITION_M * s;
    if (D < Dt) {
        return { kind: 'simple', depth_m: Number(depthRatio) * D, rim_m: Number(rimRatio) * D, floor_diameter_m: 0.0, transition_m: Dt };
    }
    const Dm = D / s / 1000.0;                           // the lunar-equivalent diameter, km
    return { kind: 'complex', depth_m: 1044.0 * Dm ** 0.301 * s, rim_m: 236.0 * Dm ** 0.399 * s,
        floor_diameter_m: 187.0 * Dm ** 1.249 * s, transition_m: Dt };
}

/** polygon_factor's table: a rounded regular polygon's radius as a factor of azimuth, mean 1 (sides straight sides,
 * the first side's outward normal at azimuthDeg, corners rounded by a soft maximum), blended with the circle by
 * strength: the AZ_SAMPLES + 1 values of 1 + strength (p - 1), as numpy builds them; null for a circle. */
export function polygonTable(sides, strength, azimuthDeg = 0.0, roundness = 0.08) {
    if (sides < 3 || strength <= 0.0) return null;
    const t = VO.AZ_TABLE_ANGLES;
    const normals = Array.from({ length: Math.trunc(sides) }, (_, k) => azimuthDeg * DEG + TAU * k / Math.trunc(sides));
    const beta = 1.0 / Math.max(Number(roundness), 1e-3);
    const p = new Float64Array(t.length);
    const c = new Float64Array(normals.length), e = new Float64Array(normals.length);
    for (let i = 0; i < t.length; i++) {
        let cmax = -Infinity;
        for (let k = 0; k < normals.length; k++) {
            c[k] = Math.cos(t[i] - normals[k]);
            cmax = Math.max(cmax, c[k]);
        }
        for (let k = 0; k < normals.length; k++) e[k] = Math.exp(beta * (c[k] - cmax));
        const m = cmax + Math.log(VO.npSum(e)) / beta;
        p[i] = 1.0 / m;
    }
    const mean = VO.npSum(p.subarray(0, t.length - 1)) / (t.length - 1);
    for (let i = 0; i < t.length; i++) p[i] = 1.0 + Number(strength) * (p[i] / mean - 1.0);
    return p;
}

/** polygon_factor at one azimuth (radians), in doubles: 1 for a circle. */
export function polygonFactor(az, sides, strength, azimuthDeg = 0.0, roundness = 0.08) {
    const t = polygonTable(sides, strength, azimuthDeg, roundness);
    return t ? VO.azRead(t, az) : 1.0;
}

// the defaults of impact_crater's keyword arguments
const CRATER_DEFAULTS = Object.freeze({ centre: [0.0, 0.0], diameter_m: 1200.0, gravity: G_EARTH, depth_ratio: 0.2,
    rim_ratio: 0.036, fill_ratio: null, fill_round: 0.25, sides: 4, polygon: 0.45, polygon_azimuth_deg: 0.0,
    radius_noise: 0.02, edge_noise: 0.01, rim_noise: 0.2, crest_round: 0.35, ejecta_reach: 2.4, ejecta_exponent: 3.0,
    hummocks: 0.05, hummock_scale: 0.10, blocks: 0.02, rays: 0.04, peak_height_frac: 0.4, peak_width_frac: 0.2,
    terraces: 4, cliffs: null, seed: 0 });

const { noiseTexels, fbmTerms } = VO;

/** impact_crater at a grid's points: { delta, ejecta, fill, talus, strength (with cliffs) } fields of the grid's size
 * (the caller's), and its kind and dims. */
export async function impactCrater(R, grid, params) {
    const p = { ...CRATER_DEFAULTS, ...params };
    const D = Number(p.diameter_m);
    const dims = craterDimensions(D, p.gravity, p.depth_ratio, p.rim_ratio);
    const R0 = 0.5 * D;
    const d = dims.depth_m, hm = dims.rim_m;
    const seed = Math.trunc(p.seed);
    const centre = [Number(p.centre[0]), Number(p.centre[1])];
    const reach = 0.5 * D * Math.max(Number(p.ejecta_reach), 1.6) * (1.0 + Number(p.polygon) * 0.6 + 4.0 * Number(p.radius_noise) +
        4.0 * Number(p.edge_noise)) * 1.05;
    const tabs = new VO.AzTables();
    const pg = polygonTable(Math.trunc(p.sides), Number(p.polygon), Number(p.polygon_azimuth_deg));
    const rows = { pg: pg ? tabs.add(pg) : 0, n61: 0, n64: 0, n62: 0, n63: 0, n66: 0 };
    if (Number(p.radius_noise)) rows.n61 = tabs.add(VO.azimuthNoiseTable(seed, 61, 1, 6));
    if (Number(p.edge_noise)) rows.n64 = tabs.add(VO.azimuthNoiseTable(seed, 64, 8, 40, 1.0));
    if (Number(p.rim_noise)) rows.n62 = tabs.add(VO.azimuthNoiseTable(seed, 62, 1, 4));
    if (Number(p.rays)) rows.n63 = tabs.add(VO.azimuthNoiseTable(seed, 63, 12, 56, 0.6));
    const complex = dims.kind === 'complex';
    const fill = p.fill_ratio === null || p.fill_ratio === undefined ? null : Number(p.fill_ratio);
    // the apron under the face (cliffs and a fill, simple craters)
    let apron = null, face = null;
    if (!complex && VO.truthy(p.cliffs) && fill !== null) {
        const spec = { ...p.cliffs };
        const tDeg = num(spec.talus_deg, 33.0), tf = num(spec.talus_frac, 0.6), faceDeg = num(spec.face_deg, 52.0);
        const vary = num(spec.apron_vary, 0.12), mounds = num(spec.mounds_m, 0.0);
        for (const k of ['talus_deg', 'talus_frac', 'face_deg', 'apron_vary', 'mounds_m']) delete spec[k];
        const zc = hm - fill * D;
        const Hw = hm - zc;
        if (!(tf > 0.05 && tf < 0.95)) throw new ValueError(`impact crater: talus_frac ${tf} must lie between 0.05 and 0.95 of the wall`);
        const zt = zc + tf * Hw;
        face = VO.faceTable(R, hm - zt, faceDeg, spec, seed);
        if (vary) rows.n66 = tabs.add(VO.azimuthNoiseTable(seed, 66, 8, 90, 0.4));
        apron = { tt: Math.tan(tDeg * DEG), tw: Math.tan(faceDeg * DEG), tf, vary, mounds, zc };
    }
    // the infilled floor's check (impact.py raises before it fills, where there is no apron)
    if (!apron && fill !== null && hm - fill * D <= hm - d) {
        throw new ValueError(`impact crater: fill_ratio ${fill} puts the fill below the bowl (${pyFormat(d / D, '.3f')} D)`);
    }
    // a complex crater's terraces and central peaks (impact.py _complex_interior, _central_peak: their numpy draws)
    const terr = [], peaks = [];
    if (complex) {
        const rng = defaultRng([Math.abs(seed), 65]);
        for (let k = 0; k < Math.trunc(p.terraces); k++) {
            const q0 = rng.uniform(0.3, 0.85), half = rng.uniform(0.07, 0.12);
            const a0 = rng.uniform(0.0, TAU), span = rng.uniform(50.0, 140.0) * DEG;
            terr.push([q0, half, a0, span]);
        }
        const prng = defaultRng([Math.abs(seed), 67]);
        const base = 0.5 * Number(p.peak_width_frac) * D, top = Number(p.peak_height_frac) * d;
        const count = 1 + prng.integers(2, 5);
        for (let k = 0; k < count; k++) {
            let cx, cy, h, rad;
            if (k === 0) {
                [cx, cy, h, rad] = [centre[0], centre[1], top, base];
            } else {
                const a = prng.uniform(0.0, TAU), dist = prng.uniform(0.25, 0.6) * base;
                cx = centre[0] + dist * Math.sin(a);
                cy = centre[1] + dist * Math.cos(a);
                h = top * prng.uniform(0.45, 0.8);
                rad = base * prng.uniform(0.4, 0.65);
            }
            peaks.push([grid.ox - cx, grid.oy - cy, h, rad, tabs.add(VO.azimuthNoiseTable(seed + k, 68, 2, 7))]);
        }
    }
    const prm = new Float32Array(40);
    prm.set([D, R0, d, hm], 0);
    prm.set([complex ? 1 : 0, dims.floor_diameter_m / D, fill === null ? -1 : fill, Number(p.fill_round)], 4);
    prm.set([pg ? 1 : 0, Number(p.radius_noise), Number(p.edge_noise), Number(p.rim_noise)], 8);
    prm.set([Number(p.crest_round), Number(p.ejecta_reach), Number(p.ejecta_exponent), Number(p.hummocks)], 12);
    prm.set([Number(p.blocks), Number(p.rays), reach, 0.0], 16);
    prm.set([rows.pg, rows.n61, rows.n64, rows.n62], 20);
    prm.set([rows.n63, rows.n66, apron ? 1 : 0, apron ? apron.mounds : 0.0], 24);
    if (apron) prm.set([apron.tt, apron.tw, apron.tf, apron.vary], 28);
    prm.set([face ? face.U : 0.0, apron ? apron.zc : 0.0, terr.length, peaks.length], 32);
    prm.set([0.0, 0.0, 0.0, 0.0], 36);
    // hummocks (fbm at hummock_scale D, seed + 71), blocks (0.012 D at seed + 73, 0.006 D at seed + 79), mounds (fbm
    // at 0.08 D, seed + 83)
    const terms = [...fbmTerms(Number(p.hummock_scale) * D, seed + 71), [0.012 * D, seed + 73], [0.006 * D, seed + 79],
        ...fbmTerms(0.08 * D, seed + 83)];
    const ttab = new Float32Array(4 * Math.max(terr.length, 1));
    terr.forEach((t, k) => ttab.set(t, 4 * k));
    const ptab = new Float32Array(8 * Math.max(peaks.length, 1));
    peaks.forEach((q, k) => { ptab.set(q.slice(0, 4), 8 * k); ptab[8 * k + 4] = q[4]; });
    const D_ = Gd.dummies(R);
    const fP = R.field(1, 10, 4, prm), fN = R.field(1, 2 * Math.max(terms.length, 1), 4, noiseTexels(grid, terms));
    const fT = R.field(1, Math.max(terr.length, 1), 4, ttab), fK = R.field(1, 2 * Math.max(peaks.length, 1), 4, ptab);
    const shape = [grid.h, grid.w];
    const out = { delta: R.field(...shape, 1), ejecta: R.field(...shape, 1), fill: R.field(...shape, 1), talus: R.field(...shape, 1),
        strength: R.field(...shape, 1) };
    R.run('impact/crater', { azt: tabs.field(R), zst: face ? face.zst : D_.f2, s0t: face ? face.s0t : D_.f1, prm: fP, ntab: fN,
        ttab: fT, ptab: fK }, { outD: out.delta, outE: out.ejecta, outF: out.fill, outT: out.talus, outS: out.strength },
    { uOrg: [grid.ox - centre[0], grid.oy - centre[1]], uStep: grid.step });
    for (const f of [fP, fN, fT, fK]) f.destroy();
    tabs.destroy();
    if (!VO.truthy(p.cliffs)) {
        out.strength.destroy();
        delete out.strength;
    }
    return { ...out, kind: dims.kind, dims };
}

/** The reference preset (impact.py METEOR_CRATER, measured from the meteor_crater DEM). */
export const METEOR_CRATER = Object.freeze({
    centre: [30.0, 0.0], diameter_m: 1194.0, depth_ratio: 0.2, rim_ratio: 0.0437, fill_ratio: 0.1426, sides: 4,
    polygon: 0.42, polygon_azimuth_deg: 75.0, radius_noise: 0.035, rim_noise: 0.2, crest_round: 0.35, ejecta_reach: 2.3,
    rays: 0.0, seed: 11,
});


// ============================================================================================== the stage ops ===

/** Stage op 'impact_crater': params are impact_crater's (plus supersample, applied on the main level only). Adds the
 * crater to h once (volcanic.js stampAdd); bed takes the excavation and the rim's uplift (all but the loose ejecta,
 * the floor's fill and the talus); the fill is recorded as deposit and the apron as talus. With cliffs, Sc takes the
 * strength the wall was built at (tan 38 degrees off the wall). Skips the coarsest level's pre-passes. */
export async function opImpactCrater(fields, level, params, seed = 0, ctx = null) {
    if (VO.isPrepass(ctx)) return fields;
    const R = ctx?.device ?? fields.h.runner;
    const p = { ...params };
    let s = Math.trunc(Number(p.supersample ?? 1));
    delete p.supersample;
    if ((level.role ?? 'main') !== 'main') s = 1;      // the main level's box filter is the judge's
    if (!has(p, 'seed')) p.seed = seed;
    for (const k of ['talus', 'deposit']) if (!(k in fields)) fields.new(k);
    const evaluate = async (grid) => {
        const out = await impactCrater(R, grid, p);
        const bed = VO.ew(R, VO.EW.SUB3, out.delta, out.ejecta, out.fill, out.talus);
        const res = { h: out.delta, bed, deposit: out.fill, talus: out.talus };
        out.ejecta.destroy();
        if (out.strength) res.strength = out.strength;   // evaluated and returned, not a field (the threshold below)
        return res;
    };
    const here = await VO.stampAdd(fields, level, VO.stampKey('impact_crater', { ...params, seed: p.seed }), evaluate, s, ctx,
        { strength: 'nanmax' });
    if (here.strength) {
        fields.Sc = VO.ew(R, VO.EW.STRENGTH, here.strength, null, null, null, Math.tan(30.0 * DEG), Math.tan(38.0 * DEG));
    }
    VO.release(here);
    VO.pullBand(fields, ctx);
    return fields;
}
opImpactCrater.evolves = true;          // called on every pass of the coarsest level; the stamp skips the pre-passes

/** boulders' sets as kernels/impact/blocks.wgsl reads them, for a grid: six texels per set. */
function blockTexels(grid, sets, sd) {
    const out = new Float32Array(24 * sets.length);
    const bits = new Uint32Array(out.buffer);
    const xmin = grid.x(0), xmax = grid.x(grid.w - 1), ymin = grid.y(0), ymax = grid.y(grid.h - 1);
    sets.forEach((s, i) => {
        const L = Number(s.spacing_m), s0 = Number(s.size_m[0]), s1 = Number(s.size_m[1]), a = num(s.exponent, 2.5);
        const tail = 1.0 - (s1 / s0) ** -a;
        const hf = (s.height_frac ?? [0.3, 0.6]).map(Number);
        const reach = 0.75 * s1;
        const IX0 = Math.floor((xmin - reach) / L), IX1 = Math.floor((xmax + reach) / L);
        const IY0 = Math.floor((ymin - reach) / L), IY1 = Math.floor((ymax + reach) / L);
        const IXb = Math.floor(grid.ox / L), IYb = Math.floor(grid.oy / L);
        const [r0, r1, r2, r3] = s.rho.map(Number);
        out.set([L, s0, s1, a], 24 * i);
        out.set([tail, hf[0], hf[1], (s.profile ?? 'slab') === 'mound' ? 1 : 0], 24 * i + 4);
        out.set([Number(s.density), r0, r1, r2], 24 * i + 8);
        out.set([r3, 0.0, IX0, IY0], 24 * i + 12);
        bits[24 * i + 13] = VO.u32of(Math.trunc(sd) * 131 + 7919 + i);
        out.set([IX1, IY1, grid.ox - L * IXb, grid.oy - L * IYb], 24 * i + 16);
        out.set([IXb, IYb, s._cx, s._cy], 24 * i + 20);
    });
    return out;
}

/** Stage op 'crater_blocks': the blocks fallen from a crater's face, over the debris apron's upper part and at its
 * foot, thinning out onto the floor; and mounds of sediment on the floor. params: crater (the impact_crater stage's
 * centre, diameter_m and planform), sets ([{ spacing_m, size_m, density, rho (four radii over the crater's broad
 * outline), height_frac, profile }]). Added once per terrain (stampAdd) to h, and to bed (blocks) or deposit
 * (mounds). */
export async function opCraterBlocks(fields, level, params, seed = 0, ctx = null) {
    if (VO.isPrepass(ctx)) return fields;
    const R = ctx?.device ?? fields.h.runner;
    const c = { ...params.crater };
    const sd = Math.trunc(Number(c.seed ?? seed));
    const centre = [num(c.centre?.[0], 0.0), num(c.centre?.[1], 0.0)];
    const R0 = 0.5 * Number(c.diameter_m);
    const sides = Math.trunc(num(c.sides, 0)), polygon = num(c.polygon, 0.0);
    const paz = num(c.polygon_azimuth_deg, 0.0), rn = num(c.radius_noise, 0.0);
    const sets = (params.sets ?? []).map((s) => ({ ...s }));
    const reach = R0 * Math.max(...sets.map((s) => Number(s.rho[3]))) * 1.3 + Math.max(...sets.map((s) => Number(s.size_m[1])));
    const evaluate = async (grid) => {
        const shape = [grid.h, grid.w];
        // the points' nearest approach to the centre (np.min(np.hypot(x - cx, y - cy)) over the grid)
        const near = (o, c0, n) => {
            const f = (c0 - o) / grid.step - 0.5;
            return [Math.floor(f), Math.ceil(f)].map((i) => Math.min(Math.max(i, 0), n - 1));
        };
        let dmin = Infinity;
        for (const i of near(grid.ox, centre[0], grid.w)) {
            for (const j of near(grid.oy, centre[1], grid.h)) dmin = Math.min(dmin, Math.hypot(grid.x(i) - centre[0], grid.y(j) - centre[1]));
        }
        if (dmin > reach) {
            const z = Gd.fill(R, shape, 0.0);
            return { h: z, bed: Gd.fill(R, shape, 0.0), deposit: Gd.fill(R, shape, 0.0) };
        }
        const tabs = new VO.AzTables();
        const pg = polygonTable(sides, polygon, paz);
        const pgRow = pg ? tabs.add(pg) : 0;
        const rnRow = rn ? tabs.add(VO.azimuthNoiseTable(sd, 61, 1, 6)) : 0;
        for (const s of sets) {
            const L = Number(s.spacing_m), IXb = Math.floor(grid.ox / L), IYb = Math.floor(grid.oy / L);
            s._cx = L * IXb - centre[0];
            s._cy = L * IYb - centre[1];
        }
        const prm = R.field(1, 2, 4, Float32Array.from([R0, pg ? 1 : 0, rn, 0.0, pgRow, rnRow, sets.length, 0.0]));
        const stab = R.field(1, 6 * Math.max(sets.length, 1), 4, blockTexels(grid, sets, sd));
        const out = { h: R.field(...shape, 1), bed: R.field(...shape, 1), deposit: R.field(...shape, 1) };
        R.run('impact/blocks', { azt: tabs.field(R), stab, prm }, { outH: out.h, outB: out.bed, outD: out.deposit }, { uStep: grid.step });
        for (const f of [prm, stab]) f.destroy();
        tabs.destroy();
        return out;
    };
    // one pass (block false): boulders loops over the blocks themselves
    const here = await VO.stampAdd(fields, level, VO.stampKey('crater_blocks', { ...params, seed: sd }), evaluate, 1, ctx, null, false);
    VO.release(here);
    VO.pullBand(fields, ctx);
    return fields;
}
opCraterBlocks.evolves = true;

export const OPS = { impact_crater: opImpactCrater, crater_blocks: opCraterBlocks };

export { craterDimensions as crater_dimensions, polygonFactor as polygon_factor };
