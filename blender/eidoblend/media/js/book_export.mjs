// book_export.mjs — run the hardcover rig (eidoverse/book_core.js, unchanged) in Deno and export it for Blender:
// static topology plus per-frame vertex caches (PC2) for the case, the mull, the stock leaves and the three
// textured window leaves, the textures the rig composes itself (the cover wrap, the mull and inlay cloth), and per
// frame the rig's state and the world matrices of its two coordinate frames (rig.frames: caseFrame, pageFrame).
// Driven by blender/eidoblend/media/book.py; guide: tools-guides/books.md.
//
//   deno run -A --no-config --node-modules-dir=none --cached-only book_export.mjs <job.json>
//
// job = {
//   out: "<dir>",
//   spec: { size: { width, height, thickness? }, pages?, openAt?, spreads: <count>, pdfPages?: <count>,
//           cover: { front?, back?, spine?, color?, wrap? }  (image paths; wrap = a full arc-length wrap),
//           angle?, pageAngle?, boardTh?, lip?, round?, uJoint?, wrapRes? }      (makeBookFromSpec's input)
//     or rig: { boardLen, jointX?, foreX?, halfH, halfT, lip, round, uJoint, pages, openAt, ... } (a measured GLB),
//   frames: [{ f, open?, side?, page?, turn?, wad?, riffle?: { t, start, secondsPerPage, turnFraction } }]  (in order;
//            side 'front' | 'back' is setOpen's second argument: which cover swings)
// }
// The leaves' fold is analytic (book_core's foldNodes): pos(s) = root + sum_k clamp(s - S_k, 0, L_k)(cos H_k, sin H_k),
// offset by the sheet's thickness along the heading read between segment midpoints. The vertex stage did it on the
// GPU; here it is the same sum on the CPU, from the same heading rows. Axes: three (x, y, z) -> Blender (x, -z, y),
// after the rig's own layFlat (the book lies on its back board, thickness up).
import * as THREE from 'npm:three@0.184.0/webgpu';
import * as TSL from 'npm:three@0.184.0/tsl';
import { createCanvas, loadImage } from 'npm:@napi-rs/canvas@0.1.69';

const job = JSON.parse(await Deno.readTextFile(Deno.args[0]));
const OUT = job.out;
await Deno.mkdir(OUT, { recursive: true });

// the rig's canvas2d() takes document.createElement('canvas') first; give it Skia canvases
globalThis.document = { createElement: (tag) => (tag === 'canvas' ? createCanvas(1, 1) : null) };
globalThis.loadCanvasImage = (bytes) => loadImage(bytes);
await import(new URL('../../../../eidoverse/book_core.js', import.meta.url).href);
const BookCore = globalThis.BookCore;
if (!BookCore) throw new Error('book_core.js did not install globalThis.BookCore');

const readBytes = async (p) => (p ? await Deno.readFile(p) : null);
const savePng = async (canvas, name) => { await Deno.writeFile(`${OUT}/${name}`, canvas.toBuffer('image/png')); return name; };
const M = () => new THREE.MeshStandardNodeMaterial();

