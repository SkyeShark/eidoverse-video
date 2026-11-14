// core/io.js against the Blender edition's core/io.py and numpy's np.savez (PORT_PLAN.md 8.2, P2; C9), on the files
// core_inputs_expected.py wrote with Blender's Python:
//   PNG16 (export_heightmap): the pixels and the filtered rows byte-identical to Blender's, IHDR and the sidecar
//   equal (the compressed IDAT is another deflate's and is not compared); R32 and R16 byte-identical; read_heightmap
//   of Blender's files equal to numpy's float64 metres rounded once to float32, bit for bit
//   export_mask (8 and 16 bits, given and own ranges, south-up), encode_png for every channel count and depth: the
//   same; Blender's PNGs and the reference DEMs read back to the same samples; a PNG with the Paeth filter refused,
//   naming it; hillshade within 1e-5 and to_u8 within one level of numpy
//   npz: np.savez files of every dtype the terrain stores (and np.savez_compressed) read with every array
//   byte-identical; Blender's Terrain.save files (zip64, float16 masks) read and written back with every array
//   byte-identical and the file byte-identical too (numpy's zip layout is deterministic); a float16 round trip
//   through the GPU exact; with --big, a save over 4 GB streamed the same way
//
//     <Blender's python> -I eidoverse/terrain/tests/core_inputs/core_inputs_expected.py [--big <dir>]
//     $EIDO_GPU_WRAP deno run --no-config --no-lock --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/core_inputs/io_test.mjs [fixtures] [--big]
// Files the test writes go to $EIDO_TEST_SCRATCH or a temporary folder, removed at the end.

import { createHash } from 'node:crypto';
import * as G from '../../core/gpu.js';
import * as IO from '../../core/io.js';
import { Checks, bitsEqual, blenderEdition, finish, fixtures, loadBin, manifest, maxErr, sameJson, jsonDiff, scratch } from './_common.mjs';

const T = new Checks('core_inputs/io');
const FIX = fixtures(Deno.args.find((a) => !a.startsWith('--')));
if (!FIX) Deno.exit(0);
const M = manifest(FIX);
Object.assign(T.extra, { numpy: M.numpy, python: M.python, zlib: M.zlib, blender_commit: M.blender_commit });
const R = await G.init();
T.extra.adapter = R.info?.description ?? null;
const IOD = new URL('io/', FIX);
const iodPath = decodeURIComponent(IOD.pathname).replace(/^\/([A-Za-z]:)/, '$1');
const TMP = scratch();
const arr = (a) => loadBin(FIX, a);
const sha1 = (bytes) => createHash('sha1').update(bytes).digest('hex');
const u8of = (a) => new Uint8Array(a.buffer, a.byteOffset, a.byteLength);
const upload = (a) => R.field(a.shape[0], a.shape[1], 1, a.dtype === 'f32' ? arr(a) : Float32Array.from(arr(a)));
// test code: host samples (uint8 / uint16, (h, w, c) C order) as the u32 samples field an image holds
const samplesOf = (data, h, wc) => R.field(h, wc, 1, Uint32Array.from(data), 'u32');
const fmt = (x) => (x === 0 ? '0' : Math.abs(x) < 1e-3 ? x.toExponential(2) : x.toFixed(4));

async function portPng(path) {
    const bytes = await Deno.readFile(path);
    const { ihdr, rows } = await IO.pngRows(bytes);
    const img = await IO.decodePng(R, bytes);
    const px = await R.read(img.field);
    img.field.destroy();
    return { ihdr, rows, px, img };
}


// -------------------------------------------------------------------------------------------- heightmaps ---

