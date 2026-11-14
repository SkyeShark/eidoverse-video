// Port of blender/eidoblend/terrain/core/io.py at f90c6fc, and of the npz files numpy's np.savez writes for the
// Blender edition's Terrain.save and cache (numpy 2.3.4, Python 3.13's zipfile).
//
// Heightmaps and masks in and out, for other tools (design section 3: Ekigar's export PNG16/R32, moved), PNG files,
// and the npz save format both editions write and read (PORT_PLAN.md 5.2).
//
//     await exportHeightmap(h, outDir, cellM, { name: 'height', formats: ['png16', 'r32'], x0, y0 })
//         -> the sidecar, also written as <name>.json: size, cell, extent, row order, height range in metres
//     const { field, meta } = await readHeightmap('<dir>/height.json')    // metres, row 0 = south (a GPU field)
//     await exportMask(m, outDir, 'slope', { lo: 0, hi: 90 })             // an 8- or 16-bit PNG of a mask over [lo, hi]
//     await writePng(path, image) / await readPng(path)                   // image: { field, width, height, channels,
//                                                                         //   bitDepth }: field holds the integer
//                                                                         //   samples (u32, h x w channels, row 0 top)
//     await writeNpz(path, arrays) / await readNpz(path) / npzDirectory(path) / iterNpz(path)
//     hillshade(h, cell), toU8(t), quantise(h, lo, span, top), encodeR32, normaliseHeights
//
// Arrays in this package are row 0 = SOUTH; files other tools read are top-down (row 0 = north), so export flips
// once (northUp) and the sidecar says which. png16 is 16-bit grayscale normalised over the sidecar's [min_m, max_m];
// r32 is headerless little-endian float32 in METRES; r16 headerless little-endian uint16 normalised like png16.
//
// The per-texel parts run on the GPU (PORT_PLAN.md 2.4, 3.2, C9): the 16-bit quantisation (kernels/grid/
// quantise.wgsl, exact: numpy's float64 arithmetic decides a table of the quantisation's steps, which every cell
// counts), the row flip, the big-endian rows and the Up filter (png_rows.wgsl, read back once), the r16 packing,
// and on reading the filter undone and the samples turned into metres (dequantise.wgsl, numpy's float64 value
// rounded once). JavaScript keeps the file framing: zlib through CompressionStream('deflate') and
// DecompressionStream('deflate'), the PNG chunks and their CRCs (node:zlib crc32), the npz's zip framing, JSON.
//
// The PNG chunk parsing and writing follow Ekigar's src/export/png.js and png_read.js (MIT, Copyright (c) 2026
// SkyeShark; the notice is in Ekigar's LICENSE: "Permission is hereby granted, free of charge, to any person
// obtaining a copy of this software ... The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software."). Their inflate is not used: it takes stored blocks only,
// and every Blender PNG is Huffman-coded.
//
// npz (np.savez: a zip of <name>.npy entries): read and written entry by entry, so a hero save over 4 GB never sits
// in one buffer (PORT_PLAN.md 3.2, C9). Zip64 always, as numpy opens every entry with force_zip64; the layout is
// Python's zipfile's (the date 1980-01-01, the versions, the attributes, the zip64 records past 2 GB), so a save
// this module writes from the arrays it read is the same file, byte for byte. Entries may be stored (np.savez) or
// deflated (np.savez_compressed; written with CompressionStream('deflate-raw')). Every entry's CRC is checked on
// reading, as numpy's np.load checks it. Ekigar's materials/zip.js refuses zip64 and caps an entry at 256 MB.
//
// An array is { dtype, shape, data }: dtype numpy's descr ('<f4', '<f2', '|u1', '<u2', '<i4', '<f8', '|b1', ...),
// shape an array of integers, data the typed array (Float32Array, Float16Array, Uint8Array, ...) in C order.
//
// Where this differs from io.py, and why:
//   - read_heightmap returns float32 metres on the GPU (numpy's float64 value rounded once); read_png a GPU field of
//     the integer samples (row 0 top) with its size; write_png and the exports take GPU fields.
//   - decode_png undoes every filter type on the CPU; here only None and Up (the GPU's), and a PNG whose rows use
//     another (Sub, Average, Paeth) throws naming it: no reference PNG does (44 of 44, PORT_PLAN.md 3.2).
//   - encode_png's zlib is Blender's Python's (zlib 1.3.1); CompressionStream is another deflate, so a PNG's IDAT
//     bytes differ while its pixels, its filtered rows and its IHDR are Blender's (C9). np.savez_compressed's
//     deflate likewise.

import { crc32 } from 'node:zlib';
import * as Gd from './grid.js';
import { ValueError, pyReprValue, pyStr } from './levels.js';
import { keyToFloat, listShape, prims } from './prims.js';

export const SIDECAR = 'eidoverse-terrain-heightmap/1';
const SIG = Uint8Array.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
const CHANNELS = { 0: 1, 2: 3, 4: 2, 6: 4 };
const COLOUR = { 1: 0, 2: 4, 3: 2, 4: 6 };
const FILTERS = { 1: 'Sub', 3: 'Average', 4: 'Paeth' };

const enc = new TextEncoder();
const dec = new TextDecoder();
const ascii = (s) => Uint8Array.from(s, (c) => c.charCodeAt(0));

function concat(parts) {
    let n = 0;
    for (const p of parts) n += p.length;
    const out = new Uint8Array(n);
    let o = 0;
    for (const p of parts) {
        out.set(p, o);
        o += p.length;
    }
    return out;
}

async function streamBytes(bytes, transform) {
    const s = new Blob([bytes]).stream().pipeThrough(transform);
    return new Uint8Array(await new Response(s).arrayBuffer());
}

const deflate = (bytes) => streamBytes(bytes, new CompressionStream('deflate'));
const inflate = (bytes) => streamBytes(bytes, new DecompressionStream('deflate'));

async function writeAll(file, bytes) {
    let o = 0;
    while (o < bytes.length) o += await file.write(bytes.subarray(o));
}

