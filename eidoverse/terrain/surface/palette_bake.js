// Port of blender/eidoblend/terrain/surface/palette_bake.py at d67f19e.
//
// The palette's maps (SURFACING_DESIGN.md 2.3, the palette bake), on the bake's levels, coarsest first:
//
//     import * as PB from './surface/palette_bake.js';
//     const colour = await PB.bake(sd, palette);   // per level a Map: 'far_colour' (n, n, 3), 'far_roughness',
//                                                  // 'down_colour' (n, n, 3), 'down_share': linear, float16 as the
//                                                  // cache keeps them; cached beside the bake by the palette's hash
//     PB.rockLayer(pal)                           // the palette's bare-rock layer
//
// Provenance colour P (down_colour, down_share). Sediment production P = fresh x bare (the mask language's `bare`)
// plus a small background, in m^2 of eroding ground per cell; the source colour c is the palette's bare-rock colour at
// the cell's stratigraphic height (the strata column's formation there, or the rock layer's colour). Both are routed
// down the bake's filled surface with the multiple-flow shares (route_colour.wgsl, route_area's scheme with four
// channels): Q = P + sum f Q_up, R = P c + sum f R_up, to convergence. down_colour = R / Q, the rock colours upstream
// weighted by where the ground erodes; down_share = Q / (Q + Q0), how much of the ground is carried sediment. A child
// level's margin holds its parent's Q and R (the specific values, as the drainage area's), so a catchment the window
// truncates still carries its upstream colour in.
//
// Far colour C (far_colour, far_roughness): the palette's ground per texel, every layer at its scan's mean
// (surface/far_colour.js, when it is there); without it the bake writes P only. C is made first; P is routed after it
// while the palette bake stays within its budget (BUDGET_S), else deferred (pMode). Each level's C and P are then
// pinned to its parent's across the border band (pinLevels), as the bake pins its maps.
//
// Where this differs from palette_bake.py, and why:
//   - The per-cell numpy work is GPU compute (the edition's rule): `bare` is the mask language compiled by
//     mask_expr.js into a generated kernel (palettes.evaluate(flat=True) in Blender, doubles), the rock colour per
//     cell kernels/palette/rock_colour.wgsl (doubles in Blender: a cell within float32's rounding of a formation's
//     top may take the formation beside it), the routing's inputs, its convergence measure and its results
//     kernels/palette/provenance_io.wgsl, the measure's maximum core/prims.js's reduction (palette_bake.py reads the
//     whole state back every 128 passes; here one number). The routing itself is Blender's route_colour kernel.
//   - The levels' maps are the bake's stored maps decoded (SurfaceData.maps), the same bytes whether the bake was just
//     made or read from the cache; a fresh Blender bake hands its palette bake the unquantised float32 maps, a cached
//     one the stored maps (so Blender's C and P of one terrain differ by which happened first; reported to the lead).
//   - The result per level is what the cache keeps (float16 arrays), read once from the GPU (the f16 encoding on the
//     GPU, kernels/port/encode.wgsl), so a bake and its cache hit hold the same values; Blender's fresh bake holds
//     float32 until it is reloaded.
//   - paletteHash hashes the palette as core/cache.js sortedJson writes it and this edition's PALETTE_CODE: the cache
//     tag is this edition's own (Blender's files are found by their own tag).

import { createHash } from 'node:crypto';
import * as ops from '../build/ops.js';
import * as P from '../build/palettes.js';
import { Compiler } from './mask_expr.js';
import * as B from './bake.js';
import * as Gd from '../core/grid.js';
import * as Ch from '../core/cache.js';
import * as Io from '../core/io.js';
import * as M from '../masks.js';
import * as HYD from '../solvers/hydraulic.js';
import { prims } from '../core/prims.js';
import { KeyError, ValueError } from '../core/levels.js';

const f32 = Math.fround;
export const BACKGROUND = 1.0e-3;           // production on every cell (m^2 per m^2): a catchment with no eroding rock
                                            // still carries its bedrock's colour
