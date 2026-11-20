// Port of the inline kernel coast_seed of blender/eidoblend/terrain/solvers/coast.py (SEED) at f90c6fc.
//
// The jump-flood seeds of a level set phi: every cell next to a sign change gets the nearest zero crossing on its
// 8 neighbour segments (sub-cell, in cell units) and the payload of the crossing's seaward cell.
//
// Differences from the GLSL, each forced by WGSL: `precise` values go through exact() (kernels/detail/exact.wgsl:
// computed as written, correctly rounded, as the twin's float32 is); `out ivec2 q` is a pointer; the payload's ?:
// is an if.

//! sampler phiT   x: the level set phi (metres): < 0 seaward (sea, cut), >= 0 landward
//! sampler payT   x: a payload read on the seaward cell of each crossing (the exposure)
//! image   outS rgba32f   x, y: the nearest zero crossing on the 8 neighbour segments (cells), z: payload, w: 1
//! include detail/exact
/* outS is all 0 where the cell has no sign change among its neighbours */
fn kmain(p: vec2<i32>) {
  let n = phiT_size();
  if (!inside(p, n)) { return; }
  let z = exact_zero(n);
  let a = phiT_at(p).x;
  let neg = a < 0.0;
  let pa = payT_at(p).x;
  var best = vec4<f32>(0.0);
  var bd = 1e30;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, BOUND_OPEN, &q)) { continue; }
    let b = phiT_at(q).x;
    if ((b < 0.0) == neg) { continue; }
    let t = exact(a / exact(a - b, z), z);
    var dd = exact(t * LEN[k], z);
    dd = exact(dd * dd, z);
    if (dd < bd) {
      bd = dd;
      let x = vec2<f32>(exact(f32(p.x) + exact(t * f32(OFF[k].x), z), z), exact(f32(p.y) + exact(t * f32(OFF[k].y), z), z));
      var pay = pa;
      if (!neg) { pay = payT_at(q).x; }
      best = vec4<f32>(x, pay, 1.0);
    }
  }
  outS_store(p, best);
}
