// Port of the inline kernel LOCK_APPLY ('lock_apply') of blender/eidoblend/terrain/solvers/fluvial.py at f90c6fc.
//
// Transcribed statement for statement from the GLSL source in fluvial.py (PORT_PLAN.md 3.3: an inline kernel
// becomes a file of the same name); the `//!` header is the GLSL's, unchanged. The changes are WGSL's: texelFetch is
// x_at, imageStore is outS_store / outM_store, textureSize is x_size(), a uniform uX is u.uX, `vec2 w[4]` is a
// function-scope array, and lock_layers' parameter is copied into a var. One forced rename: the GLSL's local `u`
// (the cell's position in block units) is `uv` here, because the runner names the uniform block `u`.
//
// The low-pass lock's second kernel (fluvial.py): the blocks' drift, spread by a cubic B-spline (C2: a bilinear
// spread leaves kinks along the block lines, and over a run the lock's correction is the level's whole effective
// uplift, hundreds of metres, so those kinks printed grid-aligned facets), taken off. Twin: solvers/fluvial.py
// lock_apply.
//! sampler st       the refining level's state (x: h)
//! sampler res      x: the blocks' drift
//! sampler pin      x: pin_w, y: pin_h (the border band holds its pins through the lock too)
//! sampler mk       x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outS rgba32f
//! image   outM rgba32f  the layers with the lock's change counted (lock_layers)
//! uniform float uGain
//! uniform int uB    the block, cells
//! uniform ivec2 uOff the block grid's offset (lock_restrict's)

/* the lock's change d of the height in the layers m: d < 0 takes deposit, then talus, then other loose cover, then
   rock, as route_incise.glsl counts a pin's (a pit the lock lowered and the incision pass refilled every step
   otherwise gathered hundreds of metres of "deposit" in one cell); d > 0 restores the parent's ground: rock, the
   loose cover unchanged and the wear reduced (counted as deposit it laid sediment over every slope the lock holds) */
fn lock_layers(m0: vec4<f32>, d: f32) -> vec4<f32> {
  var m = m0;
  if (d >= 0.0) { return vec4<f32>(max(m.x - d, 0.0), m.y, m.z, m.w); }
  var q = -d;
  let other = max(m.w - m.y - m.z, 0.0);
  var a = min(q, m.y);
  m.y -= a;
  q -= a;
  a = min(q, m.z);
  m.z -= a;
  q -= a;
  q -= min(q, other);
  m.w = max(m.w - (-d - q), 0.0);
  m.x += q;
  return m;
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let m = res_size();
  let uv = (vec2<f32>(p + u.uOff) + 0.5) / f32(u.uB) - 0.5;
  let f0 = floor(uv);
  let t = uv - f0;
  let t2 = t * t;
  let t3 = t2 * t;
  var w: array<vec2<f32>, 4>;
  w[0] = (1.0 - 3.0 * t + 3.0 * t2 - t3) / 6.0;
  w[1] = (4.0 - 6.0 * t2 + 3.0 * t3) / 6.0;
  w[2] = (1.0 + 3.0 * t + 3.0 * t2 - 3.0 * t3) / 6.0;
  w[3] = t3 / 6.0;
  var r = 0.0;
  for (var j = 0; j < 4; j++) {
    let jj = clamp(i32(f0.y) - 1 + j, 0, m.y - 1);
    var row = 0.0;
    for (var i = 0; i < 4; i++) {
      let ii = clamp(i32(f0.x) - 1 + i, 0, m.x - 1);
      row += w[i].x * res_at(vec2<i32>(ii, jj)).x;
    }
    r += w[j].y * row;
  }
  let c = st_at(p);
  let pn = pin_at(p);
  let hn = pin_apply(c.x - u.uGain * r, pn.x, pn.y);
  outS_store(p, vec4<f32>(hn, c.y, c.z, c.w));
  outM_store(p, lock_layers(mk_at(p), hn - c.x));
}