export const Q0_M2 = 1000.0;                // the eroding area upstream at which half the ground is carried sediment
export const BUDGET_S = 30.0;               // the palette bake's budget cold (SURFACING_DESIGN.md 7): past it P is deferred
export const PALETTE_BAKE_VERSION = 1;
export const NAMES = ['far_colour', 'far_roughness', 'down_colour', 'down_share'];

const sha1 = (s) => createHash('sha1').update(s).digest('hex');

/** A hash of the palette (its layers, options, strata and constants) and of the palette bake's code. */
export function paletteHash(pal) {
    const blob = Ch.sortedJson(pal);
    const code = B.codeHash(B.PALETTE_CODE);
    return sha1(blob + `|v${PALETTE_BAKE_VERSION}|${code}`).slice(0, 16);
}

/** The palette's bare-rock layer: the strata layer, else one named for rock, cliff or wall, else the first box
 * (steep-face) layer, else the first layer. */
export function rockLayer(pal) {
    const layers = pal.layers;
    for (const L of layers) if (L.strata) return L;
    for (const key of ['rock', 'cliff', 'wall', 'face']) {
        for (const L of layers) if (String(L.name ?? '').toLowerCase().includes(key)) return L;
    }
    for (const L of layers) if (L.projection === 'box') return L;
    return layers[0];
}

function meanColour(col) {
    if (Array.isArray(col) && Array.isArray(col[0])) {
        let w = 0;
        const s = [0, 0, 0];
        for (const [c, wt] of col) {
            for (let k = 0; k < 3; k++) s[k] += c[k] * wt;
            w += wt;
        }
        return s.map((v) => v / Math.max(w, 1e-9));
    }
    return col.map(Number);
}

/** The rock colour of level lv's cells at the stratigraphic heights zs (an r32f field): an rgba32f field (rgb),
 * palette_bake.rock_colour with the cell centres' world points. */
export function rockColour(R, pal, zs, lv) {
    const st = pal.strata ?? {};
    const out = R.field(zs.h, zs.w, 4);
    let form = new Float32Array(4), faults = new Float32Array(8), nf = 0, nfa = 0;
    let ucol = [0, 0, 0, 0], rock = [0, 0, 0];
    if (st.column && pal.layers.some((L) => L.strata)) {
        const layers = P.columnLayers(st.column, Boolean(st.looks ?? false));
        nf = layers.length;
        form = new Float32Array(4 * nf);
        layers.forEach((L, f) => {
            const c = meanColour(L[3]);
            form.set([L[2], c[0], c[1], c[2]], 4 * f);
        });
        const zLo = layers[0][1], zHi = layers[layers.length - 1][2];
        ucol = [Number(st.z_offset_m ?? 0.0), zLo, zHi, P.columnRepeats(st.column) ? 1 : 0];
        const fl = st.faults ?? [];
        nfa = fl.length;
        if (nfa) {
            faults = new Float32Array(8 * nfa);
            fl.forEach((f, k) => {
                const s = (Number(f.strike_deg ?? 0.0) * Math.PI) / 180;
                let nx = Math.cos(s), ny = -Math.sin(s);
                const want = { west: [-1, 0], east: [1, 0], north: [0, 1], south: [0, -1] }[f.down ?? 'west'];
                if (nx * want[0] + ny * want[1] < 0) {
                    nx = -nx;
                    ny = -ny;
                }
                faults.set([Number(f.x ?? 0.0), Number(f.y ?? 0.0), nx, ny], 4 * k);
                faults.set([Math.max(Number(f.width_m ?? 50.0), 1e-3), Number(f.throw_m ?? 0.0), 0, 0], 4 * (nfa + k));
            });
        }
    } else {
        rock = P.hexLinear(rockLayer(pal).colour).map(Number);
    }
    const fT = R.field(1, Math.max(nf, 1), 4, form);
    const faT = R.field(2, Math.max(nfa, 1), 4, nfa ? rowsOf(faults, nfa) : faults);
    R.run(B.kernel(R, 'palette/rock_colour'), { zsT: zs, formT: fT, faultT: faT }, { outC: out },
        { uCol: ucol.map(f32), uLevel: [f32(Number(lv.x0)), f32(Number(lv.y0)), f32(Number(lv.cell))], uRock: rock.map(f32),
            uN: nf, uFaults: nfa });
    fT.destroy();
    faT.destroy();
    return out;
}

