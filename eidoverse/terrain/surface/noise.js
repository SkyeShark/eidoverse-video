// Port of blender/eidoblend/terrain/surface/noise.glsl at d67f19e (its twin, noise.py, is the oracle).
//
// Blender's shader noise, for the surface bake and the material (SURFACING_DESIGN.md 2.1, 2.3; PORT_PLAN.md 3.5): the
// Noise Texture's fBM (3D and 4D, normalised: its Fac) and the Voronoi texture's F1 cell colour (2D and 3D), with
// Blender's own hashes (Bob Jenkins' lookup3, Cycles' util/hash.h) and Perlin noise (Cycles' svm/noise.h, Apache-2.0;
// Blender's GLSL is the same arithmetic, GPL-2.0-or-later; both compatible with this AGPL-3.0 repository, their
// notices kept here: Cycles is Copyright 2011-2022 Blender Foundation, Apache License 2.0; Blender's GLSL noise is
// Copyright Blender Foundation, GNU General Public License 2.0 or later). A term evaluated with these equals the
// material's Noise and Voronoi nodes at the same coordinates.
//
// Written once against build/ops.js (the backends: NUM32 the float32 oracle, TSL the material's nodes, WGSL the
// bake's compute kernels), statement for statement from noise.glsl, so the same source runs in all three:
//
//     import { noise } from './surface/noise.js';
//     import * as ops from '../build/ops.js';
//     const N = noise(ops.NUM32);               // or noise(ops.TSL(tsl)), noise(ops.WGSL())
//     N.noiseNode3(x, y, z, scale, detail, roughness)          // the Noise Texture node's Fac, 3D
//     N.noiseNode4(x, y, z, w, scale, detail, roughness)       // 4D
//     N.voronoiF1Colour2(x, y, scale, randomness)              // the Voronoi node's F1 Color (a vec3), 2D
//     N.voronoiF1Colour3(x, y, z, scale, randomness)           // 3D
//     N.hash2(kx, ky), N.hash3(...), N.hash4(...)              // lookup3 on uint32 (bit for bit in every backend)
//     N.perlin3(x, y, z), N.perlin4(...), N.snoise3(...), N.snoise4(...), N.fbm3(...), N.fbm4(...)
//
// Where this differs from noise.glsl, and why (each checked against noise.py and Blender's own node renders,
// tests/surface_data/noise_test.mjs):
//   - Coordinates are scalars (x, y, z[, w]), not vec3 / vec4: ops' functions take scalar parameters in every backend.
//   - bn_mix and bn_final's inout uints are returned as [a, b, c]; ivec2 / ivec3 (the Voronoi hashes) as arrays of
//     i32s. The arithmetic is the GLSL's, in its order.
//   - The `if (rmd != 0)` of the fBM computes the extra octave and selects (select()): the same value either way.
//   - The Voronoi loops (3 x 3, 3 x 3 x 3) are written out (a JavaScript loop when the function is built), the running
//     best and its cell as selects: `if (d < best)` keeps the first nearest, as the GLSL.

const MEMO = new WeakMap();

