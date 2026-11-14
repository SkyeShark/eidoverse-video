// Port of blender/eidoblend/terrain/kernels/common.glsl at f90c6fc.
//
// common.wgsl: prefixed to every terrain kernel by core/gpu.js (PORT_PLAN.md section 4.2). One for one with
// common.glsl; its numpy twin is the set of primitives in the Blender edition's core/twins.py (OFF, LEN, WISO,
// neighbour, pin_apply, pcg ...), which the kernel fixtures check this file against.
//
// Frames. A cell (x, y) is the array cell [row j = y, column i = x]; row 0 is the SOUTH edge, so +y is north and
// +x is east. A cell centre is at world x = x0 + (i + 0.5) * cell, y = y0 + (j + 0.5) * cell (metres, the Blender
// frame). Inputs are storage buffers read through <name>_at(q) (no filtering); outputs are written through
// <name>_store(q, v); work groups are 16 x 16.
//
// Differences from common.glsl, each forced by WGSL:
//   - `out ivec2 q` is a pointer: neighbour(p, k, n, mode, &q).
//   - wrap()'s nested ?: are if / else (WGSL has no conditional operator on statements; select() would evaluate
//     the same integers, the branches read closer to the GLSL).
//   - the #define'd boundary modes are consts.
//   - pin_apply is written as the numpy twin computes it, h (1 - a) + pin_h a, not as mix(): backends lower mix to
//     h + (pin_h - h) a, which differs in the last bits and leaves a fully pinned cell (a = 1) off its pin value by
//     a rounding. The Blender GLSL calls mix(); its twin (core/twins.py pin_apply) is the oracle both are held to.

// The 8 neighbours, k = 0..7: SW, S, SE, W, E, NW, N, NE. OFF[k] = (column step, row step). The opposite of k is
// 7 - k. LEN[k] is the distance in cells. WISO[k] are the isotropic 9-point weights (sides 2/3, diagonals 1/6):
// the Laplacian is sum_k WISO[k] (h_k - h) / cell^2, its centre weight -10/3 (WISO_SUM).
const OFF = array<vec2<i32>, 8>(vec2<i32>(-1, -1), vec2<i32>(0, -1), vec2<i32>(1, -1), vec2<i32>(-1, 0),
                                vec2<i32>(1, 0), vec2<i32>(-1, 1), vec2<i32>(0, 1), vec2<i32>(1, 1));
const LEN = array<f32, 8>(1.41421356, 1.0, 1.41421356, 1.0, 1.0, 1.41421356, 1.0, 1.41421356);
const WISO = array<f32, 8>(0.16666667, 0.66666667, 0.16666667, 0.66666667, 0.66666667, 0.16666667,
                           0.66666667, 0.16666667);
const WISO_SUM: f32 = 3.33333333;
fn opp(k: i32) -> i32 { return 7 - k; }

// Boundary modes, passed to a kernel as `//! uniform int uBound`.
//   OPEN      the grid ends: a neighbour off the edge does not exist (zero flux through the edge)
//   PERIODIC  the grid wraps on both axes (periodic dune tiles)
//   PINNED    neighbours as OPEN; cells with a pin weight hold their pin value (pin_apply) - borders, sea, flats
const BOUND_OPEN: i32 = 0;
const BOUND_PERIODIC: i32 = 1;
const BOUND_PINNED: i32 = 2;

fn inside(q: vec2<i32>, n: vec2<i32>) -> bool { return q.x >= 0 && q.y >= 0 && q.x < n.x && q.y < n.y; }

// periodic wrap for q in [-n, 2n): one exact integer step back onto the grid (a float floor(q / n) can land one
// cell off when the division rounds down)
fn wrap(q: vec2<i32>, n: vec2<i32>) -> vec2<i32> {
  var r = q;
  if (r.x < 0) { r.x += n.x; } else if (r.x >= n.x) { r.x -= n.x; }
  if (r.y < 0) { r.y += n.y; } else if (r.y >= n.y) { r.y -= n.y; }
  return r;
}

// the k-th neighbour of p under a boundary mode; false when it does not exist (off an OPEN or PINNED edge)
fn neighbour(p: vec2<i32>, k: i32, n: vec2<i32>, mode: i32, q: ptr<function, vec2<i32>>) -> bool {
  *q = p + OFF[k];
  if (mode == BOUND_PERIODIC) {
    *q = wrap(*q, n);
    return true;
  }
  return inside(*q, n);
}

fn on_edge(p: vec2<i32>, n: vec2<i32>) -> bool { return p.x == 0 || p.y == 0 || p.x == n.x - 1 || p.y == n.y - 1; }

// A Dirichlet pin, stored as two fields: pin_w (weight 0..1) and pin_h (the value). Weight 1 holds the value,
// 0 leaves the cell free; the border band ramps from 1 at a child's edge to 0 at 16 cells in.
fn pin_apply(h: f32, pin_w: f32, pin_h: f32) -> f32 {
  let a = clamp(pin_w, 0.0, 1.0);
  return h * (1.0 - a) + pin_h * a;
}

// world position of a cell centre; lv = (x0, y0, cell) of the level, metres
fn world_xy(p: vec2<i32>, lv: vec3<f32>) -> vec2<f32> { return lv.xy + (vec2<f32>(p) + 0.5) * lv.z; }

// Angles are degrees in every interface and tangents inside kernels.
fn tan_deg(d: f32) -> f32 { return tan(radians(d)); }

// 32-bit PCG hash (PCG-RXS-M-XS; Jarzynski & Olano 2020, "Hash Functions for GPU Rendering"). pcg2/pcg3/pcg4
// chain it over more words. u01 maps a hash to [0, 1) with 24 bits, exact in float32.
fn pcg(v: u32) -> u32 {
  let state = v * 747796405u + 2891336453u;
  let word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
  return (word >> 22u) ^ word;
}
fn pcg2(a: u32, b: u32) -> u32 { return pcg(pcg(a) + b); }
fn pcg3(a: u32, b: u32, c: u32) -> u32 { return pcg(pcg(pcg(a) + b) + c); }
fn pcg4(a: u32, b: u32, c: u32, d: u32) -> u32 { return pcg(pcg(pcg(pcg(a) + b) + c) + d); }
fn u01(h: u32) -> f32 { return f32(h >> 8u) * (1.0 / 16777216.0); }
// a cell's hash at an iteration with a seed: what the dune and dither decisions read
fn cell_hash(p: vec2<i32>, iter: i32, seed: i32) -> u32 { return pcg4(u32(p.x), u32(p.y), u32(iter), u32(seed)); }
