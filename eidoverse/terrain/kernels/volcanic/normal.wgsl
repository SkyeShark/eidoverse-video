// numpy's Generator.standard_normal(size) on the GPU, draw for draw: what blender/eidoblend/terrain/solvers/volcanic.py
// lava_surface draws per cell of a flow's window (rng.standard_normal(np.shape(P))) at f90c6fc, which the edition puts
// on the GPU (per-cell work). numpy 2.3.4: PCG64 (a 128-bit LCG, state = state x MULT + inc, the XSL-RR output of the
// new state) and random_standard_normal (distributions.c: the ziggurat of 256 layers; 99.3 % of draws return from the
// first 64-bit word, the rest take a wedge test or a tail loop that read more words). The port's own kernel, its
// pieces driven by solvers/volcanic.js standardNormalGpu:
//   uMode 0  words: one invocation per segment of uSeg words, from the segment's start state (advanced in BigInt on
//            the CPU, a few thousand per call), writes each word (lo, hi)
//   uMode 1  classify: every word as the start of a ziggurat attempt: cons (the words the attempt reads), out (1 when
//            it returns a value), the value; the fast path exactly (the 52-bit rabs against ki as two integers), the
//            wedge test in float32 with the near-ties marked doubtful, every tail attempt doubtful. Doubtful attempts
//            are settled in doubles on the CPU by core/np_random.js's own generator placed at that word, and patched
//            back (uMode 4); a value is float32 (numpy's float64 x rounded once, give or take its last bits)
//   uMode 2  parse: per segment and entry offset e < E, the walk of attempts from the segment's start + e to past its
//            end: the exit offset into the next segment and the values returned (the CPU chains the segments)
//   uMode 3  emit: per segment, from its entry, every returned value to its place (and the stream's end after the
//            last value wanted)
//   uMode 4  patch the settled attempts
//   uMode 5  the doubtful attempts' flags as 0 / 1 (for core/prims.js nonzero)
// Lists are core/prims.js lists (row-major, rows of LINE).
//! include prims/lib
//! sampler a r32ui       mode 0: the segments' start states (4 words each, low first); 1, 2, 3: the words (2 each);
//                        4: the patches (4 words each: index, cons, out, value bits)
//! sampler b r32ui       mode 0: the increment (4 words); 1: the ki table (2 words each: rabs's high 29 and low 23
//                        bits); 2, 3: cons; 4: a stand-in
//! sampler c r32ui       2, 3: out (bit 0) and doubt (bit 1); 3: and the segments' entries (c2)
//! sampler wf            mode 1: (wi, fi) per layer, float32; 3: the values; else a stand-in
//! sampler c2 r32ui      mode 3: per segment (entry offset, the first value's index)
//! image   o1 r32ui      0: the words; 1: cons; 2: the exits; 3: the end; 4: cons
//! image   o2 r32ui      1: out | doubt << 1; 2: the counts; 4: out | doubt << 1
//! image   o3 r32f       1: the values; 3: the values out; 4: the values
//! uniform int uMode
//! uniform int uSeg      the words of a segment
//! uniform int uCount    0: the words; 1: the words classified; 2, 3: the segments; 4: the patches
//! uniform int uE        2: the entry offsets per segment; 3: the values wanted

const MULT = array<u32, 8>(0xF645u, 0x9FCCu, 0xDF64u, 0x4385u, 0x5DA4u, 0x1FC6u, 0xED05u, 0x2360u);

// state = state x MULT + inc (mod 2^128), on 16-bit limbs (low first): the column sums kept apart in their low and
// high halves, so nothing overflows 32 bits
fn pcg_step(s: ptr<function, array<u32, 8>>, inc: array<u32, 8>) {
  var r: array<u32, 8>;
  var carry = 0u;
  for (var col = 0; col < 8; col++) {
    var lo = inc[col] + carry;
    var hi = 0u;
    for (var i = 0; i <= col; i++) {
      let p = (*s)[i] * MULT[col - i];
      lo += p & 0xFFFFu;
      hi += p >> 16u;
    }
    r[col] = lo & 0xFFFFu;
    carry = hi + (lo >> 16u);
  }
  *s = r;
}

// XSL-RR: rotr64((state >> 64) ^ state, state >> 122) as (lo, hi)
fn pcg_out(s: array<u32, 8>) -> vec2<u32> {
  let xl = ((s[1] ^ s[5]) << 16u) | (s[0] ^ s[4]);
  let xh = ((s[3] ^ s[7]) << 16u) | (s[2] ^ s[6]);
  let rot = s[7] >> 10u;
  if (rot == 0u) { return vec2<u32>(xl, xh); }
  if (rot < 32u) { return vec2<u32>((xl >> rot) | (xh << (32u - rot)), (xh >> rot) | (xl << (32u - rot))); }
  if (rot == 32u) { return vec2<u32>(xh, xl); }
  let r = rot - 32u;
  return vec2<u32>((xh >> r) | (xl << (32u - r)), (xl >> r) | (xh << (32u - r)));
}

