// sets/same_seed/noise.js — Blender's procedural textures in TSL, so a material exported from Blender keeps its
// pattern: the Noise Texture (3D Perlin fBm, normalized), the White Noise Texture (3D) and the Voronoi Texture's F1
// distance (3D, Euclidean). The hash is Bob Jenkins' lookup3 (public domain) and the gradient noise is Ken Perlin's
// improved noise, as Blender's shader nodes have them (Blender is GPL-2.0-or-later); the same coordinates give the same
// values as Blender's GPU shaders, to float precision.
//
//   const N = makeNoise(THREE);                // once per THREE
//   N.noise(vec3Node, { scale, detail, roughness, lacunarity })   // -> the Noise Texture's Fac (0..1)
//   N.white(vec3Node)                          // -> the White Noise Texture's Value; N.whiteColor(vec3Node) -> its Color
//   N.voronoiF1(vec3Node, { scale, randomness })   // -> the Voronoi Texture's Distance (F1, Euclidean)

export function makeNoise(THREE) {
    const { Fn, float, int, uint, vec3, floor, mix, select, bitcast } = THREE;

    const rot = (x, k) => x.shiftLeft(uint(k)).bitOr(x.shiftRight(uint(32 - k)));
    // lookup3's final(a, b, c), in place on three uint vars
    const final = (a, b, c) => {
        c.assign(c.bitXor(b)); c.assign(c.sub(rot(b, 14)));
        a.assign(a.bitXor(c)); a.assign(a.sub(rot(c, 11)));
        b.assign(b.bitXor(a)); b.assign(b.sub(rot(a, 25)));
        c.assign(c.bitXor(b)); c.assign(c.sub(rot(b, 16)));
        a.assign(a.bitXor(c)); a.assign(a.sub(rot(c, 4)));
        b.assign(b.bitXor(a)); b.assign(b.sub(rot(a, 14)));
        c.assign(c.bitXor(b)); c.assign(c.sub(rot(b, 24)));
    };
    // lookup3's mix(a, b, c)
    const mixABC = (a, b, c) => {
        a.assign(a.sub(c)); a.assign(a.bitXor(rot(c, 4))); c.assign(c.add(b));
        b.assign(b.sub(a)); b.assign(b.bitXor(rot(a, 6))); a.assign(a.add(c));
        c.assign(c.sub(b)); c.assign(c.bitXor(rot(b, 8))); b.assign(b.add(a));
        a.assign(a.sub(c)); a.assign(a.bitXor(rot(c, 16))); c.assign(c.add(b));
        b.assign(b.sub(a)); b.assign(b.bitXor(rot(a, 19))); a.assign(a.add(c));
        c.assign(c.sub(b)); c.assign(c.bitXor(rot(b, 4))); b.assign(b.add(a));
    };

    const hashUint3 = Fn(([kx, ky, kz]) => {
        const s = 0xdeadbeef + (3 << 2) + 13;
        const a = uint(s).add(kx).toVar(), b = uint(s).add(ky).toVar(), c = uint(s).add(kz).toVar();
        final(a, b, c);
        return c;
    }).setLayout({ name: 'bl_hash_uint3', type: 'uint', inputs: [{ name: 'kx', type: 'uint' }, { name: 'ky', type: 'uint' }, { name: 'kz', type: 'uint' }] });

    const hashUint4 = Fn(([kx, ky, kz, kw]) => {
        const s = 0xdeadbeef + (4 << 2) + 13;
        const a = uint(s).add(kx).toVar(), b = uint(s).add(ky).toVar(), c = uint(s).add(kz).toVar();
        mixABC(a, b, c);
        a.assign(a.add(kw));
        final(a, b, c);
        return c;
    }).setLayout({ name: 'bl_hash_uint4', type: 'uint', inputs: [{ name: 'kx', type: 'uint' }, { name: 'ky', type: 'uint' }, { name: 'kz', type: 'uint' }, { name: 'kw', type: 'uint' }] });

    const toUnit = (h) => float(h).div(4294967295.0);

    const fade = (t) => t.mul(t).mul(t).mul(t.mul(t.mul(6.0).sub(15.0)).add(10.0));
    const negateIf = (v, cond) => select(cond.notEqual(uint(0)), v.negate(), v);
    const grad = Fn(([hash, x, y, z]) => {
        const h = hash.bitAnd(uint(15));
        const u = select(h.lessThan(uint(8)), x, y);
        const vt = select(h.equal(uint(12)).or(h.equal(uint(14))), x, z);
        const v = select(h.lessThan(uint(4)), y, vt);
        return negateIf(u, h.bitAnd(uint(1))).add(negateIf(v, h.bitAnd(uint(2))));
    }).setLayout({ name: 'bl_noise_grad', type: 'float', inputs: [{ name: 'hash', type: 'uint' }, { name: 'x', type: 'float' }, { name: 'y', type: 'float' }, { name: 'z', type: 'float' }] });

    const perlin = Fn(([p]) => {
        const fl = floor(p);
        const X = int(fl.x), Y = int(fl.y), Z = int(fl.z);
        const fx = p.x.sub(fl.x), fy = p.y.sub(fl.y), fz = p.z.sub(fl.z);
        const u = fade(fx), v = fade(fy), w = fade(fz);
        const H = (dx, dy, dz) => hashUint3(uint(X.add(dx)), uint(Y.add(dy)), uint(Z.add(dz)));
        const g000 = grad(H(0, 0, 0), fx, fy, fz);
        const g100 = grad(H(1, 0, 0), fx.sub(1.0), fy, fz);
        const g010 = grad(H(0, 1, 0), fx, fy.sub(1.0), fz);
        const g110 = grad(H(1, 1, 0), fx.sub(1.0), fy.sub(1.0), fz);
        const g001 = grad(H(0, 0, 1), fx, fy, fz.sub(1.0));
        const g101 = grad(H(1, 0, 1), fx.sub(1.0), fy, fz.sub(1.0));
        const g011 = grad(H(0, 1, 1), fx, fy.sub(1.0), fz.sub(1.0));
        const g111 = grad(H(1, 1, 1), fx.sub(1.0), fy.sub(1.0), fz.sub(1.0));
        const x1 = float(1.0).sub(u), y1 = float(1.0).sub(v), z1 = float(1.0).sub(w);
        const a = y1.mul(g000.mul(x1).add(g100.mul(u))).add(v.mul(g010.mul(x1).add(g110.mul(u))));
        const b = y1.mul(g001.mul(x1).add(g101.mul(u))).add(v.mul(g011.mul(x1).add(g111.mul(u))));
        return z1.mul(a).add(w.mul(b)).mul(0.9820);                  // (snoise: noise_scale3)
    }).setLayout({ name: 'bl_snoise3', type: 'float', inputs: [{ name: 'p', type: 'vec3' }] });

    // the Noise Texture's Fac (3D, fBm, normalized); scale, detail, roughness and lacunarity are numbers (unrolled)
    function noise(co, { scale = 5.0, detail = 2.0, roughness = 0.5, lacunarity = 2.0, normalize = true } = {}) {
        detail = Math.min(15, Math.max(0, detail));
        roughness = Math.max(0, roughness);
        const p = vec3(co).mul(scale);
        let fscale = 1.0, amp = 1.0, maxamp = 0.0;
        let sum = float(0.0);
        for (let i = 0; i <= Math.floor(detail); i++) {
            sum = sum.add(perlin(p.mul(fscale)).mul(amp));
            maxamp += amp;
            amp *= roughness;
            fscale *= lacunarity;
        }
        const rmd = detail - Math.floor(detail);
        if (rmd !== 0.0) {
            const sum2 = sum.add(perlin(p.mul(fscale)).mul(amp));
            return normalize ? mix(sum.div(maxamp).mul(0.5).add(0.5), sum2.div(maxamp + amp).mul(0.5).add(0.5), rmd) : mix(sum, sum2, rmd);
        }
        return normalize ? sum.div(maxamp).mul(0.5).add(0.5) : sum;
    }

    // the White Noise Texture (3D): the hash of the coordinates' float bits
    const bits = (x) => bitcast(float(x), 'uint');
    function white(co) {
        const v = vec3(co);
        return toUnit(hashUint3(bits(v.x), bits(v.y), bits(v.z)));
    }
    function whiteColor(co) {
        const v = vec3(co);
        const kx = bits(v.x), ky = bits(v.y), kz = bits(v.z);
        return vec3(toUnit(hashUint3(kx, ky, kz)), toUnit(hashUint4(kx, ky, kz, uint(1))), toUnit(hashUint4(kx, ky, kz, uint(2))));
    }

    // the Voronoi Texture's F1 distance (3D, Euclidean, one octave)
    const cellPoint = Fn(([c]) => {
        const kx = uint(int(c.x)), ky = uint(int(c.y)), kz = uint(int(c.z));
        return vec3(toUnit(hashUint3(kx, ky, kz)), toUnit(hashUint4(kx, ky, kz, uint(1))), toUnit(hashUint4(kx, ky, kz, uint(2))));
    }).setLayout({ name: 'bl_voronoi_cell', type: 'vec3', inputs: [{ name: 'c', type: 'vec3' }] });
    function voronoiF1(co, { scale = 5.0, randomness = 1.0 } = {}) {
        const p = vec3(co).mul(scale);
        const cell = floor(p);
        const local = p.sub(cell);
        let best = float(1e30);
        for (let k = -1; k <= 1; k++) for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
            const off = vec3(i, j, k);
            const pt = off.add(cellPoint(cell.add(off)).mul(randomness));
            best = best.min(pt.sub(local).length());
        }
        return best;
    }

    return { noise, white, whiteColor, voronoiF1, perlin, hashUint3, hashUint4 };
}