async function readExactly(file, into, what) {
    let o = 0;
    while (o < into.length) {
        const n = await file.read(into.subarray(o));
        if (n === null) throw new Error(`${what}: the file ends early`);
        o += n;
    }
    return into;
}

const isField = (v) => v !== null && typeof v === 'object' && typeof v.h === 'number' && v.runner !== undefined;
const dirOf = (p) => p.replace(/\\/g, '/').replace(/\/[^/]*$/, '') || '.';
const joinPath = (d, f) => `${String(d).replace(/[\\/]+$/, '')}/${f}`;


// ------------------------------------------------------------------------------------------------------- PNG ---

function chunk(kind, data) {
    const out = new Uint8Array(12 + data.length);
    const v = new DataView(out.buffer);
    v.setUint32(0, data.length);
    out.set(ascii(kind), 4);
    out.set(data, 8);
    v.setUint32(8 + data.length, crc32(out.subarray(4, 8 + data.length)) >>> 0);
    return out;
}

/** The filtered rows encode_png hands zlib (filter type 2, Up, on every row; 16-bit samples big-endian), made on the
 * GPU from an image's samples and read back: a Uint8Array of h (w c bytes-per-sample + 1) bytes. */
export async function filteredRows(image) {
    const { field, width, height, channels, bitDepth } = image;
    const R = field.runner;
    const bps = bitDepth === 16 ? 2 : 1;
    const len = height * (width * channels * bps + 1);
    const words = Math.ceil(len / 4);
    const [lh, lw] = listShape(words);
    const out = R.field(lh, lw, 1, null, 'u32');
    R.run('grid/png_rows', { src: field }, { outW: out },
        { uMode: 0, uSize: [width * channels, height], uBps: bps, uWords: words, uLine: lw });
    const got = await R.read(out);
    out.destroy();
    return new Uint8Array(got.buffer, got.byteOffset, len);
}

/** PNG bytes of an image (samples on the GPU, row 0 = top, uint8 or uint16, 1-4 channels), as encode_png lays it out:
 * IHDR, one IDAT of the Up-filtered rows through zlib (CompressionStream), IEND. */
export async function encodePng(image) {
    const { width, height, channels, bitDepth } = image;
    if (bitDepth !== 8 && bitDepth !== 16) throw new ValueError(`encode_png wants uint8 or uint16, got a ${bitDepth}-bit image`);
    if (!(channels in COLOUR)) throw new ValueError(`encode_png: ${channels} channels; 1 to 4`);
    const filt = await filteredRows(image);
    const ihdr = new Uint8Array(13);
    const v = new DataView(ihdr.buffer);
    v.setUint32(0, width);
    v.setUint32(4, height);
    ihdr[8] = bitDepth;
    ihdr[9] = COLOUR[channels];
    return concat([SIG, chunk('IHDR', ihdr), chunk('IDAT', await deflate(filt)), chunk('IEND', new Uint8Array(0))]);
}

export async function writePng(path, image) {
    await Deno.mkdir(dirOf(path), { recursive: true });
    await Deno.writeFile(path, await encodePng(image));
    return path;
}

/** The chunks of PNG bytes: { ihdr: { width, height, bitDepth, colour, compression, filter, interlace }, idat
 * (the joined IDAT data), bytes }. */
export function pngChunks(bytes) {
    for (let i = 0; i < 8; i++) if (bytes[i] !== SIG[i]) throw new ValueError('not a PNG');
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let o = 8, ihdr = null;
    const idat = [];
    while (o < bytes.length) {
        const len = view.getUint32(o);
        const type = String.fromCharCode(bytes[o + 4], bytes[o + 5], bytes[o + 6], bytes[o + 7]);
        const body = bytes.subarray(o + 8, o + 8 + len);
        if (type === 'IHDR') {
            ihdr = { width: view.getUint32(o + 8), height: view.getUint32(o + 12), bitDepth: bytes[o + 16], colour: bytes[o + 17],
                compression: bytes[o + 18], filter: bytes[o + 19], interlace: bytes[o + 20], bytes: body };
        } else if (type === 'IDAT') {
            idat.push(body);
        } else if (type === 'IEND') {
            break;
        }
        o += 12 + len;
    }
    if (!ihdr) throw new ValueError('PNG without an IHDR chunk');
    return { ihdr, idat: concat(idat) };
}

/** The inflated IDAT (the filtered rows) and IHDR of PNG bytes. */
export async function pngRows(bytes) {
    const { ihdr, idat } = pngChunks(bytes);
    return { ihdr, rows: await inflate(idat) };
}

/** An image ({ field, width, height, channels, bitDepth }) from PNG bytes: any non-interlaced 8/16-bit gray, GA, RGB
 * or RGBA PNG whose rows use the None or Up filter, the filters undone on the GPU (one invocation per sample
 * column). field: u32 samples, h x w channels, row 0 = top. */
export async function decodePng(R, bytes) {
    const { ihdr, rows } = await pngRows(bytes);
    const { width: w, height: h, bitDepth: depth, colour, interlace } = ihdr;
    if (interlace) throw new ValueError('interlaced PNGs are not supported');
    if ((depth !== 8 && depth !== 16) || !(colour in CHANNELS)) {
        throw new ValueError(`PNG colour type ${colour} at ${depth} bits is not supported (8/16-bit gray, GA, RGB, RGBA)`);
    }
    const c = CHANNELS[colour];
    const bps = depth / 8;
    const stride = w * c * bps;
    if (rows.length < h * (stride + 1)) throw new ValueError(`PNG IDAT is ${rows.length} bytes, expected ${h * (stride + 1)}`);
    for (let r = 0; r < h; r++) {                          // one byte per row: the filter types
        const k = rows[r * (stride + 1)];
        if (k !== 0 && k !== 2) {
            throw new ValueError(k in FILTERS ? `PNG filter type ${k} (${FILTERS[k]}) on row ${r} is not supported: this reader ` +
                'undoes None and Up, the filters encode_png and every reference PNG use' : `PNG filter type ${k} is not valid`);
        }
    }
    const nw = Math.ceil(rows.length / 4);
    const padded = new Uint8Array(nw * 4);
    padded.set(rows);
    const [lh, lw] = listShape(nw);
    const words = new Uint32Array(lh * lw);
    words.set(new Uint32Array(padded.buffer));
    const src = R.field(lh, lw, 1, words, 'u32');
    const field = R.field(h, w * c, 1, null, 'u32');
    R.run('grid/png_rows', { src }, { outW: field }, { uMode: 1, uSize: [w * c, h], uBps: bps, uWords: nw, uLine: lw },
        [Math.ceil((w * c) / 64), 1, 1]);
    src.destroy();
    return { field, width: w, height: h, channels: c, bitDepth: depth };
}

