// eidoverse/sets/town/pyrandom.js — Python's random.Random, exactly: the Mersenne Twister seeded as CPython seeds it
// from an int, and the draws the town makes (random, uniform, choice, randrange, shuffle). The Blender edition's town
// is planned with Python's streams, so the same seed here gives the same town, building for building.
//
//   import { PyRandom } from './pyrandom.js';
//   const r = new PyRandom(7000021);   r.random(); r.uniform(2, 5); r.choice(['a', 'b']); r.randrange(3, 9); r.shuffle(list);
//
// Also the few Python numerics a port needs: pyRound (round half to even), pyMod (the sign of the divisor),
// pyIndex (a negative index counts from the end).

const N = 624, M = 397;

export class PyRandom {
    constructor(seed = 0) {
        this.mt = new Uint32Array(N);
        this.mti = N + 1;
        this.seed(seed);
    }

    // random.seed(int): init_by_array over the absolute value's 32-bit words, least significant first
    seed(a) {
        let n = BigInt(Math.trunc(Math.abs(Number(a))));
        if (typeof a === 'bigint') n = a < 0n ? -a : a;
        const key = [];
        while (n > 0n) { key.push(Number(n & 0xffffffffn)); n >>= 32n; }
        if (!key.length) key.push(0);
        this._initByArray(key);
    }

    _initGenrand(s) {
        const mt = this.mt;
        mt[0] = s >>> 0;
        for (let i = 1; i < N; i++) {
            const p = mt[i - 1] ^ (mt[i - 1] >>> 30);
            mt[i] = (Math.imul(1812433253, p) + i) >>> 0;
        }
        this.mti = N;
    }

    _initByArray(key) {
        const mt = this.mt;
        this._initGenrand(19650218);
        let i = 1, j = 0;
        for (let k = Math.max(N, key.length); k; k--) {
            const p = mt[i - 1] ^ (mt[i - 1] >>> 30);
            mt[i] = ((mt[i] ^ Math.imul(p, 1664525)) + key[j] + j) >>> 0;
            i++; j++;
            if (i >= N) { mt[0] = mt[N - 1]; i = 1; }
            if (j >= key.length) j = 0;
        }
        for (let k = N - 1; k; k--) {
            const p = mt[i - 1] ^ (mt[i - 1] >>> 30);
            mt[i] = ((mt[i] ^ Math.imul(p, 1566083941)) - i) >>> 0;
            i++;
            if (i >= N) { mt[0] = mt[N - 1]; i = 1; }
        }
        mt[0] = 0x80000000;
    }

    genrandUint32() {
        const mt = this.mt;
        let y;
        if (this.mti >= N) {
            let kk = 0;
            for (; kk < N - M; kk++) {
                y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff);
                mt[kk] = mt[kk + M] ^ (y >>> 1) ^ ((y & 1) ? 0x9908b0df : 0);
            }
            for (; kk < N - 1; kk++) {
                y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff);
                mt[kk] = mt[kk + (M - N)] ^ (y >>> 1) ^ ((y & 1) ? 0x9908b0df : 0);
            }
            y = (mt[N - 1] & 0x80000000) | (mt[0] & 0x7fffffff);
            mt[N - 1] = mt[M - 1] ^ (y >>> 1) ^ ((y & 1) ? 0x9908b0df : 0);
            this.mti = 0;
        }
        y = mt[this.mti++];
        y ^= (y >>> 11);
        y ^= (y << 7) & 0x9d2c5680;
        y ^= (y << 15) & 0xefc60000;
        y ^= (y >>> 18);
        return y >>> 0;
    }

    // a float in [0, 1) with 53 random bits (genrand_res53)
    random() {
        const a = this.genrandUint32() >>> 5, b = this.genrandUint32() >>> 6;
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
    }

    getrandbits(k) {
        if (k <= 0 || k > 32) throw new Error('getrandbits: 1..32 bits here');
        return this.genrandUint32() >>> (32 - k);
    }

    _randbelow(n) {
        if (n <= 0) throw new Error('empty range');
        const k = 32 - Math.clz32(n);                  // n.bit_length()
        let r = this.getrandbits(k);
        while (r >= n) r = this.getrandbits(k);
        return r;
    }

    uniform(a, b) { return a + (b - a) * this.random(); }

    randrange(start, stop) {
        if (stop === undefined) return this._randbelow(start);
        return start + this._randbelow(stop - start);
    }

    choice(seq) { return seq[this._randbelow(seq.length)]; }

    shuffle(x) {
        for (let i = x.length - 1; i > 0; i--) {
            const j = this._randbelow(i + 1);
            const t = x[i]; x[i] = x[j]; x[j] = t;
        }
        return x;
    }
}

// Python's round(): half to even on an exact tie; with digits, the decimal rounding of the value
export function pyRound(x, digits = 0) {
    if (digits) {
        // on the double's exact decimal digits (toFixed is exact), a tie only where the double IS the half: 0.125 is one,
        // 2.675 (2.67499999999999982...) is not
        const t = Math.abs(x).toFixed(Math.min(100, digits + 30)), dot = t.indexOf('.');
        const tail = t.slice(dot + 1 + digits);
        let n = BigInt(t.slice(0, dot) + t.slice(dot + 1, dot + 1 + digits));
        if (/^50*$/.test(tail) ? n % 2n === 1n : tail[0] >= '5') n += 1n;
        const s = n.toString().padStart(digits + 1, '0');
        const r = parseFloat(`${s.slice(0, -digits)}.${s.slice(-digits)}`);
        return x < 0 ? -r : r;
    }
    const f = Math.floor(x), d = x - f;
    if (d > 0.5) return f + 1;
    if (d < 0.5) return f;
    return f % 2 === 0 ? f : f + 1;
}

export const pyMod = (a, n) => ((a % n) + n) % n;
export const pyIndex = (arr, i) => arr[i < 0 ? arr.length + i : i];