{
    let pix = 0, rows = 0, ihdr = 0, side = 0, r32 = 0, r16 = 0, rd = 0, rdN = 0;
    const bad = [];
    for (const c of M.io.heightmaps) {
        const h = upload(c.data);
        const kw = c.kw;
        const meta = await IO.exportHeightmap(h, TMP, 7.8125, { name: c.name, formats: ['png16', 'r32', 'r16'], x0: kw.x0 ?? 0.0,
            y0: kw.y0 ?? 0.0, northUp: kw.north_up ?? true, rangeM: kw.range_m ?? null });
        h.destroy();
        const p = await portPng(`${TMP}/${c.name}.png`);
        const wantPx = arr(c.pixels), wantRows = arr(c.filtered);
        if (p.px.length === wantPx.length && p.px.every((v, i) => v === wantPx[i])) pix++;
        else bad.push(`${c.name} pixels`);
        if (p.rows.length === wantRows.length && p.rows.every((v, i) => v === wantRows[i])) rows++;
        else bad.push(`${c.name} filtered rows`);
        if ([...p.ihdr.bytes].map((b) => b.toString(16).padStart(2, '0')).join('') === c.ihdr) ihdr++;
        if (sameJson(meta, c.meta) && sameJson(JSON.parse(await Deno.readTextFile(`${TMP}/${c.name}.json`)), c.meta)) side++;
        else bad.push(`${c.name} sidecar ${jsonDiff(meta, c.meta)}`);
        const [a32, b32] = [await Deno.readFile(`${TMP}/${c.name}.r32`), await Deno.readFile(new URL(`${c.name}.r32`, IOD))];
        if (sha1(a32) === sha1(b32)) r32++;
        const [a16, b16] = [await Deno.readFile(`${TMP}/${c.name}.r16`), await Deno.readFile(new URL(`${c.name}.r16`, IOD))];
        if (sha1(a16) === sha1(b16)) r16++;
        else bad.push(`${c.name} r16`);
        // reading Blender's files: numpy's float64 metres, rounded once
        for (const [fmt_, want] of [['png16', c.read_png16], ['r16', c.read_r16]]) {
            rdN++;
            const { field } = await IO.readHeightmap(R, `${iodPath}${c.name}.json`, [fmt_]);
            const got = await R.read(field);
            field.destroy();
            const w = arr(want);
            if (got.every((v, i) => v === Math.fround(w[i]))) rd++;
            else bad.push(`${c.name} read ${fmt_}: ${fmt(maxErr(got, w).abs)}`);
        }
        rdN++;
        const { field } = await IO.readHeightmap(R, `${iodPath}${c.name}.json`, ['r32']);
        const got = await R.read(field);
        field.destroy();
        if (bitsEqual(got, arr(c.data))) rd++;
        else bad.push(`${c.name} read r32`);
    }
    const n = M.io.heightmaps.length;
    const names = M.io.heightmaps.map((c) => c.name).join(', ');
    T.ok(`export_heightmap png16 pixels byte-identical to Blender's: ${pix} of ${n} (${names})`, pix === n, bad.filter((b) => b.includes('pixels')).join(', '));
    T.ok(`export_heightmap png16 filtered rows (the Up filter's bytes) byte-identical: ${rows} of ${n}`, rows === n, bad.filter((b) => b.includes('rows')).join(', '));
    T.ok(`export_heightmap IHDR equal: ${ihdr} of ${n}`, ihdr === n);
    T.ok(`export_heightmap sidecar JSON equal (incl. a pinned range's clipped counts): ${side} of ${n}`, side === n, bad.filter((b) => b.includes('sidecar')).join(' | '));
    T.ok(`export_heightmap r32 byte-identical: ${r32} of ${n}`, r32 === n);
    T.ok(`export_heightmap r16 byte-identical: ${r16} of ${n}`, r16 === n);
    T.ok(`read_heightmap of Blender's png16, r16 (numpy's float64 rounded once) and r32 (exact), bit for bit: ${rd} of ${rdN}`, rd === rdN,
        bad.filter((b) => b.includes('read')).join(', '));
}


// ------------------------------------------------------------------------------------------- masks, codec ---