/** A PNG file as an image (see decodePng): row 0 = top. */
export async function readPng(R, path) {
    return decodePng(R, await Deno.readFile(path));
}


// --------------------------------------------------------------------------------------- the quantisation ---

const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);
function fkey(v) {
    F32[0] = v;
    const b = U32[0];
    if ((b & 0x7FFFFFFF) > 0x7F800000) return 0xFFFFFFFF;
    if ((b & 0x7FFFFFFF) === 0) return 0x80000000;
    return (b & 0x80000000) ? (~b >>> 0) : ((b | 0x80000000) >>> 0);
}
const KEY_LO = fkey(-Infinity), KEY_HI = fkey(Infinity);

// the smallest key in [lo, hi] at which pred holds (pred monotone false -> true over the keys); hi + 1 when none
function firstKey(pred, lo, hi) {
    let a = lo, b = hi + 1;
    while (a < b) {
        const m = a + Math.floor((b - a) / 2);
        if (pred(keyToFloat(m))) b = m;
        else a = m + 1;
    }
    return a;
}

/** The steps of the quantisation clip(floor(clip((v - lo) / span, 0, 1) top + 0.5), 0, top) of float32 values, as
 * order keys: step k (k = 1 .. top) is the key of the smallest float32 v with q(v) >= k, found with numpy's float64
 * arithmetic (JavaScript doubles: the same operations). A table over the levels, not the cells. */
export function quantiseSteps(lo, span, top) {
    const q = (v) => Math.min(Math.max(Math.floor(Math.min(Math.max((v - lo) / span, 0.0), 1.0) * top + 0.5), 0), top);
    const steps = new Uint32Array(top);
    let prev = KEY_LO;
    for (let k = 1; k <= top; k++) {
        // bracket around the real step lo + (k - 0.5) span / top, widened until it holds the key
        const guess = fkey(Math.fround(lo + ((k - 0.5) / top) * span));
        let d = 64;
        let a = Math.max(prev, guess - d), b = Math.min(KEY_HI, guess + d);
        while (a > prev && q(keyToFloat(a)) >= k) a = Math.max(prev, a - (d *= 4));
        while (b < KEY_HI && q(keyToFloat(b)) < k) b = Math.min(KEY_HI, b + (d *= 4));
        const key = firstKey((v) => q(v) >= k, a, b);
        steps[k - 1] = key;
        prev = key;
    }
    return steps;
}

/** The integer quantisation of a float field over [lo, lo + span] to 0..top, exactly as numpy's
 * clip(round_half_up(clip((v - lo) / span, 0, 1) * top), 0, top): a u32 field (row 0 north when opts.flip). */
export function quantise(f, lo, span, top, opts = {}) {
    const R = f.runner;
    const steps = R.field(...listShape(top), 1, (() => {
        const s = quantiseSteps(lo, span, top);
        const [lh, lw] = listShape(top);
        const full = new Uint32Array(lh * lw).fill(0xFFFFFFFF);
        full.set(s);
        return full;
    })(), 'u32');
    const out = R.field(f.h, f.w, 1, null, 'u32');
    R.run('grid/quantise', { src: f, steps }, { outQ: out }, { uTop: top, uFlip: opts.flip ? 1 : 0 });
    steps.destroy();
    return out;
}

/** The float32 value of every integer sample 0 .. top under value = lo + v / top * span, computed in doubles as numpy
 * computes it (lo + (v / top) * span) and rounded once: the table dequantise() reads. */
export function dequantiseTable(lo, span, top = 65535, form = 'read_heightmap') {
    const t = new Float32Array(top + 1);
    for (let v = 0; v <= top; v++) t[v] = form === 'real_place' ? lo + v * (span / top) : lo + (v / top) * span;
    return t;
}

/** Integer samples (a u32 field, or opts.packed16: a list of words holding two little-endian uint16 each, opts.shape
 * [h, w]) to float32 values through a table (dequantiseTable), row 0 south (opts.flip: the samples are top-down). */
export function dequantise(q, table, opts = {}) {
    const R = q.runner;
    const [h, w] = opts.shape ?? [q.h, q.w];
    const [lh, lw] = listShape(table.length);
    const full = new Float32Array(lh * lw);
    full.set(table);
    const t = R.field(lh, lw, 1, full);
    const out = R.field(h, w, 1);
    R.run('grid/dequantise', { q, table: t }, { outF: out },
        { uFlip: opts.flip ? 1 : 0, uCount: table.length, uPacked: opts.packed16 ? 1 : 0 });
    t.destroy();
    return out;
}


// ------------------------------------------------------------------------------------------------ raw formats ---

/** Headerless little-endian float32 of a float field (read back). */
export async function encodeR32(f) {
    const a = await f.runner.read(f);
    return new Uint8Array(a.buffer, a.byteOffset, a.byteLength);
}

/** Headerless little-endian uint16 of integer samples (a u32 field, each below 65536), packed on the GPU. */
export async function encodeR16(q) {
    const R = q.runner;
    const count = q.h * q.w;
    const words = Math.ceil(count / 2);
    const [lh, lw] = listShape(words);
    const out = R.field(lh, lw, 1, null, 'u32');
    R.run('grid/pack_u16', { src: q }, { outW: out }, { uCount: count, uLine: lw });
    const got = await R.read(out);
    out.destroy();
    return new Uint8Array(got.buffer, got.byteOffset, 2 * count);
}