// the faults' two rows (row 0 the points and normals, row 1 width and throw) as the field's row-major data
function rowsOf(faults, n) {
    return faults.slice(0, 8 * n);
}

/** The production kernel of a palette: (fresh x clamp(bare, 0, 1) + BACKGROUND) x cell^2, `bare` compiled with
 * every noise at its mean (palettes.evaluate(flat=True)). { kernel, names }. */
function productionKernel(R, pal) {
    const W = ops.WGSL();
    const comp = new Compiler({ ops: W, read: (nm) => ({ code: `@@${nm}@@`, type: 'f32', wgsl: true }), constants: pal.constants ?? null,
        flat: true });
    const bare = W.clamp(comp.expr('bare'), 0.0, 1.0);
    const names = [...comp.names].sort();
    const slot = Object.fromEntries(names.map((nm, k) => [nm, [k >> 2, k & 3]]));
    const ns = Math.max(1, (names.length + 3) >> 2);
    let body = W.body('  ');
    let bareCode = W.code(bare);
    for (const [nm, [s, c]] of Object.entries(slot)) {
        body = body.split(`@@${nm}@@`).join(`m${s}.${'xyzw'[c]}`);
        bareCode = bareCode.split(`@@${nm}@@`).join(`m${s}.${'xyzw'[c]}`);
    }
    const head = Array.from({ length: ns }, (_x, s) => `//! sampler maps${s}\n`).join('') + '//! sampler freshT\n' +
        '//! image outP r32f\n//! uniform float uCell2\n//! uniform float uBg\n';
    const src = '// production: the palette bake\'s eroding ground per cell, generated by surface/palette_bake.js.\n' + head +
        `\nfn kmain(p: vec2<i32>) {\n  if (!inside(p, outP_size())) { return; }\n` +
        Array.from({ length: ns }, (_x, s) => `  let m${s} = maps${s}_at(p);\n`).join('') + body +
        `\n  let fresh = freshT_at(p).x;\n  outP_store(p, vec4<f32>((fresh * ${bareCode} + u.uBg) * u.uCell2, 0.0, 0.0, 0.0));\n}\n`;
    return { kernel: R.kernel(`surface_production_${sha1(src).slice(0, 12)}`, { source: src }), names };
}

/** { prod (r32f: m^2 of eroding ground per cell), c (rgba32f: the linear rock colour) } on level i's cells. */
async function production(R, sd, pal, i) {
    const lv = sd.levels[i], n = lv.n, cell = Number(lv.cell);
    const m = await sd.maps(i);
    const { kernel, names } = productionKernel(R, pal);
    const made = [];
    const up = (a) => {
        const f = R.field(n, n, 1, a instanceof Float32Array ? a : new Float32Array(a));
        made.push(f);
        return f;
    };
    const samp = {};
    for (let s = 0; s < Math.max(1, (names.length + 3) >> 2); s++) {
        const four = names.slice(4 * s, 4 * s + 4);
        const chans = {};
        for (const nm of four) {
            const v = m[nm];
            if (v === undefined || v === null) continue;              // palettes.evaluate reads a missing map as 0
            if (v.length !== n * n) throw new ValueError(`palette bake: bare reads ${nm}, ${v.length} texels on a level of ${n} x ${n} cells`);
            chans[nm] = up(v);
        }
        const packed = R.pack(chans, four.concat(Array(4 - four.length).fill(null)), [n, n]);
        made.push(packed);
        samp[`maps${s}`] = packed;
    }
    samp.freshT = m.fresh ? up(m.fresh) : (() => { const z = R.field(n, n, 1); made.push(z); return z; })();
    const prod = R.field(n, n, 1);
    // (fresh * bare + BACKGROUND) * cell ** 2: cell ** 2 in doubles, as numpy's float(lv.cell) ** 2
    R.run(kernel, samp, { outP: prod }, { uCell2: f32(cell * cell), uBg: f32(BACKGROUND) });
    const zs = m.strata ? up(m.strata) : up(sd.terrain.fields(i).h);
    const c = rockColour(R, pal, zs, lv);
    for (const f of made) f.destroy();
    return { prod, c };
}