{
    let ok = 0;
    const bad = [];
    for (const c of M.io.masks) {
        const m = upload(c.data);
        const kw = c.kw;
        const meta = await IO.exportMask(m, TMP, c.name, { lo: kw.lo ?? null, hi: kw.hi ?? null, bits: kw.bits ?? 8, northUp: kw.north_up ?? true });
        m.destroy();
        const p = await portPng(`${TMP}/${c.name}.png`);
        const wantPx = arr(c.pixels), wantRows = arr(c.filtered);
        const same = p.px.every((v, i) => v === wantPx[i]) && p.rows.every((v, i) => v === wantRows[i]) && p.rows.length === wantRows.length &&
            [...p.ihdr.bytes].map((b) => b.toString(16).padStart(2, '0')).join('') === c.ihdr && sameJson(meta, c.meta);
        if (same) ok++;
        else bad.push(`${c.name}: ${jsonDiff(meta, c.meta) ?? 'pixels or rows'}`);
    }
    T.ok(`export_mask: pixels, filtered rows, IHDR and sidecar equal for ${ok} of ${M.io.masks.length} (8 and 16 bits, given and own ranges, south-up)`,
        ok === M.io.masks.length, bad.join(' | '));
    let enc = 0, dec = 0;
    for (const c of M.io.pngs) {
        const data = arr(c.data);
        const [h, w] = c.data.shape;
        const f = samplesOf(data, h, w * c.channels);
        const rowsPort = await IO.filteredRows({ field: f, width: w, height: h, channels: c.channels, bitDepth: c.bits });
        const png = await IO.encodePng({ field: f, width: w, height: h, channels: c.channels, bitDepth: c.bits });
        f.destroy();
        const want = arr(c.filtered);
        const { ihdr } = IO.pngChunks(png);
        if (rowsPort.length === want.length && rowsPort.every((v, i) => v === want[i]) &&
            [...ihdr.bytes].map((b) => b.toString(16).padStart(2, '0')).join('') === c.ihdr) enc++;
        const p = await portPng(new URL(c.file, IOD));
        if (p.px.every((v, i) => v === data[i]) && p.img.channels === c.channels && p.img.bitDepth === c.bits) dec++;
    }
    T.ok(`encode_png: filtered rows and IHDR byte-identical for ${enc} of ${M.io.pngs.length} (8 and 16 bits, 1-4 channels)`, enc === M.io.pngs.length);
    T.ok(`decode_png of Blender's PNGs: samples equal for ${dec} of ${M.io.pngs.length}`, dec === M.io.pngs.length);
    let refused = '';
    try {
        await IO.readPng(R, new URL(M.io.paeth.file, IOD));
    } catch (e) {
        refused = e.message;
    }
    T.ok('a PNG with the Paeth filter is refused, naming it (no reference PNG uses it)', /filter type 4 \(Paeth\) on row 5/.test(refused), refused);
    // the reference DEMs, read where real_place reads them
    const root = blenderEdition();
    let dems = 0, demN = 0;
    const missing = [];
    for (const d of M.io.dems) {
        const p = root ? `${root}/${d.path}` : null;
        try {
            Deno.statSync(p);
        } catch (_e) {
            missing.push(d.name);
            continue;
        }
        demN++;
        const img = await IO.readPng(R, p);
        const s = await R.read(img.field);
        img.field.destroy();
        const typed = d.dtype === 'uint16' ? Uint16Array.from(s) : Uint8Array.from(s);   // test code: the samples' bytes
        if (sha1(u8of(typed)) === d.sha1 && img.height === d.shape[0] && img.width === d.shape[1]) dems++;
    }
    T.ok(`reference DEMs and water masks read to the same samples as Blender's read_png: ${dems} of ${demN}`, demN > 0 && dems === demN,
        missing.length ? `not found: ${missing.join(', ')} (set $EIDO_BLENDER_EDITION)` : M.io.dems.map((d) => `${d.name} ${d.key}`).join(', '));
    // hillshade and to_u8
    const H = M.io.hillshade;
    const hf = upload(H.data);
    const hs = IO.hillshade(hf, H.cell), hs2 = IO.hillshade(hf, H.cell, 200.0, 25.0, 3.0);
    const [a, b] = [await R.read(hs), await R.read(hs2)];
    const q = IO.toU8(hs);
    const qa = await R.read(q);
    for (const f of [hf, hs, hs2, q]) f.destroy();
    const e1 = maxErr(a, arr(H.want), 1).abs, e2 = maxErr(b, arr(H.want2), 1).abs;
    const u8 = arr(H.u8);
    let off = 0, worst = 0;
    for (let i = 0; i < u8.length; i++) {
        const d = Math.abs(qa[i] - u8[i]);
        if (d) off++;
        worst = Math.max(worst, d);
    }
    T.ok('hillshade (both lights, a height factor) within 1e-5 of numpy\'s float64; to_u8 within one level', e1 <= 1e-5 && e2 <= 1e-5 && worst <= 1,
        `${fmt(e1)}, ${fmt(e2)}; to_u8 off by one level on ${off} of ${u8.length} cells (float32 against float64 shading)`);
}


