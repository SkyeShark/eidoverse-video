// The ring mesh against Blender's (PORT_PLAN.md 7.3, 7.4, 8.2 P4, C3): build/mesh.js on the levels of every fixture
// case mesh_expected.py made with Blender's own build/mesh.py, compared with what Blender built from the same input.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/mesh_api/mesh_test.mjs [case ...]
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front). Per case:
//   specs, layout       the ring specs and layout() JSON-equal
//   lattices            every ring's lattice lines, vertex numbers (NONE where Blender has -1) and own count equal
//   topology            the index buffer equal to Blender's triangles, index for index
//   x and z             bit-equal to Blender's x and -y (the lattice lines in JavaScript doubles)
//   heights             every lattice point within 14 ulp of its corner's largest tap (a seam point: of its parent
//                       points' bound plus 4 ulp of their height); the worst in ulp reported
//   normals             every terrain vertex within 1e-5 rad of vertex_normals()
//   groups              one per ring and the skirt's, Blender's triangles per ring, material 1 on context rings;
//                       the geometry carries position, normal and uv only (no mask attributes)
//   heightAt            at Blender's 2,000 points: equal to height_at to 1e-12 relative where the triangle's three
//                       vertices are bit-equal, within their bound elsewhere; the same rings; the transcription on
//                       Blender's own heights equal at every point; points outside read the edge as Blender's
//   normalAt            flat and smooth at the points against Blender's (1e-5 rad)
//   manifold            every terrain edge used by two triangles except the outer border's (open, Blender's count,
//                       all on the border), none by three; with the skirt only its bottom edges are open

import * as THREE from 'npm:three@0.184.0';
import * as G from '../../core/gpu.js';
import { RingMesh, buildRings, gpuNormals, integerWindows, makeGeometry, NONE, asWindow, searchsorted } from '../../build/mesh.js';
import { readNpz } from '../../core/io.js';
import { prims } from '../../core/prims.js';
import { Level } from '../../core/levels.js';
import * as C from './_common.mjs';

const args = Deno.args.filter((a) => !a.startsWith('--'));
const cases = C.fixtureCases(args.length ? args : null);
if (!cases) Deno.exit(0);
const R = await G.init();
const T = new C.Checks('mesh and API: the ring mesh against build/mesh.py');
T.extra.cases = {};

async function levelsOf(name, man) {
    if (man.kind === 'synthetic') {
        const levels = man.windows.map(([x0, y0, cell, n]) => ({ x0, y0, cell, n }));
        return { levels, heights: levels.map((_, k) => C.arr(name, man, `h_${k}`)) };
    }
    const base = C.blenderPath(man.save);
    const levels = man.plan.map((d) => Level.fromDict(d));
    const want = levels.map((_, i) => `L${i}__f__h`);
    const z = await readNpz(base + '.npz', { names: want });
    return { levels, heights: want.map((k) => z[k].data) };
}

// the height bound of every lattice point (see the header): per ring a Float64Array, ny x nx
function heightBounds(rm, iwins, heights) {
    const out = [];
    rm.rings.forEach((r, k) => {
        const b = new Float64Array(r.nx * r.ny);
        const s = r.spec, w = iwins[s.level], h = heights[s.level], n = w.n;
        const P = k ? rm.rings[k - 1] : null, PB = k ? out[k - 1] : null;
        for (let j = 0; j < r.ny; j++) {
            for (let i = 0; i < r.nx; i++) {
                const border = P && (j === 0 || j === r.ny - 1 || i === 0 || i === r.nx - 1);
                if (border) {
                    // the parent points the seam rule reads (columns win at the corners, as _seam_override)
                    let pts;
                    if (i === 0 || i === r.nx - 1) {
                        const pc = searchsorted(P.xs, r.xs[i]);
                        const m = searchsorted(P.ys, r.ys[j], 'right') - 1;
                        pts = [[m, pc], [Math.min(m + 1, P.ny - 1), pc]];
                        if (P.ys[m] === r.ys[j]) pts = [[m, pc]];
                    } else {
                        const pr = searchsorted(P.ys, r.ys[j]);
                        const m = searchsorted(P.xs, r.xs[i], 'right') - 1;
                        pts = [[pr, m], [pr, Math.min(m + 1, P.nx - 1)]];
                        if (P.xs[m] === r.xs[i]) pts = [[pr, m]];
                    }
                    let bound = 0, zmax = 0;
                    for (const [pj, pi] of pts) {
                        bound = Math.max(bound, PB[pj * P.nx + pi]);
                        zmax = Math.max(zmax, Math.abs(P.Zb[pj * P.nx + pi]));
                    }
                    b[j * r.nx + i] = pts.length === 1 ? bound : bound + 4 * C.ulp32(zmax);
                } else {
                    const mx = (r.xs[i] - w.x0) / w.ci, my = (r.ys[j] - w.y0) / w.ci;
                    let H = 0;
                    for (let q = 0; q < 4; q++) {
                        const jj = Math.min(Math.max(my - 2 + q, 0), n - 1);
                        for (let p = 0; p < 4; p++) {
                            const ii = Math.min(Math.max(mx - 2 + p, 0), n - 1);
                            H = Math.max(H, Math.abs(h[jj * n + ii]));
                        }
                    }
                    b[j * r.nx + i] = 14 * C.ulp32(H);
                }
            }
        }
        out.push(b);
    });
    return out;
}