/** [rgba32f field (n x n): down_colour rgb, down_share] per level (module doc), or null when, with a deadline
 * (performance.now() seconds), the next level at the mean time of the levels routed so far would pass it. */
export async function provenance(sd, pal, { R, log = console.log, deadline = null } = {}) {
    const Pr = prims(R);
    const m = B.MARGIN;
    const out = [], keep = new Map(), spent = [];
    const p = Number(sd.options.flow_p ?? 1.0);
    const io = B.kernel(R, 'palette/provenance_io');
    const route = B.kernel(R, 'route_colour');
    const release = () => {
        for (const f of keep.values()) f.destroy();
        for (const f of out) f.destroy();
    };
    for (let i = 0; i < sd.levels.length; i++) {
        const lv = sd.levels[i];
        const t0 = performance.now() / 1000;
        if (deadline !== null && t0 + (spent.length ? spent.reduce((a, b) => a + b, 0) / spent.length : 0.0) > deadline) {
            release();
            return null;
        }
        const n = lv.n, cell = Number(lv.cell), N_ = n + 2 * m;
        const b = sd._baked[i].get('_fill');
        if (!b) throw new KeyError(`level ${i}: the bake has no routing surface (_fill): bake again with this code`);
        const W = R.field(N_, N_, 1, b.data instanceof Float32Array ? b.data : new Float32Array(b.data));
        const { prod, c } = await production(R, sd, pal, i);
        const par = lv.parent !== null && lv.parent !== undefined ? keep.get(lv.parent) ?? null : null;
        let src, pin, q0;
        if (par === null) {
            const P_ = M.padLevel(prod, m, cell, { fill: 'edge' });
            const chans = {};
            for (let k = 0; k < 3; k++) {
                const one = R.field(n, n, 1);
                R.run(B.kernel(R, 'pick'), { a: c }, { outF: one }, { uCh: k, uOffset: [0, 0] });
                chans[`c${k}`] = M.padLevel(one, m, cell, { fill: 'edge' });
                one.destroy();
            }
            const cp = R.pack(chans, ['c0', 'c1', 'c2', null]);
            for (const f of Object.values(chans)) f.destroy();
            src = R.field(N_, N_, 4);
            R.run(io, { a: P_, b: cp }, { outV: src }, { uMode: 0, uM: 0, uQ0: 0 });
            P_.destroy();
            cp.destroy();
            pin = R.field(N_, N_, 4);
            q0 = R.field(N_, N_, 4);
        } else {
            src = R.field(N_, N_, 4);
            R.run(io, { a: prod, b: c }, { outV: src }, { uMode: 0, uM: m, uQ0: 0 });
            const [i0, j0, mc] = lv.inParent(sd.levels);
            const win = [i0 - m / 2 + m, j0 - m / 2 + m, mc + m];
            const chans = {};
            for (let k = 0; k < 4; k++) {
                const one = R.field(par.h, par.w, 1);
                R.run(B.kernel(R, 'pick'), { a: par }, { outF: one }, { uCh: k, uOffset: [0, 0] });
                const upk = Gd.cropUpsample2(one, win[0], win[1], win[2], 'bilinear');
                one.destroy();
                chans[`q${k}`] = Gd.arith(R, 'scale', upk, null, { amp: 0.5 });
                upk.destroy();
            }
            q0 = R.pack(chans, ['q0', 'q1', 'q2', 'q3']);
            for (const f of Object.values(chans)) f.destroy();
            pin = R.field(N_, N_, 4);
            R.run(io, { a: src, b: src }, { outV: pin }, { uMode: 1, uM: m, uQ0: 0 });          // (the samplers unread)
        }
        prod.destroy();
        c.destroy();
        const ws = R.field(N_, N_, 1);
        const u = { uDx: cell, uP: p, uBound: HYD.BOUND_OPEN };
        R.run('flow_weights', { st: W }, { outW: ws }, u);
        let a = q0, bb = R.field(N_, N_, 4);
        let prev = R.field(N_, N_, 1);
        R.run(B.kernel(R, 'pick'), { a: q0 }, { outF: prev }, { uCh: 0, uOffset: [0, 0] });
        const chg = R.field(N_, N_, 4);
        let it = 0;
        const check = 128;
        while (it < 8 * N_) {
            for (let k = 0; k < check; k++) {
                R.run(route, { st: W, wsumT: ws, qT: a, srcT: src, pinT: pin }, { outQ: bb }, u);
                [a, bb] = [bb, a];
            }
            it += check;
            R.run(io, { a, b: prev }, { outV: chg }, { uMode: 3, uM: 0, uQ0: 0 });
            const change = (await Pr.stats(chg)).max;
            R.run(B.kernel(R, 'pick'), { a }, { outF: prev }, { uCh: 0, uOffset: [0, 0] });
            if (change < 1e-4) break;
        }
        keep.set(i, a);
        const res = R.field(n, n, 4);
        R.run(io, { a, b: a }, { outV: res }, { uMode: 2, uM: m, uQ0: f32(Q0_M2) });
        out.push(res);
        for (const f of [W, ws, src, pin, bb, prev, chg]) f.destroy();
        spent.push(performance.now() / 1000 - t0);
        if (log) log(`[surface] palette bake: provenance on level ${i} in ${spent[spent.length - 1].toFixed(2)} s (${it} passes)`);
        const gp = lv.parent !== null && lv.parent !== undefined ? sd.levels[lv.parent].parent : null;
        if (gp !== null && gp !== undefined && keep.has(gp)) {
            keep.get(gp).destroy();
            keep.delete(gp);
        }
    }
    for (const f of keep.values()) f.destroy();
    return out;
}