/** [0, 1] over the field's range (or a pinned rangeM [lo, hi]: export a tile SEQUENCE with one range, or the seams
 * become cliffs): { lo, hi, span, clipped_lo, clipped_hi } (the field itself is quantised by quantise(), exactly). */
export async function normaliseHeights(f, rangeM = null) {
    const P = prims(f.runner);
    let lo, hi;
    if (rangeM === null || rangeM === undefined) {
        const s = await P.stats(f);
        lo = s.min;
        hi = s.max;
    } else {
        lo = Number(rangeM[0]);
        hi = Number(rangeM[1]);
    }
    const span = Math.max(hi - lo, 1e-12);
    let clippedLo = 0, clippedHi = 0;
    if (rangeM !== null && rangeM !== undefined) {
        // (t < 0).sum() and (t > 1).sum() with t = (v - lo) / span in float64: the float32 values below the first
        // with t >= 0, and from the first with t > 1
        const t0 = keyToFloat(firstKey((v) => (v - lo) / span >= 0, KEY_LO, KEY_HI));
        const t1 = keyToFloat(firstKey((v) => (v - lo) / span > 1, KEY_LO, KEY_HI));
        const below = P.where(f, '<', t0), above = P.where(f, '>=', t1);
        clippedLo = (await P.statsU32(below)).nonzero;
        clippedHi = (await P.statsU32(above)).nonzero;
        below.destroy();
        above.destroy();
    }
    return { lo, hi, span, clipped_lo: clippedLo, clipped_hi: clippedHi };
}


// --------------------------------------------------------------------------------------- heightmaps and masks ---

const pyJson = (v) => JSON.stringify(v, null, 1);

/** Write a heightmap in metres (a float field, row 0 = south) in each format, and <name>.json, the sidecar
 * carrying what the files cannot: size, cell, world origin, row order and the height range. Returns the sidecar.
 * opts: name ('height'), formats (['png16', 'r32']; 'r16' too), x0, y0, northUp (true), rangeM. */
export async function exportHeightmap(h, outDir, cellM, opts = {}) {
    const { name = 'height', formats = ['png16', 'r32'], x0 = 0.0, y0 = 0.0, northUp = true, rangeM = null } = opts;
    if (!isField(h)) throw new TypeError('export_heightmap: a GPU field (core/gpu.js) of heights is needed');
    const [rows, cols] = [h.h, h.w];
    await Deno.mkdir(outDir, { recursive: true });
    const nrm = await normaliseHeights(h, rangeM);
    const files = {};
    let q = null;
    const quant = () => (q = q ?? quantise(h, nrm.lo, nrm.span, 65535, { flip: northUp }));
    for (const fmt of formats) {
        if (fmt === 'png16') {
            const fn = name + '.png';
            await writePng(joinPath(outDir, fn), { field: quant(), width: cols, height: rows, channels: 1, bitDepth: 16 });
            files.png16 = { file: fn, encoding: 'height_m = min_m + v / 65535 * (max_m - min_m)' };
        } else if (fmt === 'r32') {
            const fn = name + '.r32';
            const out = northUp ? Gd.fromNorthUp(h) : h;
            await Deno.writeFile(joinPath(outDir, fn), await encodeR32(out));
            if (out !== h) out.destroy();
            files.r32 = { file: fn, encoding: 'headerless little-endian float32, metres' };
        } else if (fmt === 'r16') {
            const fn = name + '.r16';
            await Deno.writeFile(joinPath(outDir, fn), await encodeR16(quant()));
            files.r16 = { file: fn, encoding: 'headerless little-endian uint16: height_m = min_m + v / 65535 * (max_m - min_m)' };
        } else {
            if (q) q.destroy();
            throw new ValueError(`heightmap format ${pyReprValue(fmt)} is 'png16', 'r32' or 'r16'`);
        }
    }
    if (q) q.destroy();
    const meta = { format: SIDECAR, name, width: cols, height: rows, cell_m: Number(cellM),
        extent_m: [cols * Number(cellM), rows * Number(cellM)], x0_m: Number(x0), y0_m: Number(y0),
        row_order: northUp ? 'row 0 is the NORTH edge' : 'row 0 is the SOUTH edge', min_m: nrm.lo, max_m: nrm.hi,
        clipped_low: nrm.clipped_lo, clipped_high: nrm.clipped_hi, files };
    await Deno.writeTextFile(joinPath(outDir, name + '.json'), pyJson(meta));
    return meta;
}

/** { field: heights in metres (float32, row 0 = SOUTH, on the GPU), meta: the sidecar } from a sidecar written by
 * exportHeightmap (either edition's). prefer: the formats to try, in order. */
export async function readHeightmap(R, sidecarPath, prefer = ['r32', 'png16', 'r16']) {
    const meta = JSON.parse(await Deno.readTextFile(sidecarPath));
    const d = dirOf(sidecarPath);
    const [rows, cols] = [meta.height, meta.width];
    const northUp = String(meta.row_order).startsWith('row 0 is the NORTH');
    for (const fmt of prefer) {
        if (!(fmt in meta.files)) continue;
        const path = joinPath(d, meta.files[fmt].file);
        let field;
        if (fmt === 'r32') {
            const bytes = await Deno.readFile(path);
            const a = new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + rows * cols * 4));
            const top = R.field(rows, cols, 1, a);
            field = northUp ? Gd.fromNorthUp(top) : top;
            if (field !== top) top.destroy();
        } else if (fmt === 'png16') {
            const img = await readPng(R, path);
            field = dequantise(img.field, dequantiseTable(meta.min_m, meta.max_m - meta.min_m), { flip: northUp });
            img.field.destroy();
        } else {
            const bytes = await Deno.readFile(path);
            const nw = Math.ceil((rows * cols) / 2);
            const [lh, lw] = listShape(nw);
            const words = new Uint32Array(lh * lw);
            new Uint8Array(words.buffer).set(bytes.subarray(0, rows * cols * 2));
            const q = R.field(lh, lw, 1, words, 'u32');
            field = dequantise(q, dequantiseTable(meta.min_m, meta.max_m - meta.min_m), { flip: northUp, packed16: true, shape: [rows, cols] });
            q.destroy();
        }
        return { field, meta };
    }
    throw Object.assign(new Error(`${sidecarPath}: no file in formats ${pyStr(prefer)}`), { name: 'FileNotFoundError' });
}