fn limbs(w: vec4<u32>) -> array<u32, 8> {
  return array<u32, 8>(w.x & 0xFFFFu, w.x >> 16u, w.y & 0xFFFFu, w.y >> 16u, w.z & 0xFFFFu, w.z >> 16u,
                       w.w & 0xFFFFu, w.w >> 16u);
}

fn a4(i: i32) -> vec4<u32> { return vec4<u32>(a_b[4 * i], a_b[4 * i + 1], a_b[4 * i + 2], a_b[4 * i + 3]); }

// next_double of a word: (w >> 11) / 2^53, in float32
fn next_double(lo: u32, hi: u32) -> f32 { return f32(hi) * (1.0 / 4294967296.0) + f32(lo >> 11u) * (1.0 / 9007199254740992.0); }

fn kmain(p: vec2<i32>) {
  let t = line_index(p);
  if (t >= u.uCount) { return; }
  switch u.uMode {
    case 0: {
      var s = limbs(a4(t));
      let inc = limbs(vec4<u32>(b_b[0], b_b[1], b_b[2], b_b[3]));
      let base = t * u.uSeg;
      for (var k = 0; k < u.uSeg; k++) {
        pcg_step(&s, inc);
        let w = pcg_out(s);
        o1_b[2 * (base + k)] = w.x;
        o1_b[2 * (base + k) + 1] = w.y;
      }
    }
    case 1: {
      let lo = a_b[2 * t];
      let hi = a_b[2 * t + 1];
      let idx = i32(lo & 0xFFu);
      let sign = (lo >> 8u) & 1u;
      let rh = hi & 0x1FFFFFFFu;               // rabs = rh 2^23 + rl: bits 9..60 of the word
      let rl = lo >> 9u;
      let kh = b_b[2 * idx];
      let kl = b_b[2 * idx + 1];
      let wi = wf_at(vec2<i32>(idx, 0)).x;
      var x = (f32(rh) * 8388608.0 + f32(rl)) * wi;
      if (sign != 0u) { x = -x; }
      var cons = 1u;
      var flags = 0u;
      if (rh < kh || (rh == kh && rl < kl)) {
        flags = 1u;                               // returned from the first word
      } else if (idx == 0) {
        flags = 2u;                               // the tail: settled on the CPU
      } else {
        cons = 2u;
        let lo1 = a_b[2 * (t + 1)];
        let hi1 = a_b[2 * (t + 1) + 1];
        let u1 = next_double(lo1, hi1);
        let f0 = wf_at(vec2<i32>(idx - 1, 0)).y;
        let f1 = wf_at(vec2<i32>(idx, 0)).y;
        let lhs = (f0 - f1) * u1 + f1;
        let rhs = exp(-0.5 * x * x);
        if (abs(lhs - rhs) <= 1e-5 * rhs + 1e-30) { flags = 2u; } else if (lhs < rhs) { flags = 1u; }
      }
      o1_b[t] = cons;
      o2_b[t] = flags;
      o3_b[t] = x;
    }
    case 2: {
      let s = t / u.uE;
      let e = t % u.uE;
      let end = (s + 1) * u.uSeg;
      var pos = s * u.uSeg + e;
      var cnt = 0u;
      while (pos < end) {
        cnt += c_b[pos] & 1u;
        pos += i32(b_b[pos]);
      }
      o1_b[t] = u32(pos - end);
      o2_b[t] = cnt;
    }
    case 3: {
      let ent = c2_b[2 * t];
      var i = i32(c2_b[2 * t + 1]);
      let end = (t + 1) * u.uSeg;
      var pos = t * u.uSeg + i32(ent);
      let vw = wf_size().x;
      while (pos < end && i < u.uE) {
        if ((c_b[pos] & 1u) != 0u) {
          o3_b[i] = wf_at(vec2<i32>(pos % vw, pos / vw)).x;
          i += 1;
          if (i == u.uE) { o1_b[0] = u32(pos) + b_b[pos]; }
        }
        pos += i32(b_b[pos]);
      }
    }
    case 5: {
      o1_b[t] = (a_b[t] >> 1u) & 1u;           // the doubtful attempts (their flags' bit 1), for compaction
    }
    default: {
      let k = i32(a_b[4 * t]);
      o1_b[k] = a_b[4 * t + 1];
      o2_b[k] = a_b[4 * t + 2];
      o3_b[k] = bitcast<f32>(a_b[4 * t + 3]);
    }
  }
}