// ---------------------------------------------------------------------------------------------------- npz ---

async function fileSha1(path) {
    const h = createHash('sha1');
    const f = await Deno.open(path, { read: true });
    const buf = new Uint8Array(1 << 24);
    try {
        for (;;) {
            const n = await f.read(buf);
            if (n === null) break;
            h.update(buf.subarray(0, n));
        }
    } finally {
        f.close();
    }
    return h.digest('hex');
}

// stream every array from the file into a new file, entry by entry (one array in memory at a time), checking each
// against Python's sha1, dtype and shape on the way; then compare the two files
async function roundTrip(path, want, order, label) {
    let same = 0, n = 0;
    const bad = [];
    const dir = await IO.npzDirectory(path);
    const it = IO.iterNpz(path);
    const list = dir.map((e) => [e.name, async () => {
        const { value } = await it.next();
        const [name, a] = value;
        n++;
        const w = want[name];
        if (name === e.name && w && sha1(u8of(a.data)) === w.sha1 && a.dtype === w.dtype && sameJson(a.shape, w.shape)) same++;
        else bad.push(name);
        return a;
    }]);
    const out = `${TMP}/${label}_back.npz`;
    const t0 = performance.now();
    await IO.writeNpz(out, list);
    const seconds = (performance.now() - t0) / 1000;
    await it.return();
    const fileSame = (await fileSha1(out)) === (await fileSha1(path));
    const orderSame = sameJson(dir.map((e) => e.name), order);
    await Deno.remove(out);
    return { same, n, bad, fileSame, orderSame, seconds };
}