/** A mask (a float field) as an 8- or 16-bit gray PNG over [lo, hi] (default: its own range), plus <name>.json with
 * the range. opts: lo, hi, bits (8), northUp (true). */
export async function exportMask(m, outDir, name, opts = {}) {
    const { bits = 8, northUp = true } = opts;
    let { lo = null, hi = null } = opts;
    if (lo === null || hi === null) {
        const s = await prims(m.runner).stats(m);
        lo = lo === null ? s.min : Number(lo);
        hi = hi === null ? s.max : Number(hi);
    }
    lo = Number(lo);
    hi = Number(hi);
    const top = bits === 8 ? 255 : 65535;
    const q = quantise(m, lo, Math.max(hi - lo, 1e-12), top, { flip: northUp });
    await writePng(joinPath(outDir, name + '.png'), { field: q, width: m.w, height: m.h, channels: 1, bitDepth: bits === 8 ? 8 : 16 });
    q.destroy();
    const meta = { name, file: name + '.png', bits, lo, hi, row_order: northUp ? 'row 0 is the NORTH edge' : 'row 0 is the SOUTH edge',
        encoding: `value = lo + v / ${top} * (hi - lo)` };
    await Deno.writeTextFile(joinPath(outDir, name + '.json'), pyJson(meta));
    return meta;
}

/** A 0..1 hillshade of a row-0-south field (sun from the north-west, 40 degrees up, as the research's): for
 * previews. A new field. Write it top-down: writePng(path, { field: toU8(fromNorthUp(hs)), ... }). */
export function hillshade(h, cell, azimuthDeg = 315.0, altitudeDeg = 40.0, z = 1.0) {
    const az = azimuthDeg * (Math.PI / 180), alt = altitudeDeg * (Math.PI / 180);
    const light = [Math.sin(az) * Math.cos(alt), Math.cos(az) * Math.cos(alt), Math.sin(alt)];
    return Gd.shade(h, cell, light, z);
}

/** clip(round_half_up(t 255), 0, 255) of a float field: u32 samples 0..255 (row 0 north when opts.flip). */
export function toU8(t, opts = {}) {
    return quantise(t, 0.0, 1.0, 255, opts);
}


// ------------------------------------------------------------------------------------------------------ npy ---

const DTYPES = {
    '<f4': Float32Array, '<f8': Float64Array, '<f2': Float16Array, '|u1': Uint8Array, '|i1': Int8Array, '|b1': Uint8Array,
    '<u2': Uint16Array, '<i2': Int16Array, '<u4': Uint32Array, '<i4': Int32Array, '<u8': BigUint64Array, '<i8': BigInt64Array,
};
const ARRAY_DTYPE = new Map([[Float32Array, '<f4'], [Float64Array, '<f8'], [Float16Array, '<f2'], [Uint8Array, '|u1'],
    [Int8Array, '|i1'], [Uint16Array, '<u2'], [Int16Array, '<i2'], [Uint32Array, '<u4'], [Int32Array, '<i4'],
    [BigUint64Array, '<u8'], [BigInt64Array, '<i8']]);

/** An array as this module holds one: { dtype, shape, data }; the dtype follows from a typed array when not given. */
export function npArray(data, shape = null, dtype = null) {
    dtype = dtype ?? ARRAY_DTYPE.get(data.constructor);
    if (!dtype) throw new TypeError(`npArray: no numpy dtype for a ${data?.constructor?.name}`);
    shape = shape ?? [data.length];
    const n = shape.reduce((a, b) => a * b, 1);
    if (n !== data.length) throw new ValueError(`npArray: shape ${pyStr(shape)} holds ${n} values, the data ${data.length}`);
    return { dtype, shape: [...shape], data };
}

const shapeRepr = (s) => `(${s.join(', ')}${s.length === 1 ? ',' : ''})`;

/** numpy's .npy header (format.write_array's): the magic, the version, the length and the padded dict. */
export function npyHeader(dtype, shape, fortran = false) {
    let header = `{'descr': '${dtype}', 'fortran_order': ${fortran ? 'True' : 'False'}, 'shape': ${shapeRepr(shape)}, }`;
    if (shape.length) header += ' '.repeat(21 - String(shape[fortran ? shape.length - 1 : 0]).length);
    const hb = enc.encode(header);
    const hlen = hb.length + 1;
    let version = 1, lenBytes = 2;
    let pad = 64 - ((8 + 2 + hlen) % 64);
    if (hlen + pad > 0xFFFF) {
        version = 2;
        lenBytes = 4;
        pad = 64 - ((8 + 4 + hlen) % 64);
    }
    const out = new Uint8Array(8 + lenBytes + hlen + pad);
    out.set([0x93, 0x4E, 0x55, 0x4D, 0x50, 0x59, version, 0]);
    const v = new DataView(out.buffer);
    if (lenBytes === 2) v.setUint16(8, hlen + pad, true);
    else v.setUint32(8, hlen + pad, true);
    out.set(hb, 8 + lenBytes);
    out.fill(0x20, 8 + lenBytes + hb.length, out.length - 1);
    out[out.length - 1] = 0x0A;
    return out;
}

/** The header of .npy bytes: { dtype, shape, fortran, offset (where the data starts) }. */
export function parseNpyHeader(bytes) {
    const magic = [0x93, 0x4E, 0x55, 0x4D, 0x50, 0x59];
    for (let i = 0; i < 6; i++) if (bytes[i] !== magic[i]) throw new ValueError('not a .npy array (no \\x93NUMPY magic)');
    const major = bytes[6];
    const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const lenBytes = major === 1 ? 2 : 4;
    const hlen = lenBytes === 2 ? v.getUint16(8, true) : v.getUint32(8, true);
    const text = dec.decode(bytes.subarray(8 + lenBytes, 8 + lenBytes + hlen));
    const descr = /'descr'\s*:\s*'([^']+)'/.exec(text);
    const fo = /'fortran_order'\s*:\s*(True|False)/.exec(text);
    const sh = /'shape'\s*:\s*\(([^)]*)\)/.exec(text);
    if (!descr || !fo || !sh) throw new ValueError(`cannot parse the .npy header ${JSON.stringify(text)}`);
    const shape = sh[1].split(',').map((s) => s.trim()).filter(Boolean).map((s) => parseInt(s, 10));
    return { dtype: descr[1], shape, fortran: fo[1] === 'True', offset: 8 + lenBytes + hlen };
}