async function checkCase(name) {
    const man = C.manifest(name);
    const rec = {};
    T.extra.cases[name] = rec;
    const { levels, heights } = await levelsOf(name, man);
    const t0 = performance.now();
    const rm = await buildRings(R, levels, heights, { cores: man.cores, meshRes: man.mesh_res });
    rec.build_s = +((performance.now() - t0) / 1000).toFixed(3);
    rec.triangles = rm.triangleCount;
    rec.vertices = rm.vertexCount;
    rec.blender_build_s = man.seconds_build;
    const tag = (s) => `${name}: ${s}`;

    // specs, layout
    T.ok(tag('ring specs equal'), C.sameJson(rm.specs.map((s) => s.asList()), man.specs),
        C.jsonDiff(rm.specs.map((s) => s.asList()), man.specs) ?? `${rm.specs.length} rings`);
    T.ok(tag('layout() JSON-equal'), C.sameJson(JSON.parse(JSON.stringify(rm.layout())), man.layout),
        C.jsonDiff(JSON.parse(JSON.stringify(rm.layout())), man.layout) ?? '');

    // lattices
    let latticeOk = true, latticeWhy = '';
    rm.rings.forEach((r, k) => {
        const bx = C.arr(name, man, `xs_${k}`), by = C.arr(name, man, `ys_${k}`), bi = C.arr(name, man, `idx_${k}`);
        const mr = man.rings[k];
        if (r.nx !== mr.nx || r.ny !== mr.ny || r.v0 !== mr.v0 || r.own !== mr.own) {
            latticeOk = false;
            latticeWhy ||= `ring ${k}: nx ${r.nx}/${mr.nx} ny ${r.ny}/${mr.ny} v0 ${r.v0}/${mr.v0} own ${r.own}/${mr.own}`;
            return;
        }
        for (let i = 0; i < r.nx; i++) if (r.xs[i] !== bx[i]) { latticeOk = false; latticeWhy ||= `ring ${k} xs[${i}]`; break; }
        for (let j = 0; j < r.ny; j++) if (r.ys[j] !== by[j]) { latticeOk = false; latticeWhy ||= `ring ${k} ys[${j}]`; break; }
        for (let q = 0; q < bi.length; q++) {
            const want = bi[q] < 0 ? NONE : bi[q];
            if (r.idx[q] !== want) { latticeOk = false; latticeWhy ||= `ring ${k} idx[${q}] ${r.idx[q]} vs ${bi[q]}`; break; }
        }
        if (!C.sameJson(r.holeLines ?? null, mr.hole_lines)) { latticeOk = false; latticeWhy ||= `ring ${k} hole lines`; }
    });
    T.ok(tag('every ring\'s lattice lines and vertex numbers equal'), latticeOk, latticeWhy || `${rm.rings.length} rings`);

    // topology
    const bt = C.arr(name, man, 'tris');
    let triOk = bt.length === rm.index.length, firstBad = -1;
    for (let q = 0; triOk && q < bt.length; q++) if (rm.index[q] !== bt[q]) { triOk = false; firstBad = q; }
    T.ok(tag('index buffer equal to Blender\'s triangles'), triOk,
        triOk ? `${bt.length / 3} triangles` : `length ${rm.index.length / 3} vs ${bt.length / 3}; first difference at ${firstBad}`);

    // positions
    const bv = C.arr(name, man, 'verts');
    const V = bv.length / 3, nv = man.skirt ? man.skirt.first_vertex : V;
    let xzOk = rm.positions.length === bv.length, xzBad = '';
    for (let v = 0; xzOk && v < V; v++) {
        if (rm.positions[3 * v] !== bv[3 * v] || rm.positions[3 * v + 2] !== -bv[3 * v + 1]) {
            xzOk = false;
            xzBad = `vertex ${v}: (${rm.positions[3 * v]}, ${-rm.positions[3 * v + 2]}) vs (${bv[3 * v]}, ${bv[3 * v + 1]})`;
        }
    }
    T.ok(tag('x and z bit-equal to Blender\'s x and -y'), xzOk, xzOk ? `${V} vertices` : xzBad);

    // heights: every lattice point against its bound
    const { iwins } = integerWindows(levels.map(asWindow));
    rm.rings.forEach((r, k) => { r.Zb = C.arr(name, man, `Z_${k}`); });
    const bounds = heightBounds(rm, iwins, heights);
    let worstRatio = 0, worstUlpCR = 0, worstUlpSeam = 0, differ = 0, points = 0, where = '';
    rm.rings.forEach((r, k) => {
        for (let j = 0; j < r.ny; j++) {
            for (let i = 0; i < r.nx; i++) {
                const q = j * r.nx + i;
                const d = Math.abs(r.Z[q] - r.Zb[q]);
                points++;
                if (d) differ++;
                const ratio = d / bounds[k][q];
                if (ratio > worstRatio) {
                    worstRatio = ratio;
                    where = `ring ${k} (${i}, ${j}): ${r.Z[q]} vs ${r.Zb[q]}, bound ${bounds[k][q]}`;
                }
                const border = k && (j === 0 || j === r.ny - 1 || i === 0 || i === r.nx - 1);
                const u = d / (bounds[k][q] / 14);
                if (border) worstUlpSeam = Math.max(worstUlpSeam, d / C.ulp32(r.Zb[q] || 1));
                else worstUlpCR = Math.max(worstUlpCR, u);
            }
        }
    });
    rec.heights = { lattice_points: points, differ, worst_over_bound: worstRatio, worst_ulp_of_largest_tap: worstUlpCR,
        worst_seam_ulp_of_z: worstUlpSeam };
    T.ok(tag('heights within 14 ulp of each corner\'s largest tap (seams within their parents\' bound)'), worstRatio <= 1,
        `${differ} of ${points} lattice points differ from Blender's float64-then-float32; worst ${worstUlpCR.toFixed(2)} ulp of ` +
        `the largest tap (bound 14), seams worst ${worstUlpSeam.toFixed(2)} ulp of z; worst / bound ${worstRatio.toFixed(3)}` +
        (worstRatio > 1 ? `; at ${where}` : ''));

    // normals. (a) The kernel itself: build/mesh.js gpuNormals on Blender's own vertices and triangles, against
    // vertex_normals() of the same vertices. (b) The port's normals on its own vertices against Blender's: their
    // heights differ within the bound above, and a height difference dz over a triangle of horizontal extent sigma
    // (its 2 x 2 edge matrix's smallest singular value) turns its face normal by up to 2 sqrt(2) dz / sigma, which
    // at 2,000 m (ulp 1.2e-4 m) over a 0.5 m cell is 2.4e-4 rad per ulp: so (b) is graded by that bound, per vertex
    const bn = C.arr(name, man, 'vn');
    const kernelWorst = await kernelOnBlender(bn, bv, bt, nv, man.terrain_triangles);
    T.ok(tag('the normals kernel on Blender\'s vertices within 1e-5 rad of vertex_normals() (skirt excluded)'),
        kernelWorst.worst <= 1e-5, `worst ${kernelWorst.worst.toExponential(3)} rad at vertex ${kernelWorst.at}`);
    const vb = vertexBounds(rm, bounds, nv, man.terrain_triangles);
    let worstAng = 0, worstRatio2 = 0, at = -1;
    for (let v = 0; v < nv; v++) {
        const a = C.angle(rm.vertexNormal(v), [bn[3 * v], bn[3 * v + 1], bn[3 * v + 2]]);
        if (!(a <= worstAng)) { worstAng = a; at = v; }
        worstRatio2 = Math.max(worstRatio2, a / vb.normal[v]);
    }
    rec.normals = { kernel_on_blender_vertices_worst_rad: kernelWorst.worst, port_vs_blender_worst_rad: worstAng,
        port_vs_blender_worst_over_bound: worstRatio2 };
    T.ok(tag('vertex normals against Blender\'s within the turn their heights\' bound allows (+1e-5 rad)'), worstRatio2 <= 1,
        `worst ${worstAng.toExponential(3)} rad at vertex ${at}; worst / bound ${worstRatio2.toFixed(3)}`);

    // groups and attributes
    const g = makeGeometry(THREE, rm);
    const attrs = Object.keys(g.attributes).sort();
    const roles = levels.map((l) => l.role ?? null);
    let groupOk = g.groups.length === rm.rings.length + (man.skirt ? 1 : 0), groupWhy = `${g.groups.length} groups`;
    rm.rings.forEach((r, k) => {
        const gr = g.groups[k];
        const mi = roles[r.spec.level] === 'context' ? 1 : 0;
        if (!gr || gr.count !== 3 * man.ring_triangles[k] || gr.materialIndex !== mi) {
            groupOk = false;
            groupWhy = `ring ${k}: ${gr?.count / 3} triangles (Blender ${man.ring_triangles[k]}), material ${gr?.materialIndex} (want ${mi})`;
        }
    });
    if (man.skirt) {
        const sg = g.groups[g.groups.length - 1];
        if (sg.start !== 3 * man.terrain_triangles || sg.count !== 3 * (man.triangles - man.terrain_triangles)) {
            groupOk = false;
            groupWhy = `the skirt's group ${sg.start}+${sg.count}`;
        }
    }
    T.ok(tag('one geometry group per ring (Blender\'s triangles per ring, context rings material 1) and the skirt\'s'),
        groupOk, groupWhy);
    T.ok(tag('no mask attributes: position, normal and uv only'), C.sameJson(attrs, ['normal', 'position', 'uv']), attrs.join(', '));
    g.dispose();

    // heightAt
    const px = C.arr(name, man, 'px'), py = C.arr(name, man, 'py'), hz = C.arr(name, man, 'hz');
    const ringOf = C.arr(name, man, 'ring_of');
    let ringsOk = true, exactN = 0, exactWorst = 0, boundN = 0, boundWorst = 0, fans = 0;
    for (let q = 0; q < px.length; q++) {
        const [z, tr] = rm._height(px[q], py[q]);
        if (tr.ring !== ringOf[q]) ringsOk = false;
        const r = rm.rings[tr.ring];
        let pts;
        if (tr.fan === null) {
            pts = tr.lower ? [[tr.i, tr.j], [tr.i + 1, tr.j], [tr.i + 1, tr.j + 1]] : [[tr.i, tr.j], [tr.i + 1, tr.j + 1], [tr.i, tr.j + 1]];
            pts = pts.map(([i, j]) => [tr.ring, i, j]);
        } else {
            fans++;
            pts = null;                                      // a fan point: its child line points (below)
        }
        let same = pts !== null, bound = 0;
        if (pts) {
            for (const [k, i, j] of pts) {
                const rr = rm.rings[k], qq = j * rr.nx + i;
                if (rr.Z[qq] !== rr.Zb[qq]) same = false;
                bound = Math.max(bound, bounds[k][qq]);
            }
        } else {
            same = false;
            // the apex and the child's border: the largest bound on the hole's rim of the ring and on the child's border
            const rr = rm.rings[tr.ring], cr = rm.rings[tr.ring + 1];
            const [jb, jt, il, ir] = rr.holeLines;
            for (let j = jb - 1; j <= jt + 1; j++) for (let i = il - 1; i <= ir + 1; i++) {
                if (j > jb && j < jt && i > il && i < ir) continue;
                bound = Math.max(bound, bounds[tr.ring][j * rr.nx + i]);
            }
            for (let j = 0; j < cr.ny; j++) for (const i of [0, cr.nx - 1]) bound = Math.max(bound, bounds[tr.ring + 1][j * cr.nx + i]);
            for (let i = 0; i < cr.nx; i++) for (const j of [0, cr.ny - 1]) bound = Math.max(bound, bounds[tr.ring + 1][j * cr.nx + i]);
        }
        const d = Math.abs(z - hz[q]);
        if (same) {
            exactN++;
            exactWorst = Math.max(exactWorst, d / Math.max(Math.abs(hz[q]), 1));
        } else {
            boundN++;
            boundWorst = Math.max(boundWorst, d / bound);
        }
    }
    rec.height_at = { points: px.length, bit_equal_triangles: exactN, worst_relative_there: exactWorst,
        other: boundN, worst_over_bound_there: boundWorst, fan_points: fans };
    T.ok(tag('heightAt finds Blender\'s ring at every point'), ringsOk, '');
    T.ok(tag(`heightAt equal to height_at to 1e-12 relative on bit-equal triangles, within the bound elsewhere`),
        exactWorst <= 1e-12 && boundWorst <= 1,
        `${exactN} points on bit-equal triangles, worst ${exactWorst.toExponential(2)} relative; ${boundN} others ` +
        `(${fans} in fans), worst / bound ${boundWorst.toFixed(3)}`);

    // the transcription itself, on Blender's own heights and normals
    const brm = blenderMesh(name, man, rm);
    let trWorst = 0;
    for (let q = 0; q < px.length; q++) trWorst = Math.max(trWorst, Math.abs(brm.heightAt(px[q], py[q]) - hz[q]) / Math.max(Math.abs(hz[q]), 1));
    const ox = C.arr(name, man, 'outside_xy'), oz = C.arr(name, man, 'outside_z');
    let outWorst = 0;
    for (let q = 0; q < oz.length; q++) outWorst = Math.max(outWorst, Math.abs(brm.heightAt(ox[2 * q], ox[2 * q + 1]) - oz[q]));
    T.ok(tag('heightAt on Blender\'s own heights equals height_at at every point (the transcription)'), trWorst <= 1e-12 && outWorst === 0,
        `worst ${trWorst.toExponential(2)} relative over ${px.length} points; outside the window ${outWorst}`);

    // normalAt: the transcription on Blender's data to 1e-12; the port's within the bound of its triangle (flat) or
    // of its corners' vertex normals (smooth), as above
    const nfl = C.arr(name, man, 'n_flat'), nsm = C.arr(name, man, 'n_smooth');
    let flatPort = 0, flatTr = 0, smPort = 0, smTr = 0, flatRatio = 0, smRatio = 0;
    for (let q = 0; q < px.length; q++) {
        const fb = [nfl[3 * q], nfl[3 * q + 1], nfl[3 * q + 2]], sb = [nsm[3 * q], nsm[3 * q + 1], nsm[3 * q + 2]];
        const [, tr] = rm._height(px[q], py[q]);
        const r = rm.rings[tr.ring], nxr = r.nx;
        const corners = tr.lower ? [[tr.i, tr.j], [tr.i + 1, tr.j], [tr.i + 1, tr.j + 1]]
            : [[tr.i, tr.j], [tr.i + 1, tr.j + 1], [tr.i, tr.j + 1]];
        let dz = 0, nb = 0;
        for (const [i, j] of corners) {
            dz = Math.max(dz, bounds[tr.ring][j * nxr + i]);
            nb = Math.max(nb, vb.normal[r.idx[j * nxr + i]]);
        }
        const sig = sigmaMin(corners.map(([i, j]) => [r.xm[i], r.ym[j]]));
        const fbound = 2 * Math.SQRT2 * dz / sig + 1e-5;
        const fa = C.angle(rm.normalAt(px[q], py[q], false), fb), sa = C.angle(rm.normalAt(px[q], py[q], true), sb);
        flatPort = Math.max(flatPort, fa);
        smPort = Math.max(smPort, sa);
        flatRatio = Math.max(flatRatio, fa / fbound);
        smRatio = Math.max(smRatio, sa / nb);
        flatTr = Math.max(flatTr, C.angle(brm.normalAt(px[q], py[q], false), fb));
        smTr = Math.max(smTr, C.angle(brm.normalAt(px[q], py[q], true), sb));
    }
    rec.normal_at = { flat_rad: flatPort, flat_over_bound: flatRatio, flat_transcription_rad: flatTr, smooth_rad: smPort,
        smooth_over_bound: smRatio, smooth_transcription_rad: smTr };
    T.ok(tag('normalAt: the transcription on Blender\'s data within 1e-12 rad (flat and smooth); the port within its bound'),
        flatTr <= 1e-12 && smTr <= 1e-12 && flatRatio <= 1 && smRatio <= 1,
        `transcription flat ${flatTr.toExponential(2)}, smooth ${smTr.toExponential(2)} rad; the port flat ` +
        `${flatPort.toExponential(2)} rad (worst / bound ${flatRatio.toFixed(3)}), smooth ${smPort.toExponential(2)} rad ` +
        `(worst / bound ${smRatio.toFixed(3)})`);

    // the edge-manifold check
    const mf = manifold(rm, man);
    rec.manifold = mf;
    T.ok(tag('edge-manifold: open edges only on the outer border (Blender\'s count), none shared by 3; the skirt hangs from ' +
        'copies of the border at the border\'s very positions'),
        mf.open === man.open_edges_expected && mf.openOnBorder && mf.over === 0 && mf.skirtOver === 0 &&
        (!man.skirt || (mf.skirtOpen === 3 * mf.perimeter && mf.skirtTopAtBorder)),
        `terrain: ${mf.open} open (want ${man.open_edges_expected}), on the border ${mf.openOnBorder}, ${mf.over} shared by 3+; ` +
        `with the skirt ${mf.skirtOpen} open (the border, the skirt's top and its bottom: ${mf.perimeter} each), ` +
        `${mf.skirtOver} shared by 3+, its top copies at the border vertices' positions ${mf.skirtTopAtBorder}`);
    for (const r of rm.rings) delete r.Zb;
}