/** Delete a bake's palette bakes beyond the `keep` most recently written palettes. */
export async function prune(folder, key, keep = 2) {
    const tags = new Map();
    for (const e of Deno.readDirSync(folder)) {
        const pre = `surface_${key}_pal`;
        if (e.isFile && e.name.startsWith(pre) && e.name.endsWith('_L0.npz')) {
            tags.set(e.name.slice(`surface_${key}_`.length, -'_L0.npz'.length), Deno.statSync(`${folder}/${e.name}`).mtime?.getTime() ?? 0);
        }
    }
    const old = [...tags.keys()].sort((x, y) => tags.get(y) - tags.get(x)).slice(keep);
    for (const tag of old) {
        for (const e of Deno.readDirSync(folder)) {
            if (e.isFile && e.name.startsWith(`surface_${key}_${tag}_L`) && e.name.endsWith('.npz')) {
                try {
                    await Deno.remove(`${folder}/${e.name}`);
                } catch (_e) { /* gone already */ }
            }
        }
    }
}

/** Each level's palette maps (r32f GPU fields per channel: 'far_colour.0'.., 'far_roughness', 'down_colour.0'..,
 * 'down_share') blended to its parent's over the border band (masks.pinBand, B.BAND cells), coarsest first, as the
 * bake pins its own maps: a child's border is then its parent's. In place. */
export function pinLevels(sd, out) {
    for (let i = 0; i < sd.levels.length; i++) {
        const lv = sd.levels[i];
        if (lv.parent === null || lv.parent === undefined) continue;
        const plv = sd.levels[lv.parent];
        const child = new M.Masks(lv.cell, lv.x0, lv.y0, [lv.n, lv.n]);
        const parent = new M.Masks(plv.cell, plv.x0, plv.y0, [plv.n, plv.n]);
        for (const [nm, f] of Object.entries(out[i])) {
            const g = out[lv.parent][nm];
            if (!g) continue;
            child[nm] = f;
            parent[nm] = g;
        }
        M.pinBand(child, parent, B.BAND, []);
    }
}

// rgba fields of a level -> its r32f channel fields by name (the pinning's and the encoding's unit)
function split(R, rgba, names) {
    const out = {};
    names.forEach((nm, k) => {
        if (nm === null) return;
        const one = R.field(rgba.h, rgba.w, 1);
        R.run(B.kernel(R, 'pick'), { a: rgba }, { outF: one }, { uCh: k, uOffset: [0, 0] });
        out[nm] = one;
    });
    return out;
}