function typedFor(dtype, buffer, offset, count) {
    const T = DTYPES[dtype];
    if (!T) throw new ValueError(`dtype ${dtype} is not one this reader takes (${Object.keys(DTYPES).join(', ')})`);
    return new T(buffer, offset, count);
}

/** A GPU field (float32, one channel) of a 2-d float array: float32 as it is, float16 through kernels/grid/half.wgsl
 * (exact: every float16 is a float32). A 1-d array becomes one row. */
export function fieldFromArray(R, a) {
    const [h, w] = a.shape.length === 2 ? a.shape : a.shape.length === 1 ? [1, a.shape[0]] : [0, 0];
    if (!h || !w) throw new ValueError(`fieldFromArray: a 1- or 2-d array is needed, got shape ${pyStr(a.shape)}`);
    if (a.dtype === '<f4') return R.field(h, w, 1, a.data);
    if (a.dtype !== '<f2') throw new ValueError(`fieldFromArray: float32 or float16 data, got ${a.dtype}`);
    const n = h * w, nw = Math.ceil(n / 2);
    const [lh, lw] = listShape(nw);
    const words = new Uint32Array(lh * lw);
    new Uint16Array(words.buffer, 0, n).set(new Uint16Array(a.data.buffer, a.data.byteOffset, n));
    const D = Gd.dummies(R);
    const wf = R.field(lh, lw, 1, words, 'u32');
    const out = R.field(h, w, 1);
    R.run('grid/half', { src: D.f1, words: wf }, { outF: out, outW: D.u1 }, { uMode: 0, uCount: n, uLine: lw });
    wf.destroy();
    return out;
}

/** A float field read back as an array of dtype '<f4' or '<f2' (numpy's float32 -> float16 cast, on the GPU). */
export async function arrayFromField(f, dtype = '<f4') {
    const R = f.runner;
    if (dtype === '<f4') return npArray(await R.read(f), [f.h, f.w]);
    if (dtype !== '<f2') throw new ValueError(`arrayFromField: dtype '<f4' or '<f2', got ${dtype}`);
    const n = f.h * f.w, nw = Math.ceil(n / 2);
    const [lh, lw] = listShape(nw);
    const D = Gd.dummies(R);
    const out = R.field(lh, lw, 1, null, 'u32');
    R.run('grid/half', { src: f, words: D.u1 }, { outF: D.f1, outW: out }, { uMode: 1, uCount: n, uLine: lw },
        [Math.ceil(lw / 16), Math.ceil(lh / 16), 1]);
    const words = await R.read(out);
    out.destroy();
    return npArray(new Float16Array(words.buffer, 0, n), [f.h, f.w], '<f2');
}

/** A .npy file, synchronously (small arrays: a painted shape): { dtype, shape, data }. */
export function readNpySync(path) {
    const bytes = Deno.readFileSync(path);
    const h = parseNpyHeader(bytes);
    if (h.fortran) throw new ValueError(`${path}: a Fortran-order array; C order is needed`);
    const count = h.shape.reduce((a, b) => a * b, 1);
    const T = DTYPES[h.dtype];
    const buf = bytes.buffer.slice(bytes.byteOffset + h.offset, bytes.byteOffset + h.offset + count * T.BYTES_PER_ELEMENT);
    return { dtype: h.dtype, shape: h.shape, data: typedFor(h.dtype, buf, 0, count) };
}


// ------------------------------------------------------------------------------------------------------ npz ---

const ZIP64_LIMIT = 2 ** 31 - 1;                        // Python's zipfile: past it, the zip64 records
const LOCAL_SIG = 0x04034b50, CENTRAL_SIG = 0x02014b50, END_SIG = 0x06054b50, END64_SIG = 0x06064b50, LOC64_SIG = 0x07064b50;
const DOS_DATE = (0 << 9) | (1 << 5) | 1;               // 1980-01-01, ZipInfo's default date_time
const CREATE_SYSTEM = Deno.build.os === 'windows' ? 0 : 3;   // zipfile's, as the Python on the same system writes it
const EXTERNAL_ATTR = 0o600 << 16;

function le(n) {
    const b = new Uint8Array(n);
    return { b, v: new DataView(b.buffer) };
}

// zipfile's flag for a name that is not ASCII (it is then written as UTF-8)
const utfFlag = (name) => ([...name].some((c) => c.codePointAt(0) > 0x7f) ? 0x800 : 0);

function localHeader(name, crc, size, csize, method) {
    const nb = enc.encode(name);
    const utf = utfFlag(name);
    const { b, v } = le(30 + nb.length + 20);
    v.setUint32(0, LOCAL_SIG, true);
    v.setUint8(4, 45);                                  // extract_version: zip64
    v.setUint8(5, 0);
    v.setUint16(6, utf, true);
    v.setUint16(8, method, true);
    v.setUint16(10, 0, true);                           // time 00:00:00
    v.setUint16(12, DOS_DATE, true);
    v.setUint32(14, crc >>> 0, true);
    v.setUint32(18, 0xFFFFFFFF, true);
    v.setUint32(22, 0xFFFFFFFF, true);
    v.setUint16(26, nb.length, true);
    v.setUint16(28, 20, true);
    b.set(nb, 30);
    const o = 30 + nb.length;
    v.setUint16(o, 1, true);                            // the zip64 extra: file_size, compress_size
    v.setUint16(o + 2, 16, true);
    v.setBigUint64(o + 4, BigInt(size), true);
    v.setBigUint64(o + 12, BigInt(csize), true);
    return b;
}