// the smallest singular value of a triangle's horizontal edge matrix [p1 - p0; p2 - p0] (metres)
function sigmaMin(p) {
    const a = p[1][0] - p[0][0], b = p[1][1] - p[0][1], c = p[2][0] - p[0][0], d = p[2][1] - p[0][1];
    const S = a * a + b * b + c * c + d * d, det = Math.abs(a * d - b * c);
    const smax = Math.sqrt((S + Math.sqrt(Math.max(S * S - 4 * det * det, 0))) / 2);
    return det / smax;
}

// Per terrain vertex: its height bound (the lattice point it is) and the bound of its normal's turn: 1.5 x the
// largest 2 sqrt(2) dz / sigma over its triangles (the weights and the normalisation move it a little more than its
// faces), + 1e-5 rad
function vertexBounds(rm, bounds, nv, nT) {
    const hb = new Float64Array(nv);
    rm.rings.forEach((r, k) => {
        for (let q = 0; q < r.idx.length; q++) {
            const v = r.idx[q];
            if (v !== NONE && v >= r.v0 && v < nv) hb[v] = bounds[k][q];
        }
    });
    const nb = new Float64Array(nv);
    const P = rm.positions, I = rm.index;
    for (let t = 0; t < nT; t++) {
        const a = I[3 * t], b = I[3 * t + 1], c = I[3 * t + 2];
        const sig = sigmaMin([[P[3 * a], -P[3 * a + 2]], [P[3 * b], -P[3 * b + 2]], [P[3 * c], -P[3 * c + 2]]]);
        const e = 2 * Math.SQRT2 * Math.max(hb[a], hb[b], hb[c]) / sig;
        for (const v of [a, b, c]) if (e > nb[v]) nb[v] = e;
    }
    for (let v = 0; v < nv; v++) nb[v] = 1.5 * nb[v] + 1e-5;
    return { height: hb, normal: nb };
}