// ---- the spec (makeBookFromSpec's arithmetic, kept in step with eidoverse/book.js) -----------------------------
let rigSpec, images = {};
const BIND_LEAVES = 502, BIND_PAGES = (BIND_LEAVES - 2) * 2;
if (job.rig) {
    rigSpec = Object.assign({}, job.rig);
} else {
    const input = job.spec;
    const pdfPages = input.pdfPages || 0;
    const nSpreads = input.spreads || 0;
    const size = {
        width: input.size?.width ?? 0.14,
        height: input.size?.height ?? 0.2,
        thickness: input.size?.thickness
            ?? (pdfPages ? Math.min(0.08, Math.max(0.012, 0.008 + Math.min(pdfPages, BIND_PAGES) * 0.00005))
                : nSpreads ? Math.min(0.08, Math.max(0.01, 0.008 + nSpreads * 2 * 0.00005)) : null),
    };
    if (!size.thickness) throw new Error('spec.size.thickness required (no spreads or pdf to estimate it from)');
    const pages = input.pages ?? (pdfPages ? Math.max(12, Math.min(BIND_LEAVES, Math.ceil(pdfPages / 2) + 2))
        : nSpreads ? nSpreads + 1 : 26);
    const halfT = size.thickness / 2;
    const lip = input.lip ?? Math.max(0.003, size.thickness * 0.21);
    const round = input.round ?? Math.max(0.0015, size.thickness * 0.09);
    const uJoint = input.uJoint ?? BookCore.solveWrapLayout({ boardLen: size.width, lip, round, halfT });
    rigSpec = {
        boardLen: size.width, halfH: size.height / 2, halfT, boardTh: input.boardTh ?? 0.0025, lip, round, uJoint,
        liningFit: true, pages, openAt: input.openAt ?? 1, angle: input.angle ?? 180, pageAngle: input.pageAngle ?? 179,
    };
    const cover = input.cover || {};
    if (!cover.wrap && (cover.front || cover.back || cover.spine)) {
        const t = await BookCore.composeWrapTexture(THREE, {
            front: await readBytes(cover.front), back: await readBytes(cover.back), spine: await readBytes(cover.spine),
            color: cover.color || '#8a1420',
        }, uJoint, input.wrapRes || 4096);
        images.wrap = await savePng(t.image, 'wrap.png');
    }
}

const materials = { cloth: M(), lining: M(), edge: M(), spread: M(), trim: M() };
const rig = BookCore.makeBookRig(THREE, rigSpec, materials, { tsl: TSL, log: () => {} });
images.mull = await savePng(rig.mull.material.map.image, 'mull.png');
images.inlay = await savePng(rig.caseMesh.material[3].map.image, 'inlay.png');
const nSpreads = job.spec?.spreads ?? job.spreads ?? 0;
if (nSpreads > 0) {
    const dummy = new THREE.Texture();
    rig.setSpreadSource({ count: nSpreads, get: () => dummy, pages: null, dispose: false });
}
rig.layFlat();

// ---- parts ----------------------------------------------------------------------------------------------------
const P = rig.probe();
const leafBoneS = P.leafBoneS, leafMidS = P.leafMidS, NSEG = P.NSEG, NROW = P.NROW;
const shells = rig.leafField.stockShells, edges = rig.leafField.stockEdges, slots = rig.leafField.windowSlots;
const tpl = shells.geometry.attributes.position.array;         // the leaf template: x = s along the sheet
const tplUv = shells.geometry.attributes.uv.array;
const NT = tpl.length / 3;
const N_LEAF = rig.metrics.N_LEAF;
const rowAttr = []; for (let r = 0; r < NROW; r++) rowAttr.push(shells.geometry.attributes[`leafH${r}`].array);
const visAttr = shells.geometry.attributes.leafV.array;

const groupsOf = (geo, mats) => {                       // per-triangle material index from a geometry's groups
    const idx = geo.index.array, mat = new Int32Array(idx.length / 3);
    if (geo.groups.length) for (const g of geo.groups) for (let t = g.start / 3; t < (g.start + g.count) / 3; t++) mat[t] = g.materialIndex;
    return { tris: Array.from(idx), mat: Array.from(mat), materials: mats };
};
const caseG = rig.caseMesh.geometry;
const parts = {
    case: Object.assign({ n: caseG.attributes.position.count, uv: Array.from(caseG.attributes.uv.array) },
        groupsOf(caseG, ['cloth', 'lining', 'trim', 'inlay'])),
    mull: { n: rig.mull.geometry.attributes.position.count, uv: Array.from(rig.mull.geometry.attributes.uv.array),
        tris: Array.from(rig.mull.geometry.index.array), mat: [], materials: ['mull'] },
};
{   // every stock leaf realised: paper shells (material 0) and the closed walls (material 1)
    const iS = shells.geometry.index.array, iE = edges.geometry.index.array;
    const tris = [], mat = [], uv = [];
    for (let i = 0; i < N_LEAF; i++) {
        const o = i * NT;
        for (let k = 0; k < iS.length; k++) tris.push(iS[k] + o);
        for (let k = 0; k < iS.length / 3; k++) mat.push(0);
        for (let k = 0; k < iE.length; k++) tris.push(iE[k] + o);
        for (let k = 0; k < iE.length / 3; k++) mat.push(1);
        for (let k = 0; k < tplUv.length; k++) uv.push(tplUv[k]);
    }
    parts.leaves = { n: N_LEAF * NT, tris, mat, uv, materials: ['paper', 'edge'] };
}
for (let w = 0; w < 3; w++) {
    parts[`window${w}`] = Object.assign({ n: NT, uv: Array.from(tplUv) },
        groupsOf(slots[w].mesh.geometry, ['recto', 'verso', 'edge']));
}
parts.mull.mat = new Array(parts.mull.tris.length / 3).fill(0);

