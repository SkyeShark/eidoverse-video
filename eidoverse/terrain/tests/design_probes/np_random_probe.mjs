// Design probe (PORT_PLAN.md section 2.4): numpy's Generator(PCG64(SeedSequence(seed))) in JS, bit for bit. The
// Blender edition draws its plans (karst towers, cinder cones, cirque order, wind schedules, rivers, strata cores,
// impact blocks, lava walkers) from np.random.default_rng(seed or [seed, salt]); the same recipe and seed can only
// give the same landform in the port when the port draws the same numbers. This is the core of that port:
// SeedSequence's entropy pool and generate_state, PCG64 (128-bit LCG, XSL-RR output), next_double, next_uint32
// (with numpy's half-word buffer), random(), uniform(), and integers() (Lemire's bounded method).
//
//     python -c "...numpy draws..." > expected.json   (np_random_expected.py writes it)
//     deno run --no-config --no-lock --allow-read eidoverse/terrain/tests/design_probes/np_random_probe.mjs expected.json

const M32 = 0xFFFFFFFFn, M64 = (1n << 64n) - 1n, M128 = (1n << 128n) - 1n;
const MULT128 = (0x2360ED051FC65DA4n << 64n) | 0x4385DF649FCCF645n;

function words32(n) {                          // numpy _int_to_uint32_array: little-endian 32-bit words
    n = BigInt(n);
    if (n < 0n) throw new Error('negative seed');
    if (n === 0n) return [0];
    const out = [];
    while (n > 0n) { out.push(Number(n & M32)); n >>= 32n; }
    return out;
}

const mul32 = (a, b) => Math.imul(a, b) >>> 0;

function seedSequencePool(entropy) {
    const ent = (Array.isArray(entropy) ? entropy : [entropy]).flatMap(words32);
    const INIT_A = 0x43b0d7e5, MULT_A = 0x931e8875, MIX_L = 0xca01f9dd, MIX_R = 0x4973f715;
    let hc = INIT_A;
    const hashmix = (v) => {
        v = (v ^ hc) >>> 0;
        hc = mul32(hc, MULT_A);
        v = mul32(v, hc);
        return (v ^ (v >>> 16)) >>> 0;
    };
    const mix = (x, y) => { let r = (mul32(MIX_L, x) - mul32(MIX_R, y)) >>> 0; return (r ^ (r >>> 16)) >>> 0; };
    const pool = [0, 0, 0, 0];
    for (let i = 0; i < 4; i++) pool[i] = hashmix(i < ent.length ? ent[i] : 0);
    for (let s = 0; s < 4; s++) for (let d = 0; d < 4; d++) if (s !== d) pool[d] = mix(pool[d], hashmix(pool[s]));
    for (let s = 4; s < ent.length; s++) for (let d = 0; d < 4; d++) pool[d] = mix(pool[d], hashmix(ent[s]));
    return pool;
}

function generateState64(pool, nWords64) {
    const INIT_B = 0x8b51f9dd, MULT_B = 0x58f38ded;
    let hc = INIT_B;
    const w = [];
    for (let i = 0; i < 2 * nWords64; i++) {
        let v = (pool[i % 4] ^ hc) >>> 0;
        hc = mul32(hc, MULT_B);
        v = mul32(v, hc);
        w.push((v ^ (v >>> 16)) >>> 0);
    }
    const out = [];
    for (let i = 0; i < nWords64; i++) out.push((BigInt(w[2 * i + 1]) << 32n) | BigInt(w[2 * i]));
    return out;
}

export class NpGenerator {
    constructor(seed) {
        const v = generateState64(seedSequencePool(seed), 4);
        const initstate = (v[0] << 64n) | v[1], initseq = (v[2] << 64n) | v[3];
        this.inc = ((initseq << 1n) | 1n) & M128;
        this.state = 0n;
        this._step();
        this.state = (this.state + initstate) & M128;
        this._step();
        this.hasU32 = false;
        this.u32 = 0;
    }
    _step() { this.state = (this.state * MULT128 + this.inc) & M128; }
    nextU64() {
        this._step();
        const s = this.state;
        const x = ((s >> 64n) ^ s) & M64;
        const rot = Number(s >> 122n);
        return ((x >> BigInt(rot)) | (x << BigInt((64 - rot) & 63))) & M64;
    }
    nextU32() {
        if (this.hasU32) { this.hasU32 = false; return this.u32; }
        const n = this.nextU64();
        this.hasU32 = true;
        this.u32 = Number(n >> 32n);
        return Number(n & M32);
    }
    random() { return Number(this.nextU64() >> 11n) * (1.0 / 9007199254740992.0); }
    uniform(lo, hi) { return lo + (hi - lo) * this.random(); }
    integers(lo, hi) {                              // [lo, hi), int64 default dtype, rng < 2^32: Lemire on 32 bits
        const rng = hi - 1 - lo;
        if (rng === 0) return lo;
        if (rng > 0xFFFFFFFE) throw new Error('probe covers 32-bit ranges');
        const excl = rng + 1;
        let m = BigInt(this.nextU32()) * BigInt(excl);
        let left = Number(m & M32);
        if (left < excl) {
            const thr = (0xFFFFFFFF - rng) % excl;
            while (left < thr) { m = BigInt(this.nextU32()) * BigInt(excl); left = Number(m & M32); }
        }
        return lo + Number(m >> 32n);
    }
}

if (import.meta.main) {
    const exp = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
    let ok = 0, bad = 0;
    for (const c of exp.cases) {
        const g = new NpGenerator(c.seed);
        const got = [];
        for (const d of c.draws) {
            if (d.m === 'random') got.push(...Array.from({ length: d.n }, () => g.random()));
            else if (d.m === 'uniform') got.push(...Array.from({ length: d.n }, () => g.uniform(d.lo, d.hi)));
            else if (d.m === 'integers') got.push(...Array.from({ length: d.n }, () => g.integers(d.lo, d.hi)));
        }
        const same = got.length === c.values.length && got.every((v, i) => Object.is(v, c.values[i]));
        same ? ok++ : bad++;
        if (!same) {
            const i = got.findIndex((v, k) => !Object.is(v, c.values[k]));
            console.log('MISMATCH seed', JSON.stringify(c.seed), 'at', i, got[i], c.values[i]);
        }
    }
    const res = { cases: exp.cases.length, bit_exact: ok, mismatched: bad, numpy: exp.numpy };
    console.log(JSON.stringify(res));
    if (Deno.args[1]) Deno.writeTextFileSync(Deno.args[1], JSON.stringify(res, null, 1));
}