function centralEntry(e) {
    const nb = enc.encode(e.name);
    const utf = utfFlag(e.name);
    const extra = [];
    let size = e.size, csize = e.csize, off = e.offset;
    if (e.size > ZIP64_LIMIT || e.csize > ZIP64_LIMIT) {
        extra.push(e.size, e.csize);
        size = 0xFFFFFFFF;
        csize = 0xFFFFFFFF;
    }
    if (e.offset > ZIP64_LIMIT) {
        extra.push(e.offset);
        off = 0xFFFFFFFF;
    }
    const xl = extra.length ? 4 + 8 * extra.length : 0;
    const { b, v } = le(46 + nb.length + xl);
    v.setUint32(0, CENTRAL_SIG, true);
    v.setUint8(4, 45);                                  // create_version
    v.setUint8(5, CREATE_SYSTEM);
    v.setUint8(6, 45);                                  // extract_version
    v.setUint8(7, 0);
    v.setUint16(8, utf, true);
    v.setUint16(10, e.method, true);
    v.setUint16(12, 0, true);
    v.setUint16(14, DOS_DATE, true);
    v.setUint32(16, e.crc >>> 0, true);
    v.setUint32(20, csize, true);
    v.setUint32(24, size, true);
    v.setUint16(28, nb.length, true);
    v.setUint16(30, xl, true);
    v.setUint16(32, 0, true);
    v.setUint16(34, 0, true);
    v.setUint16(36, 0, true);
    v.setUint32(38, EXTERNAL_ATTR, true);
    v.setUint32(42, off, true);
    b.set(nb, 46);
    if (xl) {
        const o = 46 + nb.length;
        v.setUint16(o, 1, true);
        v.setUint16(o + 2, 8 * extra.length, true);
        extra.forEach((x, i) => v.setBigUint64(o + 4 + 8 * i, BigInt(x), true));
    }
    return b;
}

function endRecords(count, cdSize, cdOffset, pos2) {
    const parts = [];
    if (count > 0xFFFF || cdOffset > ZIP64_LIMIT || cdSize > ZIP64_LIMIT) {
        const z = le(56);
        z.v.setUint32(0, END64_SIG, true);
        z.v.setBigUint64(4, 44n, true);
        z.v.setUint16(12, 45, true);
        z.v.setUint16(14, 45, true);
        z.v.setUint32(16, 0, true);
        z.v.setUint32(20, 0, true);
        z.v.setBigUint64(24, BigInt(count), true);
        z.v.setBigUint64(32, BigInt(count), true);
        z.v.setBigUint64(40, BigInt(cdSize), true);
        z.v.setBigUint64(48, BigInt(cdOffset), true);
        const l = le(20);
        l.v.setUint32(0, LOC64_SIG, true);
        l.v.setUint32(4, 0, true);
        l.v.setBigUint64(8, BigInt(pos2), true);
        l.v.setUint32(16, 1, true);
        parts.push(z.b, l.b);
        count = Math.min(count, 0xFFFF);
        cdSize = Math.min(cdSize, 0xFFFFFFFF);
        cdOffset = Math.min(cdOffset, 0xFFFFFFFF);
    }
    const e = le(22);
    e.v.setUint32(0, END_SIG, true);
    e.v.setUint16(8, count, true);
    e.v.setUint16(10, count, true);
    e.v.setUint32(12, cdSize, true);
    e.v.setUint32(16, cdOffset, true);
    parts.push(e.b);
    return concat(parts);
}

const bytesOf = (a) => new Uint8Array(a.data.buffer, a.data.byteOffset, a.data.byteLength);

/** Write arrays as np.savez does (opts.compress: as np.savez_compressed), entry by entry: `arrays` is an object or
 * Map (name -> array, or a function giving one, so the caller need not hold them all), or a list of [name, array]
 * pairs; a name gets '.npy'. A typed array alone is a 1-d array; a Float32Array with opts.shapes[name] takes that
 * shape. Returns the file's size. */
export async function writeNpz(path, arrays, opts = {}) {
    const list = arrays instanceof Map ? [...arrays.entries()] : Array.isArray(arrays) ? arrays : Object.entries(arrays);
    await Deno.mkdir(dirOf(path), { recursive: true });
    const file = await Deno.open(path, { write: true, create: true, truncate: true });
    const entries = [];
    let pos = 0;
    try {
        for (const [key, value] of list) {
            let a = typeof value === 'function' ? await value() : value;
            if (ArrayBuffer.isView(a)) a = npArray(a, opts.shapes?.[key] ?? null);
            const head = npyHeader(a.dtype, a.shape);
            const body = bytesOf(a);
            const name = key + '.npy';
            let crc = crc32(head);
            crc = crc32(body, crc);
            const size = head.length + body.length;
            let data = null, csize = size;
            if (opts.compress) {
                data = await streamBytes(concat([head, body]), new CompressionStream('deflate-raw'));
                csize = data.length;
            }
            const lh = localHeader(name, crc, size, csize, opts.compress ? 8 : 0);
            entries.push({ name, crc, size, csize, offset: pos, method: opts.compress ? 8 : 0 });
            await writeAll(file, lh);
            if (data) await writeAll(file, data);
            else {
                await writeAll(file, head);
                await writeAll(file, body);
            }
            pos += lh.length + csize;
        }
        const cd = entries.map(centralEntry);
        const cdSize = cd.reduce((s, b) => s + b.length, 0);
        for (const b of cd) await writeAll(file, b);
        const tail = endRecords(entries.length, cdSize, pos, pos + cdSize);
        await writeAll(file, tail);
        return pos + cdSize + tail.length;
    } finally {
        file.close();
    }
}

/** The directory of an npz: [{ name (without .npy), method, crc, size, csize, offset (the local header's) }], in the
 * file's order. */
