// eidoverse/motion_vectors_test.mjs — the motion-file encoder (motion_vectors.js) without a GPU: the .npz it writes is
// one deflated xyzw.npy member with a valid CRC, a numpy v1.0 header for a (4, H, W) float16 array whose data starts
// 64-byte aligned, and the half-float bits exactly as given.
//   deno test --no-check --allow-read --node-modules-dir=manual --no-lock eidoverse/motion_vectors_test.mjs
import zlib from 'node:zlib';
import { encodeMotionNpz } from './motion_vectors.js';

function assert(ok, what) {
    if (!ok) throw new Error(what);
}

Deno.test('encodeMotionNpz: a zip of one deflated xyzw.npy, float16 (4, H, W), bits kept', () => {
    const width = 7, height = 3;
    const halves = new Uint16Array(4 * width * height);
    for (let i = 0; i < halves.length; i++) halves[i] = (i * 2654435761) & 0x7bff;   // finite half bits
    const zip = encodeMotionNpz(halves, width, height);
    const dv = new DataView(zip.buffer, zip.byteOffset, zip.byteLength);
    assert(dv.getUint32(0, true) === 0x04034b50, 'local file header signature');
    assert(dv.getUint16(8, true) === 8, 'deflated member');
    const crc = dv.getUint32(14, true), csize = dv.getUint32(18, true), usize = dv.getUint32(22, true);
    const nameLength = dv.getUint16(26, true);
    assert(new TextDecoder().decode(zip.subarray(30, 30 + nameLength)) === 'xyzw.npy', 'member name');
    const npy = new Uint8Array(zlib.inflateRawSync(zip.subarray(30 + nameLength, 30 + nameLength + csize)));
    assert(npy.length === usize, 'uncompressed size');
    assert((zlib.crc32(npy) >>> 0) === crc, 'CRC-32');
    const end = dv.getUint32(zip.length - 22, true), cdOffset = dv.getUint32(zip.length - 6, true);
    assert(end === 0x06054b50 && dv.getUint32(cdOffset, true) === 0x02014b50, 'central directory and end record');
    assert(npy[0] === 0x93 && new TextDecoder().decode(npy.subarray(1, 6)) === 'NUMPY' && npy[6] === 1, 'npy v1.0 magic');
    const headerLength = npy[8] | (npy[9] << 8);
    const header = new TextDecoder().decode(npy.subarray(10, 10 + headerLength));
    assert(header.startsWith(`{'descr': '<f2', 'fortran_order': False, 'shape': (4, ${height}, ${width}), }`), header);
    assert((10 + headerLength) % 64 === 0 && header.endsWith('\n'), 'data 64-byte aligned');
    const data = new Uint16Array(npy.slice(10 + headerLength).buffer);
    assert(data.length === halves.length && data.every((v, i) => v === halves[i]), 'the half-float bits as given');
});