// ---- the fold, on the CPU ------------------------------------------------------------------------------------
const H = new Float64Array(NSEG), cH = new Float64Array(NSEG), sH = new Float64Array(NSEG);
function foldInto(dst, dstOff, rows, vis, mw) {          // rows(r) -> [x, y, z, w]; writes NT Blender points
    const hv = (k) => { const j = k + 2; return rows(j >> 2)[j & 3]; };
    for (let k = 0; k < NSEG; k++) { H[k] = hv(k); cH[k] = Math.cos(H[k]); sH[k] = Math.sin(H[k]); }
    const r0 = rows(0), rx = r0[0], ry = r0[1];
    const e = mw.elements, v = new THREE.Vector3();
    for (let q = 0; q < NT; q++) {
        const s = tpl[q * 3], py = tpl[q * 3 + 1], pz = tpl[q * 3 + 2];
        let x = rx, y = ry;
        for (let k = 0; k < NSEG; k++) {
            const L = leafBoneS[k + 1] - leafBoneS[k];
            const run = Math.min(L, Math.max(0, s - leafBoneS[k]));
            x += cH[k] * run; y += sH[k] * run;
        }
        let ph = H[0];
        for (let k = 0; k < NSEG - 1; k++) {
            const t = Math.min(1, Math.max(0, (s - leafMidS[k]) / (leafMidS[k + 1] - leafMidS[k])));
            ph += (H[k + 1] - H[k]) * t;
        }
        v.set((x - py * Math.sin(ph)) * vis, (y + py * Math.cos(ph)) * vis, pz * vis).applyMatrix4(mw);
        const o = dstOff + q * 3;
        dst[o] = v.x; dst[o + 1] = -v.z; dst[o + 2] = v.y;
    }
}

// ---- PC2 writers -----------------------------------------------------------------------------------------------
const nF = job.frames.length;
const writers = {};
for (const [name, part] of Object.entries(parts)) {
    const f = await Deno.open(`${OUT}/${name}.pc2`, { write: true, create: true, truncate: true });
    const head = new ArrayBuffer(32), dv = new DataView(head);
    const sig = 'POINTCACHE2\0';
    for (let i = 0; i < 12; i++) dv.setUint8(i, sig.charCodeAt(i));
    dv.setInt32(12, 1, true); dv.setInt32(16, part.n, true);
    dv.setFloat32(20, job.frames[0].f, true); dv.setFloat32(24, 1, true); dv.setInt32(28, nF, true);
    await writeAll(f, new Uint8Array(head));
    writers[name] = { f, buf: new Float32Array(part.n * 3) };
}
async function writeAll(f, u8) { let o = 0; while (o < u8.length) o += await f.write(u8.subarray(o)); }

