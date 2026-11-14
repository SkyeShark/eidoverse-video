// common.wgsl: blender/eidoblend/terrain/kernels/common.glsl, one for one, in WGSL (a design-probe copy; the port's
// own is eidoverse/terrain/kernels/common.wgsl). Frames as there: a cell (x, y) is array cell [row j = y, column
// i = x], row 0 the SOUTH edge; neighbours k = 0..7 are SW, S, SE, W, E, NW, N, NE; the opposite of k is 7 - k.

const OFF = array<vec2<i32>, 8>(vec2<i32>(-1, -1), vec2<i32>(0, -1), vec2<i32>(1, -1), vec2<i32>(-1, 0),
                                vec2<i32>(1, 0), vec2<i32>(-1, 1), vec2<i32>(0, 1), vec2<i32>(1, 1));
const LEN = array<f32, 8>(1.41421356, 1.0, 1.41421356, 1.0, 1.0, 1.41421356, 1.0, 1.41421356);
const WISO = array<f32, 8>(0.16666667, 0.66666667, 0.16666667, 0.66666667, 0.66666667, 0.16666667,
                           0.66666667, 0.16666667);
const WISO_SUM: f32 = 3.33333333;
fn opp(k: i32) -> i32 { return 7 - k; }

const BOUND_OPEN: i32 = 0;
const BOUND_PERIODIC: i32 = 1;
const BOUND_PINNED: i32 = 2;

fn inside(q: vec2<i32>, n: vec2<i32>) -> bool { return q.x >= 0 && q.y >= 0 && q.x < n.x && q.y < n.y; }

fn wrap(q: vec2<i32>, n: vec2<i32>) -> vec2<i32> {
  var r = q;
  if (r.x < 0) { r.x += n.x; } else if (r.x >= n.x) { r.x -= n.x; }
  if (r.y < 0) { r.y += n.y; } else if (r.y >= n.y) { r.y -= n.y; }
  return r;
}

fn neighbour(p: vec2<i32>, k: i32, n: vec2<i32>, mode: i32, q: ptr<function, vec2<i32>>) -> bool {
  *q = p + OFF[k];
  if (mode == BOUND_PERIODIC) {
    *q = wrap(*q, n);
    return true;
  }
  return inside(*q, n);
}

fn on_edge(p: vec2<i32>, n: vec2<i32>) -> bool { return p.x == 0 || p.y == 0 || p.x == n.x - 1 || p.y == n.y - 1; }

// written as the twin computes it (h (1 - a) + pin_h a), not as mix(): backends lower mix to h + (pin_h - h) a
fn pin_apply(h: f32, pin_w: f32, pin_h: f32) -> f32 {
  let a = clamp(pin_w, 0.0, 1.0);
  return h * (1.0 - a) + pin_h * a;
}

fn world_xy(p: vec2<i32>, lv: vec3<f32>) -> vec2<f32> { return lv.xy + (vec2<f32>(p) + 0.5) * lv.z; }
fn tan_deg(d: f32) -> f32 { return tan(radians(d)); }

fn pcg(v: u32) -> u32 {
  let state = v * 747796405u + 2891336453u;
  let word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
  return (word >> 22u) ^ word;
}
fn pcg2(a: u32, b: u32) -> u32 { return pcg(pcg(a) + b); }
fn pcg3(a: u32, b: u32, c: u32) -> u32 { return pcg(pcg(pcg(a) + b) + c); }
fn pcg4(a: u32, b: u32, c: u32, d: u32) -> u32 { return pcg(pcg(pcg(pcg(a) + b) + c) + d); }
fn u01(h: u32) -> f32 { return f32(h >> 8u) * (1.0 / 16777216.0); }
fn cell_hash(p: vec2<i32>, iter: i32, seed: i32) -> u32 { return pcg4(u32(p.x), u32(p.y), u32(iter), u32(seed)); }