// build/mesh.js gpuNormals on Blender's own vertices (three.js axes) and triangles, against Blender's normals
async function kernelOnBlender(bn, bv, bt, nv, nT) {
    const V = bv.length / 3;
    const pos3 = new Float32Array(3 * V);
    for (let v = 0; v < V; v++) {
        pos3[3 * v] = bv[3 * v];
        pos3[3 * v + 1] = bv[3 * v + 2];
        pos3[3 * v + 2] = -bv[3 * v + 1];
    }
    const P = prims(R);
    const pos = P.list(3 * V, 'f32', pos3), tri = P.list(bt.length, 'u32', new Uint32Array(bt.buffer, bt.byteOffset, bt.length));
    const nrm = P.list(3 * V, 'f32');
    const made = gpuNormals(R, pos, tri, nv, nT, nrm);
    const n = await R.readRange(nrm, 0, 3 * nv);
    for (const f of [pos, tri, nrm, ...made]) f.destroy();
    let worst = 0, at = -1;
    for (let v = 0; v < nv; v++) {
        const a = C.angle([n[3 * v], -n[3 * v + 2], n[3 * v + 1]], [bn[3 * v], bn[3 * v + 1], bn[3 * v + 2]]);
        if (!(a <= worst)) { worst = a; at = v; }
    }
    return { worst, at };
}