/** The level's palette maps as the cache keeps them: Map name -> float16 npArray ((n, n, 3) colours), one readback. */
async function stored(R, chans, n) {
    const plan = [];
    for (const base of NAMES) {
        const three = [0, 1, 2].every((c) => chans[`${base}.${c}`]);
        let src = null, own = null, shape;
        if (three) {
            const rgba = R.pack({ r: chans[`${base}.0`], g: chans[`${base}.1`], b: chans[`${base}.2`] }, ['r', 'g', 'b', null]);
            own = R.field(n, 3 * n, 1);
            R.run(B.kernel(R, 'atlas/interleave'), { src: rgba }, { outF: own }, {});
            rgba.destroy();
            src = own;
            shape = [n, n, 3];
        } else if (chans[base]) {
            src = chans[base];
            shape = [n, n];
        } else {
            continue;
        }
        const words = R.field(src.h, Math.ceil(src.w / 2), 1, null, 'u32');
        R.run(B.kernel(R, 'encode'), { src }, { outW: words }, { uKind: 4, uScale: 1.0, uRef: 0.0 });
        if (own) own.destroy();
        plan.push({ base, words, w: src.w, h: src.h, shape });
    }
    const got = await R.readAll(plan.map((x) => x.words));
    const map = new Map();
    plan.forEach((x, k) => {
        x.words.destroy();
        const halves = new Uint16Array(got[k].buffer, got[k].byteOffset, got[k].byteLength / 2);
        const stride = 2 * Math.ceil(x.w / 2);
        let data;
        if (stride === x.w) {
            data = halves.slice(0, x.h * x.w);
        } else {
            data = new Uint16Array(x.h * x.w);
            for (let j = 0; j < x.h; j++) data.set(halves.subarray(j * stride, j * stride + x.w), j * x.w);
        }
        map.set(x.base, { dtype: '<f2', shape: x.shape, data: new Float16Array(data.buffer) });
    });
    return map;
}

/** A level's cached palette maps (an npz) as Map name -> npArray, the arrays as stored. */
async function loadLevel(path) {
    const z = await Io.readNpz(path);
    return new Map(Object.entries(z));
}

/** A stored float16 map back on the GPU as r32f channel fields by name ('<name>.<c>' for a colour): its halves
 * copied row by row into words and decoded there (kernels/port/decode.wgsl), a colour de-interleaved there. */
function fieldsOf(R, nm, a) {
    const h = a.shape[0], w = a.shape.length === 3 ? a.shape[1] * a.shape[2] : a.shape[1];
    const stride = Math.ceil(w / 2);
    const words = new Uint32Array(h * stride);
    const halves = new Uint16Array(words.buffer);
    const src = new Uint16Array(a.data.buffer, a.data.byteOffset, h * w);
    if (stride * 2 === w) halves.set(src);
    else for (let j = 0; j < h; j++) halves.set(src.subarray(j * w, (j + 1) * w), j * 2 * stride);
    const wf = R.field(h, stride, 1, words, 'u32');
    const flat = R.field(h, w, 1);
    R.run(B.kernel(R, 'decode'), { src: wf }, { outF: flat }, { uKind: 1, uSquare: 0, uA: 1.0, uB: 0.0 });
    wf.destroy();
    if (a.shape.length !== 3) return { [nm]: flat };
    const rgba = R.field(h, a.shape[1], 4);
    R.run(B.kernel(R, 'atlas/deinterleave'), { src: flat }, { outR: rgba }, {});
    flat.destroy();
    const out = split(R, rgba, [`${nm}.0`, `${nm}.1`, `${nm}.2`, null]);
    rgba.destroy();
    return out;
}

/** The palette bake of a SurfaceData: per level a Map { far_colour, far_roughness[, down_colour, down_share] },
 * cached as <cache>/surface_<key>_pal<hash>_L<i>.npz (float16). C first, then P by pMode: true always, false never,
 * 'budget' while the palette bake stays within budgetS (each level's routing projected from the levels done). Past
 * the budget P is deferred: the levels it routed are dropped, and the material's sediment layers mix toward the
 * debris' own column colour (SURFACING_DESIGN.md 2.3). A cached bake without P gains it with pMode true.
 * sd.info.palette_bake records what was made, cached or deferred and the seconds. */