{
    const mixed = M.io.npz[0];
    const got = await IO.readNpz(new URL(mixed.file, IOD).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
    const names = Object.keys(mixed.arrays);
    const ok = names.every((k) => got[k] && got[k].dtype === mixed.arrays[k].dtype && sameJson(got[k].shape, mixed.arrays[k].shape) &&
        sha1(u8of(got[k].data)) === mixed.arrays[k].sha1);
    T.ok(`np.savez of every dtype the terrain stores (f4, f2, f8, u1, u2, u4, i4, bool, 0-d, 1-d, 3-d, empty) read byte-identical: ${names.length} arrays`, ok,
        names.filter((k) => !got[k] || sha1(u8of(got[k].data)) !== mixed.arrays[k].sha1).join(', '));
    const rt = await roundTrip(`${iodPath}${mixed.file}`, mixed.arrays, names, 'mixed');
    T.ok('np.savez file written back from its arrays byte-identical (the zip64 layout, the headers, the padding)', rt.fileSame && rt.orderSame);
    const comp = await IO.readNpz(`${iodPath}${M.io.npz[1].file}`);
    T.ok('np.savez_compressed (deflated entries) read byte-identical', names.every((k) => comp[k] && sha1(u8of(comp[k].data)) === mixed.arrays[k].sha1));
    // a deflated write read back, and refused when its CRC is wrong
    const cpath = `${TMP}/compressed.npz`;
    await IO.writeNpz(cpath, got, { compress: true });
    const back = await IO.readNpz(cpath);
    T.ok('writeNpz({ compress }) read back byte-identical', names.every((k) => sha1(u8of(back[k].data)) === mixed.arrays[k].sha1));
    const raw = await Deno.readFile(`${iodPath}${mixed.file}`);
    raw[200] ^= 0xFF;                                     // inside the first array's data
    await Deno.writeFile(`${TMP}/corrupt.npz`, raw);
    let crc = '';
    try {
        await IO.readNpz(`${TMP}/corrupt.npz`);
    } catch (e) {
        crc = e.message;
    }
    T.ok('a corrupted entry is refused on its CRC-32, as np.load refuses it', /Bad CRC-32/.test(crc), crc);
    for (const f of [cpath, `${TMP}/corrupt.npz`]) await Deno.remove(f);
}
{
    let saves = 0;
    const det = [];
    for (const s of M.io.saves) {
        try {
            Deno.statSync(s.path);
        } catch (_e) {
            det.push(`${s.path.split(/[\\/]/).pop()} missing`);
            continue;
        }
        const label = s.path.split(/[\\/]/).pop().replace('.npz', '');
        const rt = await roundTrip(s.path, s.arrays, s.order, label);
        const ok = rt.same === rt.n && rt.n === s.order.length && rt.fileSame && rt.orderSame;
        if (ok) saves++;
        const f16 = Object.values(s.arrays).filter((a) => a.dtype === '<f2').length;
        det.push(`${label}: ${rt.same} of ${rt.n} arrays (${f16} float16), ${(s.bytes / 1e6).toFixed(0)} MB, file ${rt.fileSame ? 'identical' : 'DIFFERS'}, ` +
            `read and written back in ${rt.seconds.toFixed(1)} s`);
    }
    T.ok(`Blender Terrain.save files read and written back, every array byte-identical and the file too: ${saves} of ${M.io.saves.length}`,
        M.io.saves.length > 0 && saves === M.io.saves.length, det.join(' | '));
    // float16 through the GPU: the masks up as float32 and back as float16, numpy's cast (exact on float16 values)
    if (M.io.saves.length) {
        const s = M.io.saves[0];
        const names = s.order.filter((k) => s.arrays[k].dtype === '<f2').slice(0, 6);
        let same = 0;
        for await (const [name, a] of IO.iterNpz(s.path, { names })) {
            const f = IO.fieldFromArray(R, a);
            const back = await IO.arrayFromField(f, '<f2');
            f.destroy();
            if (sha1(u8of(back.data)) === s.arrays[name].sha1) same++;
        }
        T.ok(`float16 masks through the GPU (fieldFromArray, arrayFromField '<f2') byte-identical: ${same} of ${names.length}`, same === names.length && same > 0);
    }
    // numpy's float32 -> float16 rounding on the GPU, against the CPU's (V8's Float16Array rounds to nearest even too)
    const n = 1 << 18;
    const v = new Float32Array(n);
    const bits = new Uint32Array(v.buffer);
    for (let i = 0; i < n; i++) bits[i] = (Math.imul(i, 2654435761) >>> 0) ^ (i << 7);   // test data: every exponent
    for (let i = 0; i < n; i++) if (Number.isNaN(v[i])) v[i] = 0;
    const f = R.field(1 << 9, 1 << 9, 1, v);
    const back = await IO.arrayFromField(f, '<f2');
    f.destroy();
    const cpu = Float16Array.from(v);
    const a = new Uint16Array(back.data.buffer, back.data.byteOffset, n), b = new Uint16Array(cpu.buffer);
    let diff = 0;
    for (let i = 0; i < n; i++) if (a[i] !== b[i]) diff++;
    T.ok(`float32 -> float16 on the GPU (numpy's npy_floatbits_to_halfbits) equal to round-to-nearest-even on ${n - diff} of ${n} values (overflow, subnormals, ties)`,
        diff === 0, `${diff} differ`);
}
if (Deno.args.includes('--big')) {
    const B = M.io.big;
    if (!B) {
        T.ok('the save over 4 GB (core_inputs_expected.py --big <dir>)', false, 'the fixtures were made without --big');
    } else {
        const rt = await roundTrip(B.path, B.arrays, B.order, 'big');
        T.ok(`a save over 4 GB (${(B.bytes / 1e9).toFixed(2)} GB, ${B.order.length} arrays: zip64 offsets, the zip64 end records) streamed, ` +
            'every array and the file byte-identical', rt.same === rt.n && rt.n === B.order.length && rt.fileSame && rt.orderSame,
            `${rt.same} of ${rt.n} arrays; file ${rt.fileSame ? 'identical' : 'DIFFERS'}; read and written back in ${rt.seconds.toFixed(1)} s`);
    }
}

try {
    if (!Deno.env.get('EIDO_TEST_SCRATCH')) await Deno.remove(TMP, { recursive: true });
} catch (_e) { /* fine */ }
G.shutdown();
Deno.exit(finish(T, 'io_test.json'));