export async function npzDirectory(path, file = null) {
    const own = !file;
    file = file ?? await Deno.open(path, { read: true });
    try {
        const total = (await file.stat()).size;
        const tailLen = Math.min(total, 22 + 0xFFFF);
        const tail = new Uint8Array(tailLen);
        await file.seek(total - tailLen, Deno.SeekMode.Start);
        await readExactly(file, tail, path);
        const tv = new DataView(tail.buffer);
        let e = -1;
        for (let i = tailLen - 22; i >= 0; i--) {
            if (tv.getUint32(i, true) === END_SIG) {
                e = i;
                break;
            }
        }
        if (e < 0) throw new ValueError(`${path}: not a zip file (no end of central directory)`);
        let count = tv.getUint16(e + 10, true), cdSize = tv.getUint32(e + 12, true), cdOffset = tv.getUint32(e + 16, true);
        if (e >= 20 && tv.getUint32(e - 20, true) === LOC64_SIG) {
            const at = Number(tv.getBigUint64(e - 20 + 8, true));
            const z = new Uint8Array(56);
            await file.seek(at, Deno.SeekMode.Start);
            await readExactly(file, z, path);
            const zv = new DataView(z.buffer);
            if (zv.getUint32(0, true) !== END64_SIG) throw new ValueError(`${path}: a zip64 locator without its record`);
            count = Number(zv.getBigUint64(32, true));
            cdSize = Number(zv.getBigUint64(40, true));
            cdOffset = Number(zv.getBigUint64(48, true));
        }
        const cd = new Uint8Array(cdSize);
        await file.seek(cdOffset, Deno.SeekMode.Start);
        await readExactly(file, cd, path);
        const v = new DataView(cd.buffer);
        const out = [];
        let o = 0;
        for (let k = 0; k < count; k++) {
            if (v.getUint32(o, true) !== CENTRAL_SIG) throw new ValueError(`${path}: a broken central directory at entry ${k}`);
            const method = v.getUint16(o + 10, true), crc = v.getUint32(o + 16, true);
            let csize = v.getUint32(o + 20, true), size = v.getUint32(o + 24, true);
            const nl = v.getUint16(o + 28, true), xl = v.getUint16(o + 30, true), cl = v.getUint16(o + 32, true);
            let offset = v.getUint32(o + 42, true);
            const name = dec.decode(cd.subarray(o + 46, o + 46 + nl));
            let x = o + 46 + nl;
            const xend = x + xl;
            while (x + 4 <= xend) {
                const tag = v.getUint16(x, true), ln = v.getUint16(x + 2, true);
                if (tag === 1) {
                    let q = x + 4;
                    if (size === 0xFFFFFFFF) { size = Number(v.getBigUint64(q, true)); q += 8; }
                    if (csize === 0xFFFFFFFF) { csize = Number(v.getBigUint64(q, true)); q += 8; }
                    if (offset === 0xFFFFFFFF) { offset = Number(v.getBigUint64(q, true)); q += 8; }
                }
                x += 4 + ln;
            }
            out.push({ name: name.endsWith('.npy') ? name.slice(0, -4) : name, file: name, method, crc, size, csize, offset });
            o = xend + cl;
        }
        return out;
    } finally {
        if (own) file.close();
    }
}

async function readEntry(file, e, path, verify) {
    const lh = new Uint8Array(30);
    await file.seek(e.offset, Deno.SeekMode.Start);
    await readExactly(file, lh, path);
    const lv = new DataView(lh.buffer);
    if (lv.getUint32(0, true) !== LOCAL_SIG) throw new ValueError(`${path}: no local header for ${e.file}`);
    const start = e.offset + 30 + lv.getUint16(26, true) + lv.getUint16(28, true);
    let raw;
    if (e.method === 0) {
        raw = new Uint8Array(e.size);
        await file.seek(start, Deno.SeekMode.Start);
        await readExactly(file, raw, path);
    } else if (e.method === 8) {
        const comp = new Uint8Array(e.csize);
        await file.seek(start, Deno.SeekMode.Start);
        await readExactly(file, comp, path);
        raw = await streamBytes(comp, new DecompressionStream('deflate-raw'));
    } else {
        throw new ValueError(`${path}: entry ${e.file} uses zip method ${e.method}; stored (0) or deflated (8) are read`);
    }
    if (verify && (crc32(raw) >>> 0) !== (e.crc >>> 0)) throw new ValueError(`${path}: Bad CRC-32 for file '${e.file}'`);
    const h = parseNpyHeader(raw);
    if (h.fortran) throw new ValueError(`${path}: ${e.file} is a Fortran-order array; C order is needed`);
    const count = h.shape.reduce((a, b) => a * b, 1);
    const T = DTYPES[h.dtype];
    if (!T) throw new ValueError(`${path}: ${e.file}: dtype ${h.dtype} is not one this reader takes`);
    let data;
    if (h.offset % T.BYTES_PER_ELEMENT === 0) {
        data = new T(raw.buffer, raw.byteOffset + h.offset, count);
    } else {
        data = new T(raw.buffer.slice(raw.byteOffset + h.offset, raw.byteOffset + h.offset + count * T.BYTES_PER_ELEMENT));
    }
    return { dtype: h.dtype, shape: h.shape, data };
}

/** The arrays of an npz, one entry at a time: for await (const [name, array] of iterNpz(path)). opts.names limits
 * which; opts.verify (true) checks each entry's CRC-32, as np.load does. */
export async function* iterNpz(path, opts = {}) {
    const file = await Deno.open(path, { read: true });
    try {
        const dir = await npzDirectory(path, file);
        for (const e of dir) {
            if (opts.names && !opts.names.includes(e.name)) continue;
            yield [e.name, await readEntry(file, e, path, opts.verify !== false)];
        }
    } finally {
        file.close();
    }
}

/** Every array of an npz (or opts.names), as an object name -> array, in the file's order. */
export async function readNpz(path, opts = {}) {
    const out = {};
    for await (const [name, a] of iterNpz(path, opts)) out[name] = a;
    return out;
}

export {
    exportHeightmap as export_heightmap, readHeightmap as read_heightmap, exportMask as export_mask,
    readPng as read_png, writePng as write_png, encodePng as encode_png, decodePng as decode_png,
    normaliseHeights as normalise_heights, toU8 as to_u8, encodeR32 as encode_r32, encodeR16 as encode_r16,
};