// ---- the frames ------------------------------------------------------------------------------------------------
const frameInfo = [];
const v = new THREE.Vector3();
// rig.frames (caseFrame, pageFrame): each frame's world matrix taken to Blender's axes on the world side only,
// C · M with C: three (x, y, z) -> Blender (x, -z, y), so the frame keeps its own local axes (book_core.js's
// caseFrame: X along the cross-section, Y out through the front cover, Z the turning axis). Rows, for mathutils.
const TO_B = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
const rowsOf = (obj) => {
    const e = new THREE.Matrix4().multiplyMatrices(TO_B, obj.matrixWorld).elements;
    return [0, 1, 2, 3].map((r) => [0, 1, 2, 3].map((c) => +e[c * 4 + r].toFixed(7)));
};
for (const fr of job.frames) {
    if (fr.open !== undefined && fr.open !== null) rig.setOpen(fr.open, fr.side ?? undefined);   // side: 'front' | 'back'
    if (fr.riffle) rig.riffle(fr.riffle.t, fr.riffle);
    else {
        if (fr.page !== undefined && fr.page !== null) rig.setPage(fr.page);
        if (fr.turn !== undefined && fr.turn !== null) rig.poseTurn(fr.turn, fr.wad ?? 1);
    }
    rig.root.updateMatrixWorld(true);
    let minZ = Infinity;
    {   // the case: CPU skinning (three's own applyBoneTransform)
        const { buf } = writers.case, m = rig.caseMesh;
        for (let i = 0; i < parts.case.n; i++) {
            m.getVertexPosition(i, v); v.applyMatrix4(m.matrixWorld);
            buf[i * 3] = v.x; buf[i * 3 + 1] = -v.z; buf[i * 3 + 2] = v.y;
            if (v.y < minZ) minZ = v.y;
        }
    }
    {   // the mull: its posed ribbon, written in place by the rig
        const { buf } = writers.mull, m = rig.mull, a = m.geometry.attributes.position.array;
        for (let i = 0; i < parts.mull.n; i++) {
            v.set(a[i * 3], a[i * 3 + 1], a[i * 3 + 2]).applyMatrix4(m.matrixWorld);
            buf[i * 3] = v.x; buf[i * 3 + 1] = -v.z; buf[i * 3 + 2] = v.y;
        }
    }
    {   // the stock leaves (a leaf a window slot is drawing has vis 0: it collapses to the page frame's origin)
        const { buf } = writers.leaves, mw = shells.matrixWorld;
        for (let i = 0; i < N_LEAF; i++) {
            foldInto(buf, i * NT * 3, (r) => rowAttr[r].subarray(i * 4, i * 4 + 4), visAttr[i], mw);
        }
        for (let i = 2; i < buf.length; i += 3) if (buf[i] < minZ && buf[i] !== 0) minZ = Math.min(minZ, buf[i]);
    }
    const slotInfo = [];
    for (let w = 0; w < 3; w++) {
        const s = slots[w], { buf } = writers[`window${w}`];
        const rows = (r) => { const q = s.uRows[r].value; return [q.x, q.y, q.z, q.w]; };
        foldInto(buf, 0, rows, s.mesh.visible ? 1 : 0, s.mesh.matrixWorld);
        const kv = rig.page - 1 + w;
        slotInfo.push({ visible: s.mesh.visible, recto: kv, verso: kv + 1 });
    }
    for (const [name, wr] of Object.entries(writers)) await writeAll(wr.f, new Uint8Array(wr.buf.buffer));
    const pr = rig.probe();
    frameInfo.push({ f: fr.f, page: rig.page, open: rig.openAmount, side: pr.openSide, turn: pr.turnPhase ?? null,
        slots: slotInfo, minZ: +minZ.toFixed(6),
        caseFrame: rowsOf(rig.frames.caseFrame), pageFrame: rowsOf(rig.frames.pageFrame) });
}
for (const wr of Object.values(writers)) wr.f.close();

const met = {};
for (const [k, val] of Object.entries(rig.metrics)) met[k] = val;
const sb = rig.seatBox();                     // closed-case bounds in the rig root's space (after layFlat's rotation)
await Deno.writeTextFile(`${OUT}/book.json`, JSON.stringify({
    rig: rigSpec, metrics: met, spreads: nSpreads, maxPage: rig.maxPage, spreadCount: rig.spreadCount, images,
    frames: frameInfo, parts, seatBox: { min: [sb.min.x, sb.min.y, sb.min.z], max: [sb.max.x, sb.max.y, sb.max.z] },
}));
console.log(JSON.stringify({ out: OUT, frames: nF, leaves: N_LEAF, caseVerts: parts.case.n, leafVerts: parts.leaves.n,
    maxPage: rig.maxPage, spreads: nSpreads, images }));
// exit explicitly: Deno 2.8.1 panics in V8's external-memory accounting while tearing down the Skia canvases
// ("Check failed: total_before >= -delta") after everything above is written
Deno.exit(0);