/** The noise functions on one backend (memoised per backend object). */
export function noise(ops) {
    if (MEMO.has(ops)) return MEMO.get(ops);
    const o = ops;
    const K = (n) => o.u(n >>> 0);

    // uint bn_rot(uint x, uint k) { return (x << k) | (x >> (32u - k)); }
    const rot = (x, k) => o.uor(o.ushl(x, k), o.ushr(x, 32 - k));

    // bn_mix and bn_final: Jenkins' lookup3 rounds on three uints
    const mix = (a, b, c) => {
        a = o.usub(a, c); a = o.uxor(a, rot(c, 4)); c = o.uadd(c, b);
        b = o.usub(b, a); b = o.uxor(b, rot(a, 6)); a = o.uadd(a, c);
        c = o.usub(c, b); c = o.uxor(c, rot(b, 8)); b = o.uadd(b, a);
        a = o.usub(a, c); a = o.uxor(a, rot(c, 16)); c = o.uadd(c, b);
        b = o.usub(b, a); b = o.uxor(b, rot(a, 19)); a = o.uadd(a, c);
        c = o.usub(c, b); c = o.uxor(c, rot(b, 4)); b = o.uadd(b, a);
        return [a, b, c];
    };
    const final = (a, b, c) => {
        c = o.uxor(c, b); c = o.usub(c, rot(b, 14));
        a = o.uxor(a, c); a = o.usub(a, rot(c, 11));
        b = o.uxor(b, a); b = o.usub(b, rot(a, 25));
        c = o.uxor(c, b); c = o.usub(c, rot(b, 16));
        a = o.uxor(a, c); a = o.usub(a, rot(c, 4));
        b = o.uxor(b, a); b = o.usub(b, rot(a, 14));
        c = o.uxor(c, b); c = o.usub(c, rot(b, 24));
        return [a, b, c];
    };

    const hash2 = o.fn('bn_hash2', [['kx', 'uint'], ['ky', 'uint']], 'uint', (o_, kx, ky) => {
        let a = K(0xdeadbeef + (2 << 2) + 13);
        let b = a, c = a;
        b = o.uadd(b, ky);
        a = o.uadd(a, kx);
        [a, b, c] = final(a, b, c);
        return c;
    });

    const hash3 = o.fn('bn_hash3', [['kx', 'uint'], ['ky', 'uint'], ['kz', 'uint']], 'uint', (o_, kx, ky, kz) => {
        let a = K(0xdeadbeef + (3 << 2) + 13);
        let b = a, c = a;
        c = o.uadd(c, kz);
        b = o.uadd(b, ky);
        a = o.uadd(a, kx);
        [a, b, c] = final(a, b, c);
        return c;
    });

    const hash4 = o.fn('bn_hash4', [['kx', 'uint'], ['ky', 'uint'], ['kz', 'uint'], ['kw', 'uint']], 'uint',
        (o_, kx, ky, kz, kw) => {
            let a = K(0xdeadbeef + (4 << 2) + 13);
            let b = a, c = a;
            a = o.uadd(a, kx);
            b = o.uadd(b, ky);
            c = o.uadd(c, kz);
            [a, b, c] = mix(a, b, c);
            a = o.uadd(a, kw);
            [a, b, c] = final(a, b, c);
            return c;
        });

    // float bn_u2f(uint h) { return float(h) / float(0xFFFFFFFFu); }
    const u2f = (h) => o.div(o.utof(h), 4294967295.0);

    // the Voronoi texture's hashes of integer cell indices (Blender 4.1+: the PCG hashes of "Hash Functions for GPU
    // Rendering", JCGT 2020, in signed integers)
    const C1 = 1664525, C2 = 1013904223;
    const pcg2d = (vx, vy) => {
        vx = o.iadd(o.imul(vx, C1), C2);
        vy = o.iadd(o.imul(vy, C1), C2);
        vx = o.iadd(vx, o.imul(vy, C1));
        vy = o.iadd(vy, o.imul(vx, C1));
        vx = o.ixor(vx, o.ishr(vx, 16));
        vy = o.ixor(vy, o.ishr(vy, 16));
        vx = o.iadd(vx, o.imul(vy, C1));
        vy = o.iadd(vy, o.imul(vx, C1));
        return [o.iand(vx, 0x7FFFFFFF), o.iand(vy, 0x7FFFFFFF)];
    };
    const pcg3d = (vx, vy, vz) => {
        vx = o.iadd(o.imul(vx, C1), C2);
        vy = o.iadd(o.imul(vy, C1), C2);
        vz = o.iadd(o.imul(vz, C1), C2);
        vx = o.iadd(vx, o.imul(vy, vz));
        vy = o.iadd(vy, o.imul(vz, vx));
        vz = o.iadd(vz, o.imul(vx, vy));
        vx = o.ixor(vx, o.ishr(vx, 16));
        vy = o.ixor(vy, o.ishr(vy, 16));
        vz = o.ixor(vz, o.ishr(vz, 16));
        vx = o.iadd(vx, o.imul(vy, vz));
        vy = o.iadd(vy, o.imul(vz, vx));
        vz = o.iadd(vz, o.imul(vx, vy));
        return [o.iand(vx, 0x7FFFFFFF), o.iand(vy, 0x7FFFFFFF), o.iand(vz, 0x7FFFFFFF)];
    };
    const INV31 = 1.0 / 2147483648.0;                    // 1.0 / float(0x7FFFFFFF): float(2^31 - 1) is 2^31
    const hashI2F2 = (kx, ky) => pcg2d(kx, ky).map((v) => o.mul(o.itof(v), INV31));
    const hashI2F3 = (kx, ky) => pcg3d(kx, ky, o.i(0)).map((v) => o.mul(o.itof(v), INV31));
    const hashI3F3 = (kx, ky, kz) => pcg3d(kx, ky, kz).map((v) => o.mul(o.itof(v), INV31));

    const fade = (t) => o.mul(o.mul(o.mul(t, t), t), o.add(o.mul(t, o.sub(o.mul(t, 6.0), 15.0)), 10.0));
    const negateIf = (v, c) => o.select(o.une(c, o.u(0)), o.neg(v), v);

    const grad3 = (hash, x, y, z) => {
        const h = o.uand(hash, o.u(15));
        const u = o.select(o.ult(h, o.u(8)), x, y);
        const vt = o.select(o.or(o.ueq(h, o.u(12)), o.ueq(h, o.u(14))), x, z);
        const v = o.select(o.ult(h, o.u(4)), y, vt);
        return o.add(negateIf(u, o.uand(h, o.u(1))), negateIf(v, o.uand(h, o.u(2))));
    };

    const grad4 = (hash, x, y, z, w) => {
        const h = o.uand(hash, o.u(31));
        const u = o.select(o.ult(h, o.u(24)), x, y);
        const v = o.select(o.ult(h, o.u(16)), y, z);
        const s = o.select(o.ult(h, o.u(8)), z, w);
        return o.add(o.add(negateIf(u, o.uand(h, o.u(1))), negateIf(v, o.uand(h, o.u(2)))), negateIf(s, o.uand(h, o.u(4))));
    };

    const triMix = (v0, v1, v2, v3, v4, v5, v6, v7, x, y, z) => {
        const x1 = o.sub(1.0, x);
        const y1 = o.sub(1.0, y);
        const z1 = o.sub(1.0, z);
        return o.add(o.mul(z1, o.add(o.mul(y1, o.add(o.mul(v0, x1), o.mul(v1, x))), o.mul(y, o.add(o.mul(v2, x1), o.mul(v3, x))))),
            o.mul(z, o.add(o.mul(y1, o.add(o.mul(v4, x1), o.mul(v5, x))), o.mul(y, o.add(o.mul(v6, x1), o.mul(v7, x))))));
    };

    const perlin3 = o.fn('bn_perlin3', [['px', 'float'], ['py', 'float'], ['pz', 'float']], 'float', (o_, px, py, pz) => {
        const flx = o.floor(px), fly = o.floor(py), flz = o.floor(pz);
        const X = o.itou(o.ftoi(flx)), Y = o.itou(o.ftoi(fly)), Z = o.itou(o.ftoi(flz));
        const fx = o.sub(px, flx), fy = o.sub(py, fly), fz = o.sub(pz, flz);
        const u = fade(fx), v = fade(fy), w = fade(fz);
        const one = o.u(1);
        const X1 = o.uadd(X, one), Y1 = o.uadd(Y, one), Z1 = o.uadd(Z, one);
        const fx1 = o.sub(fx, 1.0), fy1 = o.sub(fy, 1.0), fz1 = o.sub(fz, 1.0);
        return triMix(grad3(hash3(X, Y, Z), fx, fy, fz),
            grad3(hash3(X1, Y, Z), fx1, fy, fz),
            grad3(hash3(X, Y1, Z), fx, fy1, fz),
            grad3(hash3(X1, Y1, Z), fx1, fy1, fz),
            grad3(hash3(X, Y, Z1), fx, fy, fz1),
            grad3(hash3(X1, Y, Z1), fx1, fy, fz1),
            grad3(hash3(X, Y1, Z1), fx, fy1, fz1),
            grad3(hash3(X1, Y1, Z1), fx1, fy1, fz1), u, v, w);
    });

    const perlin4 = o.fn('bn_perlin4', [['px', 'float'], ['py', 'float'], ['pz', 'float'], ['pw', 'float']], 'float',
        (o_, px, py, pz, pw) => {
            const flx = o.floor(px), fly = o.floor(py), flz = o.floor(pz), flw = o.floor(pw);
            const X = o.itou(o.ftoi(flx)), Y = o.itou(o.ftoi(fly)), Z = o.itou(o.ftoi(flz)), W = o.itou(o.ftoi(flw));
            const fx = o.sub(px, flx), fy = o.sub(py, fly), fz = o.sub(pz, flz), fw = o.sub(pw, flw);
            const u = fade(fx), v = fade(fy), t = fade(fz), s = fade(fw);
            const one = o.u(1);
            const X1 = o.uadd(X, one), Y1 = o.uadd(Y, one), Z1 = o.uadd(Z, one), W1 = o.uadd(W, one);
            const fx1 = o.sub(fx, 1.0), fy1 = o.sub(fy, 1.0), fz1 = o.sub(fz, 1.0), fw1 = o.sub(fw, 1.0);
            const a = triMix(grad4(hash4(X, Y, Z, W), fx, fy, fz, fw),
                grad4(hash4(X1, Y, Z, W), fx1, fy, fz, fw),
                grad4(hash4(X, Y1, Z, W), fx, fy1, fz, fw),
                grad4(hash4(X1, Y1, Z, W), fx1, fy1, fz, fw),
                grad4(hash4(X, Y, Z1, W), fx, fy, fz1, fw),
                grad4(hash4(X1, Y, Z1, W), fx1, fy, fz1, fw),
                grad4(hash4(X, Y1, Z1, W), fx, fy1, fz1, fw),
                grad4(hash4(X1, Y1, Z1, W), fx1, fy1, fz1, fw), u, v, t);
            const b = triMix(grad4(hash4(X, Y, Z, W1), fx, fy, fz, fw1),
                grad4(hash4(X1, Y, Z, W1), fx1, fy, fz, fw1),
                grad4(hash4(X, Y1, Z, W1), fx, fy1, fz, fw1),
                grad4(hash4(X1, Y1, Z, W1), fx1, fy1, fz, fw1),
                grad4(hash4(X, Y, Z1, W1), fx, fy, fz1, fw1),
                grad4(hash4(X1, Y, Z1, W1), fx1, fy, fz1, fw1),
                grad4(hash4(X, Y1, Z1, W1), fx, fy1, fz1, fw1),
                grad4(hash4(X1, Y1, Z1, W1), fx1, fy1, fz1, fw1), u, v, t);
            return o.mix(a, b, s);
        });

    // C's fmod: a - b trunc(a / b)
    const fmod = (a, b) => o.sub(a, o.mul(b, o.trunc(o.div(a, b))));

    // the safe signed noise: repeats every 100000 on each axis (Blender's guard against float precision)
    const pcOf = (a) => o.mul(0.5, o.select(o.ge(o.abs(a), 1000000.0), 1.0, 0.0));
    const snoise3 = (x, y, z) => {
        const qx = o.add(fmod(x, 100000.0), pcOf(x));
        const qy = o.add(fmod(y, 100000.0), pcOf(y));
        const qz = o.add(fmod(z, 100000.0), pcOf(z));
        return o.mul(0.9820, perlin3(qx, qy, qz));
    };
    const snoise4 = (x, y, z, w) => {
        const qx = o.add(fmod(x, 100000.0), pcOf(x));
        const qy = o.add(fmod(y, 100000.0), pcOf(y));
        const qz = o.add(fmod(z, 100000.0), pcOf(z));
        const qw = o.add(fmod(w, 100000.0), pcOf(w));
        return o.mul(0.8344, perlin4(qx, qy, qz, qw));
    };

    // the Noise Texture's fBM, normalised (its Fac), lacunarity 2
    const fbmOf = (sn, dims) => (o_, ...a) => {
        const p = a.slice(0, dims);
        let detail = a[dims], roughness = a[dims + 1];
        detail = o.clamp(detail, 0.0, 15.0);
        roughness = o.max(roughness, 0.0);
        const fscale = o.vr('float', 1.0), amp = o.vr('float', 1.0), maxamp = o.vr('float', 0.0), sum = o.vr('float', 0.0);
        o.loop(0, o.iadd(o.ftoi(detail), 1), () => {
            const t = sn(...p.map((c) => o.mul(fscale.get(), c)));
            sum.set(o.add(sum.get(), o.mul(t, amp.get())));
            maxamp.set(o.add(maxamp.get(), amp.get()));
            amp.set(o.mul(amp.get(), roughness));
            fscale.set(o.mul(fscale.get(), 2.0));
        });
        const rmd = o.sub(detail, o.floor(detail));
        const t = sn(...p.map((c) => o.mul(fscale.get(), c)));
        const sum2 = o.add(sum.get(), o.mul(t, amp.get()));
        const plain = o.add(o.div(o.mul(0.5, sum.get()), maxamp.get()), 0.5);
        const blended = o.mix(plain, o.add(o.div(o.mul(0.5, sum2), o.add(maxamp.get(), amp.get())), 0.5), rmd);
        return o.select(o.ne(rmd, 0.0), blended, plain);
    };
    const fbm3 = o.fn('bn_fbm3', [['px', 'float'], ['py', 'float'], ['pz', 'float'], ['detail', 'float'], ['roughness', 'float']],
        'float', fbmOf(snoise3, 3));
    const fbm4 = o.fn('bn_fbm4', [['px', 'float'], ['py', 'float'], ['pz', 'float'], ['pw', 'float'], ['detail', 'float'],
        ['roughness', 'float']], 'float', fbmOf(snoise4, 4));

    // the Noise Texture node's Fac: 3D (Vector x Scale) and 4D ((Vector, W) x Scale), fBM, no distortion
    const noiseNode3 = (x, y, z, scale, detail, roughness) => fbm3(o.mul(x, scale), o.mul(y, scale), o.mul(z, scale), detail, roughness);
    const noiseNode4 = (x, y, z, w, scale, detail, roughness) =>
        fbm4(o.mul(x, scale), o.mul(y, scale), o.mul(z, scale), o.mul(w, scale), detail, roughness);

    // the Voronoi texture node's F1 Color (Euclidean, detail 0)
    const voronoiF1Colour2 = o.fn('bn_voronoi_f1_colour2', [['cx', 'float'], ['cy', 'float'], ['scale', 'float'],
        ['randomness', 'float']], 'vec3', (o_, cx, cy, scale, randomness) => {
        const coordx = o.mul(cx, scale), coordy = o.mul(cy, scale);
        const flx = o.floor(coordx), fly = o.floor(coordy);
        const cellx = o.ftoi(flx), celly = o.ftoi(fly);
        const lx = o.sub(coordx, flx), ly = o.sub(coordy, fly);
        let best = o.f(3.4e38);
        let tx = o.i(0), ty = o.i(0);
        const r = o.clamp(randomness, 0.0, 1.0);
        for (let j = -1; j <= 1; j++) {
            for (let i = -1; i <= 1; i++) {
                const [hx, hy] = hashI2F2(o.iadd(cellx, i), o.iadd(celly, j));
                const ptx = o.add(o.f(i), o.mul(hx, r)), pty = o.add(o.f(j), o.mul(hy, r));
                const dx = o.sub(ptx, lx), dy = o.sub(pty, ly);
                const d = o.sqrt(o.add(o.mul(dx, dx), o.mul(dy, dy)));
                const take = o.lt(d, best);
                best = o.select(take, d, best);
                tx = o.select(take, o.i(i), tx);
                ty = o.select(take, o.i(j), ty);
            }
        }
        const c = hashI2F3(o.iadd(cellx, tx), o.iadd(celly, ty));
        return o.v3(c[0], c[1], c[2]);
    });

    const voronoiF1Colour3 = o.fn('bn_voronoi_f1_colour3', [['cx', 'float'], ['cy', 'float'], ['cz', 'float'],
        ['scale', 'float'], ['randomness', 'float']], 'vec3', (o_, cx, cy, cz, scale, randomness) => {
        const co = [o.mul(cx, scale), o.mul(cy, scale), o.mul(cz, scale)];
        const fl = co.map((v) => o.floor(v));
        const cell = fl.map((v) => o.ftoi(v));
        const loc = co.map((v, q) => o.sub(v, fl[q]));
        let best = o.f(3.4e38);
        let t = [o.i(0), o.i(0), o.i(0)];
        const r = o.clamp(randomness, 0.0, 1.0);
        for (let k = -1; k <= 1; k++) {
            for (let j = -1; j <= 1; j++) {
                for (let i = -1; i <= 1; i++) {
                    const off = [i, j, k];
                    const h = hashI3F3(o.iadd(cell[0], i), o.iadd(cell[1], j), o.iadd(cell[2], k));
                    const d2 = [0, 1, 2].map((q) => {
                        const pt = o.add(o.f(off[q]), o.mul(h[q], r));
                        const dd = o.sub(pt, loc[q]);
                        return o.mul(dd, dd);
                    });
                    const d = o.sqrt(o.add(o.add(d2[0], d2[1]), d2[2]));
                    const take = o.lt(d, best);
                    best = o.select(take, d, best);
                    t = t.map((v, q) => o.select(take, o.i(off[q]), v));
                }
            }
        }
        const c = hashI3F3(o.iadd(cell[0], t[0]), o.iadd(cell[1], t[1]), o.iadd(cell[2], t[2]));
        return o.v3(c[0], c[1], c[2]);
    });

    const out = { hash2, hash3, hash4, u2f, pcg2d, pcg3d, fade, grad3, grad4, triMix, perlin3, perlin4, fmod, snoise3,
        snoise4, fbm3, fbm4, noiseNode3, noiseNode4, voronoiF1Colour2, voronoiF1Colour3 };
    MEMO.set(ops, out);
    return out;
}

export const LICENCES = Object.freeze({
    cycles: 'Cycles (svm/noise.h, util/hash.h): Copyright 2011-2022 Blender Foundation, Apache License 2.0',
    blender: "Blender's GLSL noise (gpu_shader_material_noise.glsl, hash.glsl): Copyright Blender Foundation, GPL-2.0-or-later",
});