export async function bake(sd, pal, { cache = null, log = console.log, pMode = 'budget', budgetS = BUDGET_S, R = null } = {}) {
    R = R ?? await (await import('../core/gpu.js')).init();
    const tag = 'pal' + paletteHash(pal);
    sd._colourTag = tag;
    const n = sd.levels.length;
    const files = cache ? Array.from({ length: n }, (_x, i) => `${cache}/surface_${sd.key}_${tag}_L${i}.npz`) : null;
    const t0 = performance.now() / 1000;
    const rec = { tag };
    let loaded = null;
    const exists = (pth) => {
        try {
            Deno.statSync(pth);
            return true;
        } catch (_e) {
            return false;
        }
    };
    if (files && files.every(exists)) {
        loaded = [];
        for (const pth of files) loaded.push(await loadLevel(pth));
        rec.C = loaded[0].has('far_colour') ? 'cached' : 'absent';
        rec.P = loaded[0].has('down_colour') ? 'cached' : 'deferred';
        if (pMode !== true || loaded[0].has('down_colour')) {
            rec.seconds = +(performance.now() / 1000 - t0).toFixed(3);
            sd.info.palette_bake = rec;
            return loaded;
        }
    }
    // the levels' maps as r32f channel fields by name, pinned and encoded at the end
    const chans = Array.from({ length: n }, () => ({}));
    if (loaded === null) {
        let FC = null;
        try {
            FC = await import('./far_colour.js');
        } catch (e) {
            if (!/Module not found|Cannot find module|ERR_MODULE_NOT_FOUND/.test(String(e?.message ?? e))) throw e;
        }
        if (FC !== null) {
            const t1 = performance.now() / 1000;
            const C = await FC.bake(sd, pal, { R, log });
            C.forEach((rgba, i) => {
                Object.assign(chans[i], split(R, rgba, ['far_colour.0', 'far_colour.1', 'far_colour.2', 'far_roughness']));
                rgba.destroy();
            });
            rec.C = 'made';
            rec.C_seconds = +(performance.now() / 1000 - t1).toFixed(2);
        } else {
            rec.C = 'absent';
        }
    } else {
        // a cached C (without P) gains P: its maps back on the GPU as they are stored (decoded from float16)
        loaded.forEach((map, i) => {
            for (const [nm, a] of map) Object.assign(chans[i], fieldsOf(R, nm, a));
        });
    }
    if (pMode) {
        const t1 = performance.now() / 1000;
        const prov = await provenance(sd, pal, { R, log, deadline: pMode === true ? null : t0 + Number(budgetS) });
        if (prov === null) {
            rec.P = 'deferred';
            if (log) log(`[surface] palette bake ${tag}: provenance deferred (past the ${budgetS} s budget)`);
        } else {
            prov.forEach((rgba, i) => {
                Object.assign(chans[i], split(R, rgba, ['down_colour.0', 'down_colour.1', 'down_colour.2', 'down_share']));
                rgba.destroy();
            });
            rec.P = 'made';
            rec.P_seconds = +(performance.now() / 1000 - t1).toFixed(2);
        }
    } else {
        rec.P = 'skipped';
    }
    pinLevels(sd, chans);
    const out = [];
    for (let i = 0; i < n; i++) {
        out.push(await stored(R, chans[i], sd.levels[i].n));
        for (const f of Object.values(chans[i])) f.destroy();
    }
    if (files) {
        await Deno.mkdir(cache, { recursive: true });
        for (let i = 0; i < n; i++) {
            const tmp = files[i] + '.tmp.npz';
            await Io.writeNpz(tmp, [...out[i].entries()]);
            await Deno.rename(tmp, files[i]);
        }
        await prune(cache, sd.key, 2);
    }
    rec.seconds = +(performance.now() / 1000 - t0).toFixed(3);
    sd.info.palette_bake = rec;
    if (log) log(`[surface] palette bake ${tag}: ${rec.seconds.toFixed(2)} s (C ${rec.C}, P ${rec.P})`);
    return out;
}

export { paletteHash as palette_hash, rockLayer as rock_layer, pinLevels as pin_levels };