// A RingMesh on Blender's own lattice data (its heights, lines and vertex numbers, its normals in three.js axes):
// the host methods' transcription checked apart from the GPU's rounding
function blenderMesh(name, man, rm) {
    const rings = rm.rings.map((r, k) => {
        const xm = Float64Array.from(C.arr(name, man, `xm_${k}`)), ym = Float64Array.from(C.arr(name, man, `ym_${k}`));
        const idx = Uint32Array.from(C.arr(name, man, `idx_${k}`), (v) => (v < 0 ? NONE : v));
        return { ...r, xm, ym, Z: C.arr(name, man, `Z_${k}`), idx, _lines: null };
    });
    const bn = C.arr(name, man, 'vn');
    const normals = new Float64Array(bn.length);
    for (let v = 0; v < bn.length / 3; v++) {
        normals[3 * v] = bn[3 * v];
        normals[3 * v + 1] = bn[3 * v + 2];
        normals[3 * v + 2] = -bn[3 * v + 1];
    }
    return new RingMesh({ ...rm, rings, normals });
}

function manifold(rm, man) {
    const idx = rm.index, nT = man.terrain_triangles, nAll = idx.length / 3, V = rm.vertexCount;
    const count = (ntri) => {
        const keys = new Float64Array(3 * ntri);
        for (let t = 0; t < ntri; t++) {
            for (let e = 0; e < 3; e++) {
                const a = idx[3 * t + e], b = idx[3 * t + (e + 1) % 3];
                keys[3 * t + e] = Math.min(a, b) * V + Math.max(a, b);
            }
        }
        keys.sort();
        const ones = [];
        let over = 0;
        for (let q = 0; q < keys.length;) {
            let e = q + 1;
            while (e < keys.length && keys[e] === keys[q]) e++;
            if (e - q === 1) ones.push(keys[q]);
            else if (e - q > 2) over++;
            q = e;
        }
        return { ones, over };
    };
    const t = count(nT);
    const [xmin, ymin, xmax, ymax] = rm.bounds();
    const P = rm.positions;
    const onBorder = (v) => P[3 * v] === xmin || P[3 * v] === xmax || -P[3 * v + 2] === ymin || -P[3 * v + 2] === ymax;
    let on = true;
    for (const k of t.ones) {
        const a = Math.floor(k / V), b = k - a * V;
        if (!onBorder(a) || !onBorder(b)) { on = false; break; }
    }
    const s = count(nAll);
    // the skirt's top copies sit exactly on the border vertices they copy (mesh.py: verts[perim]), so the border
    // is closed where it is drawn, though not by shared edges (the border keeps its smooth shading)
    const m = man.skirt ? (nAll - nT) / 2 : 0;
    let topAt = true;
    if (m) {
        const r0 = rm.rings[0], nx = r0.nx, ny = r0.ny, nv = man.skirt.first_vertex;
        for (let k = 0; k < m && topAt; k++) {
            let i, j;
            if (k < nx) { i = k; j = 0; } else if (k < nx + ny - 1) { i = nx - 1; j = k - nx + 1; } else if (k < 2 * nx + ny - 2) {
                i = nx - 2 - (k - (nx + ny - 1)); j = ny - 1;
            } else { i = 0; j = ny - 2 - (k - (2 * nx + ny - 2)); }
            const v = r0.idx[j * nx + i], c = nv + k;
            for (let a = 0; a < 3; a++) if (P[3 * v + a] !== P[3 * c + a]) topAt = false;
        }
    }
    return { open: t.ones.length, openOnBorder: on, over: t.over, skirtOpen: s.ones.length, skirtOver: s.over,
        perimeter: m, skirtTopAtBorder: topAt };
}

for (const name of cases) {
    try {
        await checkCase(name);
    } catch (e) {
        T.ok(`${name}: ran`, false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 6).join('\n')}`);
    }
}
G.shutdown();
Deno.exit(C.finish(T, 'mesh_test.json'));
