// eidoverse/motion_vectors.js — per-pixel motion vectors from the renderer, written as the motion files DLSS 5's
// temporal path reads (dlss5nr/; tools-guides/postprocessing.md, "DLSS 5 over a finished film").
//
// The runner turns it on with a scene config key: "motionVectors": "work/<id>/motion". The auto-enhance scene pass
// then carries one more MRT attachment, three's velocity node (the motion TRAA and motion blur use: camera motion,
// object transforms, skinned meshes and instanced meshes, each against its own previous frame), scaled to pixels;
// after every frame's render the runner reads that attachment back and writes <dir>/<frame:04d>.npz, the video's own
// 0-based frame number, in the motion-file layout of dlss5nr/motion_npz.py: one float16 array `xyzw` (4, H, W), rows
// top-down, X and Y pointing from a pixel to where its surface was a frame earlier (Y up), Z and W zero. That is
// Blender's Vector-pass layout, so dlss5nr.py reads both the same way: --convention "+X -Y" --offset 0.
//
// What three's velocity does not follow: vertex motion made in a material's positionNode (wind on the flora, cloth,
// GPU-driven particles and fluids) and morph targets are measured from the mesh's own unmoved vertices, so they read as
// motion they do not have. For a film full of those, dlss5nr/flow_motion.py (optical flow from the frames) is the
// better source; dlss5nr/motion_check.py's warp error on the film says which source fits it better.
//
//   import { velocityAttachment, createMotionVectorWriter, encodeMotionNpz } from './motion_vectors.js';
//   mrt({ output, ..., velocity: velocityAttachment(THREE, alpha) })      // in the scene pass
//   const writer = createMotionVectorWriter({ renderer, pass: scenePass, dir, width, height });
//   await writer.capture(frameIndex);   // after the frame's render
//   await writer.close();               // { frames, bytes } once every file is on disk

import zlib from 'node:zlib';

// The scene pass attachment: three's velocity (NDC, current minus previous) in pixels pointing back to the previous
// frame (x right, y up), carried with the material's alpha so transparent surfaces blend into it by their visibility.
export function velocityAttachment(THREE, alpha = 1) {
    const { velocity, screenSize, vec4 } = THREE;
    return vec4(velocity.x.mul(screenSize.x).mul(-0.5), velocity.y.mul(screenSize.y).mul(-0.5), 0, alpha);
}

const NAME = new TextEncoder().encode('xyzw.npy');

// The .npz bytes of a (4, height, width) float16 array given as raw half-float bits (C order): one deflated member,
// xyzw.npy, as numpy's savez_compressed writes it (np.load reads it).
export function encodeMotionNpz(halves, width, height) {
    let header = `{'descr': '<f2', 'fortran_order': False, 'shape': (4, ${height}, ${width}), }`;
    header += ' '.repeat(63 - ((10 + header.length) % 64)) + '\n';           // the data starts 64-byte aligned
    const head = new TextEncoder().encode(header);
    const npy = new Uint8Array(10 + head.length + halves.byteLength);
    npy.set([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 1, 0, head.length & 255, head.length >> 8]);   // \x93NUMPY v1.0
    npy.set(head, 10);
    npy.set(new Uint8Array(halves.buffer, halves.byteOffset, halves.byteLength), 10 + head.length);
    const crc = zlib.crc32(npy) >>> 0;
    const body = new Uint8Array(zlib.deflateRawSync(npy, { level: 1 }));
    const local = new DataView(new ArrayBuffer(30));
    const central = new DataView(new ArrayBuffer(46));
    const end = new DataView(new ArrayBuffer(22));
    // local file header: signature, version 2.0, no flags, deflate, 1980-01-01 00:00, crc, sizes, the name's length
    [[0, 0x04034b50, 4], [4, 20, 2], [6, 0, 2], [8, 8, 2], [10, 0, 2], [12, 33, 2], [14, crc, 4],
     [18, body.length, 4], [22, npy.length, 4], [26, NAME.length, 2], [28, 0, 2]].forEach(([o, v, n]) =>
        n === 4 ? local.setUint32(o, v, true) : local.setUint16(o, v, true));
    // central directory entry: the same, plus where the local header is (offset 0)
    [[0, 0x02014b50, 4], [4, 20, 2], [6, 20, 2], [8, 0, 2], [10, 8, 2], [12, 0, 2], [14, 33, 2], [16, crc, 4],
     [20, body.length, 4], [24, npy.length, 4], [28, NAME.length, 2], [30, 0, 2], [32, 0, 2], [34, 0, 2], [36, 0, 2],
     [38, 0, 4], [42, 0, 4]].forEach(([o, v, n]) => n === 4 ? central.setUint32(o, v, true) : central.setUint16(o, v, true));
    const cdOffset = 30 + NAME.length + body.length;
    [[0, 0x06054b50, 4], [4, 0, 2], [6, 0, 2], [8, 1, 2], [10, 1, 2], [12, 46 + NAME.length, 4], [16, cdOffset, 4],
     [20, 0, 2]].forEach(([o, v, n]) => n === 4 ? end.setUint32(o, v, true) : end.setUint16(o, v, true));
    const out = new Uint8Array(cdOffset + 46 + NAME.length + 22);
    let at = 0;
    for (const part of [new Uint8Array(local.buffer), NAME, body, new Uint8Array(central.buffer), NAME, new Uint8Array(end.buffer)]) {
        out.set(part, at);
        at += part.length;
    }
    return out;
}

// Reads the scene pass's velocity attachment after each frame and writes its motion file; files are written while the
// next frames render (a few in flight at most).
export function createMotionVectorWriter({ renderer, pass, dir, width, height, attachment = 'velocity' }) {
    const texture = pass.getTexture(attachment);
    const index = pass.renderTarget.textures.indexOf(texture);
    if (index < 0) throw new Error(`motion vectors: the scene pass has no '${attachment}' attachment`);
    Deno.mkdirSync(dir, { recursive: true });
    const plane = width * height;
    const pending = new Set();
    let frames = 0, bytes = 0;
    async function write(frameIndex, raw) {
        // raw: RGBA half bits, rows padded to 256 bytes (WebGPU's copy alignment), top row first
        const stride = Math.ceil((width * 8) / 256) * 256 / 2;
        const halves = new Uint16Array(4 * plane);                      // X plane, Y plane, Z and W left zero
        for (let y = 0; y < height; y++) {
            const row = y * stride, o = y * width;
            for (let x = 0; x < width; x++) {
                halves[o + x] = raw[row + x * 4];
                halves[plane + o + x] = raw[row + x * 4 + 1];
            }
        }
        const npz = encodeMotionNpz(halves, width, height);
        const path = `${dir}/${String(frameIndex).padStart(4, '0')}.npz`;
        await Deno.writeFile(path + '.part', npz);
        await Deno.rename(path + '.part', path);
        frames += 1;
        bytes += npz.length;
    }
    return {
        dir,
        async capture(frameIndex) {
            while (pending.size >= 4) await Promise.race(pending);
            const raw = await renderer.readRenderTargetPixelsAsync(pass.renderTarget, 0, 0, width, height, index);
            const job = write(frameIndex, raw).finally(() => pending.delete(job));
            pending.add(job);
        },
        async close() {
            await Promise.all(pending);
            return { frames, bytes };
        },
    };
}
