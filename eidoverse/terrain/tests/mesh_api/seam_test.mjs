// The seams' creases (PORT_PLAN.md 7.3, 8.2 P4): the port of blender/tests/terrain/mesh_api/test_seam_crease.py and
// of test_mesh.py's seam_creases, on the port's ring mesh of every fixture case mesh_expected.py made.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/mesh_api/seam_test.mjs [case ...]
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front). For each seam (ring k's border inside
// ring k - 1), at 2,000 points along it, the angle between the triangle normals a quarter of a vertex spacing
// outside and inside the border; the same across lattice lines three spacings inside the child ring and three
// outside in the parent ring, which every ring has everywhere (test_mesh.py border_points and crease_deg, the points
// from numpy's default_rng(7): core/np_random.js). Per case:
//   points     the sample points equal Blender's to the bit
//   creases    every crease Blender's within its dot product's rounding (acos near 0) where the two triangles'
//              corners have Blender's heights, and elsewhere within the turn their height differences allow: a normal
//              whose corners move by at most d on legs of at least s turns by at most 2 sqrt(2) d / s (the normal as a
//              function of the gradient is 1-Lipschitz in angle); the seams' p50, p90 and p99 within the largest such
//              turn of Blender's
//   criteria   real data (the saves), test_seam_crease.py's: a seam within 25 % + 0.1 degree of the ordinary lines at
//              p50 and p99 reads like any other row of the mesh; every level sampling one rough surface (the
//              synthetic rough_5x512_cores, where any extra bend at a border is the mesh's), test_mesh.py
//              seam_creases': within 10 %. Each seam's verdict must be Blender's on the same fields (the port's
//              topology is Blender's index for index, mesh_test.mjs); a seam over the criterion is listed with both
//              editions' numbers

import * as G from '../../core/gpu.js';
import { RingMesh, buildRings } from '../../build/mesh.js';
import { defaultRng } from '../../core/np_random.js';
import { readNpz } from '../../core/io.js';
import { Level } from '../../core/levels.js';
import * as C from './_common.mjs';

const args = Deno.args.filter((a) => !a.startsWith('--'));
const cases = C.fixtureCases(args.length ? args : null);
if (!cases) Deno.exit(0);
const R = await G.init();
const T = new C.Checks('mesh and API: the seams\' creases (test_seam_crease.py)');
T.extra.cases = {};
const DEG = 180.0 / Math.PI;

// the fixture's levels and heights (as mesh_test.mjs reads them)
async function levelsOf(name, man) {
    if (man.kind === 'synthetic') {
        const levels = man.windows.map(([x0, y0, cell, n]) => ({ x0, y0, cell, n }));
        return { levels, heights: levels.map((_, k) => C.arr(name, man, `h_${k}`)) };
    }
    const levels = man.plan.map((d) => Level.fromDict(d));
    const want = levels.map((_, i) => `L${i}__f__h`);
    const z = await readNpz(C.blenderPath(man.save) + '.npz', { names: want });
    return { levels, heights: want.map((k) => z[k].data) };
}

// test_mesh.py border_points, in numpy 2's arithmetic: x0 = r.xm[0] + inset is a float32 scalar plus a Python float
// (float32 under NEP 50), x1 - x0 float32, t * (x1 - x0) and x0 + ... float64, np.full(k, x0) float32
function borderPoints(r, inset, n = 2000) {
    const f = Math.fround;
    const x0 = f(r.xm[0] + f(inset)), x1 = f(r.xm[r.nx - 1] - f(inset)), y0 = f(r.ym[0] + f(inset)), y1 = f(r.ym[r.ny - 1] - f(inset));
    const k = Math.floor(n / 4);
    const t = defaultRng(7).uniform(0.03, 0.97, k);
    const dx = f(x1 - x0), dy = f(y1 - y0);
    const xs = new Float64Array(4 * k), ys = new Float64Array(4 * k), nx = new Float64Array(4 * k), ny = new Float64Array(4 * k);
    for (let q = 0; q < k; q++) {
        xs[q] = x0 + t[q] * dx; ys[q] = y0; ny[q] = -1;
        xs[k + q] = x0 + t[q] * dx; ys[k + q] = y1; ny[k + q] = 1;
        xs[2 * k + q] = x0; ys[2 * k + q] = y0 + t[q] * dy; nx[2 * k + q] = -1;
        xs[3 * k + q] = x1; ys[3 * k + q] = y0 + t[q] * dy; nx[3 * k + q] = 1;
    }
    return [xs, ys, nx, ny];
}

// the cell normal_at(smooth=False) reads at a point: its ring, lattice cell, and the cell's smaller side
function cellOf(rm, x, y) {
    const [cx, cy] = rm._clamp(x, y);
    const k = rm._ringOf(cx, cy);
    const r = rm.rings[k];
    const [i, j] = RingMesh._locate(r, cx, cy);
    return { k, i, j, side: Math.min(r.xm[i + 1] - r.xm[i], r.ym[j + 1] - r.ym[j]) };
}

/** test_mesh.py crease_deg, and per point the bound of its difference from Blender's (degrees): the turn the two
 * cells' height differences allow (0 where their corners have Blender's heights), and `acos`'s width over the dot
 * product's last bits (near a zero crease the arc cosine turns a rounding of the dot product into about 1e-6
 * degrees). `dz[k]` is ring k's |Z_port - Z_blender| per lattice point. */
function creases(rm, dz, pts, d) {
    const [xs, ys, nx, ny] = pts;
    const n = xs.length;
    const out = new Float64Array(n), bound = new Float64Array(n), round = new Float64Array(n);
    const eps = 4 * Number.EPSILON;
    const turn = (c) => {
        const r = rm.rings[c.k], D = dz[c.k], w = r.nx;
        const m = Math.max(D[c.j * w + c.i], D[c.j * w + c.i + 1], D[(c.j + 1) * w + c.i + 1], D[(c.j + 1) * w + c.i]);
        return 2 * Math.SQRT2 * m / c.side;
    };
    for (let q = 0; q < n; q++) {
        const ax = xs[q] - nx[q] * d, ay = ys[q] - ny[q] * d, bx = xs[q] + nx[q] * d, by = ys[q] + ny[q] * d;
        const a = rm.normalAt(ax, ay, false), b = rm.normalAt(bx, by, false);
        const dot = Math.min(Math.max(a[0] * b[0] + a[1] * b[1] + a[2] * b[2], -1.0), 1.0);
        out[q] = Math.acos(dot) * DEG;
        bound[q] = (turn(cellOf(rm, ax, ay)) + turn(cellOf(rm, bx, by))) * DEG;
        round[q] = (Math.acos(Math.max(dot - eps, -1.0)) - Math.acos(Math.min(dot + eps, 1.0))) * DEG + 1e-9;
    }
    return { deg: out, bound, round };
}

// np.percentile(a, q) of float64 data with a Python-number q (numpy 2.3.4: the linear method, _lerp's two forms)
function percentile(a, q) {
    const s = Float64Array.from(a).sort();
    const idx = (s.length - 1) * (q / 100);
    const lo = Math.floor(idx), hi = Math.min(lo + 1, s.length - 1), t = idx - lo;
    const d = s[hi] - s[lo];
    return t >= 0.5 ? s[hi] - d * (1 - t) : s[lo] + d * t;
}

const pct = (a) => [50, 90, 99].map((q) => percentile(a, q));
const concat = (a, b) => {
    const o = new Float64Array(a.length + b.length);
    o.set(a);
    o.set(b, a.length);
    return o;
};
// the two editions' criteria: test_seam_crease.py's (real data) and test_mesh.py seam_creases' (one surface)
const CRITERIA = {
    real: { what: '25 % + 0.1 degree', ok: (s, o) => s[0] <= o[0] * 1.25 + 0.1 && s[2] <= o[2] * 1.25 + 0.1 },
    one_surface: { what: '10 %', ok: (s, o) => s[0] <= 1.1 * o[0] && s[2] <= 1.1 * o[2] },
};

async function checkCase(name) {
    const man = C.manifest(name);
    if (!man.creases || !Object.keys(man.creases).length) return;
    const rec = { seams: {} };
    T.extra.cases[name] = rec;
    const tag = (s) => `${name}: ${s}`;
    const { levels, heights } = await levelsOf(name, man);
    const rm = await buildRings(R, levels, heights, { cores: man.cores, meshRes: man.mesh_res });
    // |Z_port - Z_blender| per lattice point of every ring
    const dz = rm.rings.map((r, k) => {
        const zb = C.arr(name, man, `Z_${k}`), out = new Float64Array(r.Z.length);
        for (let q = 0; q < out.length; q++) out[q] = Math.abs(r.Z[q] - zb[q]);
        return out;
    });
    const crit = man.kind === 'synthetic' && name.startsWith('rough') ? 'one_surface' : 'real';
    let pointsOk = true, creaseOk = true, pctOk = true, sameVerdicts = true, worstRatio = 0, worstExact = 0, firstBad = '';
    const over = [], within = [];
    for (let k = 1; k < rm.rings.length; k++) {
        const child = rm.rings[k], parent = rm.rings[k - 1];
        const sc = child.spec.sp * rm.unit, sp = parent.spec.sp * rm.unit;
        const parts = { seam: [0.0, 0.25 * Math.min(sc, sp)], inner: [3 * sc, 0.25 * sc], outer: [-3 * sp, 0.25 * sp] };
        const got = {}, want = {};
        for (const [part, [inset, d]] of Object.entries(parts)) {
            const pts = borderPoints(child, inset);
            const bp = C.arr(name, man, `crease_${part}_points_${k}`);           // (2000, 4): x, y, nx, ny
            for (let q = 0; q < pts[0].length && pointsOk; q++) {
                for (let c = 0; c < 4; c++) {
                    if (pts[c][q] !== bp[4 * q + c]) {
                        pointsOk = false;
                        firstBad ||= `seam ${k} ${part} point ${q}: column ${c} ${pts[c][q]} vs ${bp[4 * q + c]}`;
                    }
                }
            }
            got[part] = creases(rm, dz, pts, d);
            want[part] = C.arr(name, man, `crease_${part}_${k}`);
            for (let q = 0; q < want[part].length; q++) {
                const e = Math.abs(got[part].deg[q] - want[part][q]), b = got[part].bound[q], rd = got[part].round[q];
                if (b === 0) {
                    worstExact = Math.max(worstExact, e / rd);
                    if (e > rd) {
                        creaseOk = false;
                        firstBad ||= `seam ${k} ${part} point ${q}: ${got[part].deg[q]} vs ${want[part][q]} deg with Blender's heights (rounding ${rd})`;
                    }
                } else {
                    worstRatio = Math.max(worstRatio, e / (b + rd));
                    if (e > b + rd) {
                        creaseOk = false;
                        firstBad ||= `seam ${k} ${part} point ${q}: ${got[part].deg[q]} vs ${want[part][q]} deg, bound ${b} + ${rd}`;
                    }
                }
            }
        }
        const sPort = pct(got.seam.deg), sBl = pct(want.seam);
        const oPort = pct(concat(got.inner.deg, got.outer.deg)), oBl = pct(concat(want.inner, want.outer));
        const most = (...cs) => Math.max(...cs.flatMap((c) => Array.from(c.bound, (b, q) => b + c.round[q])));
        const bSeam = most(got.seam), bOrd = most(got.inner, got.outer);
        for (let q = 0; q < 3; q++) {
            if (Math.abs(sPort[q] - sBl[q]) > bSeam || Math.abs(oPort[q] - oBl[q]) > bOrd) {
                pctOk = false;
                firstBad ||= `seam ${k}: percentiles ${sPort.map((v) => v.toFixed(4))} / ${oPort.map((v) => v.toFixed(4))} vs ${sBl.map((v) => v.toFixed(4))} / ${oBl.map((v) => v.toFixed(4))}`;
            }
        }
        const vPort = CRITERIA[crit].ok(sPort, oPort), vBl = CRITERIA[crit].ok(sBl, oBl);
        if (vPort !== vBl) {
            sameVerdicts = false;
            firstBad ||= `seam ${k}: the port ${vPort ? 'within' : 'over'}, Blender ${vBl ? 'within' : 'over'}`;
        }
        (vPort ? within : over).push(k);
        rec.seams[k] = { spacing_m: [sp, sc], seam_p50_p90_p99_deg: sPort, ordinary_p50_p90_p99_deg: oPort,
            blender_seam_p50_p90_p99_deg: sBl, blender_ordinary_p50_p90_p99_deg: oBl, criterion: CRITERIA[crit].what,
            within: vPort, blender_within: vBl, bound_deg: [bSeam, bOrd] };
        console.log(`  ${name} seam ${k} (${sp} -> ${sc} m): seam p50/p90/p99 ${sPort.map((v) => v.toFixed(2)).join('/')} deg, ordinary ` +
            `${oPort.map((v) => v.toFixed(2)).join('/')} deg ${vPort ? 'WITHIN' : 'OVER'} (Blender ${sBl.map((v) => v.toFixed(2)).join('/')} / ` +
            `${oBl.map((v) => v.toFixed(2)).join('/')} ${vBl ? 'WITHIN' : 'OVER'})`);
    }
    rec.within = within;
    rec.over = over;
    rec.worst_over_bound = worstRatio;
    rec.worst_over_rounding_where_heights_equal = worstExact;
    T.ok(tag('the sample points equal Blender\'s to the bit (numpy\'s default_rng(7) and border_points\' arithmetic)'), pointsOk, pointsOk ? `${rm.rings.length - 1} seams x 6,000 points` : firstBad);
    T.ok(tag('every crease Blender\'s: within the dot product\'s rounding where the heights are Blender\'s, within the turn their differences allow elsewhere; the percentiles within the largest turn'),
        creaseOk && pctOk, creaseOk && pctOk ? `worst / rounding ${worstExact.toFixed(3)} where equal; worst / bound ${worstRatio.toFixed(3)} elsewhere` : firstBad);
    T.ok(tag(`criterion (${CRITERIA[crit].what} of the ordinary lines at p50 and p99): every seam's verdict Blender's on the same fields`),
        sameVerdicts, `within: ${within.join(', ') || 'none'}; over: ${over.length ? over.map((k) => `${k} (${rec.seams[k].spacing_m.join(' -> ')} m)`).join(', ') : 'none'}` +
        (sameVerdicts ? '' : `; ${firstBad}`));
    if (crit === 'one_surface') {
        T.ok(tag('one surface sampled by every level: every seam within 10 % of the ordinary lines (the seam rule alone)'), over.length === 0,
            over.length ? `over: ${over.join(', ')}` : `${within.length} seams`);
    }
    rm.dispose();
}

for (const name of cases) {
    try {
        await checkCase(name);
    } catch (e) {
        T.ok(`${name}: ran`, false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 8).join('\n')}`);
    }
}
G.shutdown();
Deno.exit(C.finish(T, 'seam_test.json'));
