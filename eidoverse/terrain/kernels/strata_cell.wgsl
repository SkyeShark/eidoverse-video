// Port of the inline kernel STRATA_CELL ('strata_cell') of blender/eidoblend/terrain/solvers/strata.py at f90c6fc.
//
// Transcribed statement for statement from the GLSL source in strata.py (PORT_PLAN.md 3.3: an inline kernel becomes
// a file of the same name); the `//!` header is the GLSL's, unchanged. The changes are WGSL's: texelFetch(x, q, 0)
// is x_at(q), imageStore is outC_store (an rg32f image stores the first two components), textureSize is st_size(),
// and a uniform uX is u.uX.
//
// One forced deviation: zs passes through exact() (`//! include detail/exact`, the detail package's
// kernels/detail/exact.wgsl: an identity the compiler cannot see through). Written plainly, this machine's shader
// compiler rewrites (h - zoff) - uTZ0 into another order of the same sum (measured with tests/layered_rock/
// kernels_test.mjs's case: storing zs gives it to the bit, folding it into the table coordinate does not), and at a
// contact of the column (two beds' tangents or creep factors in neighbouring 0.5 m entries) the coordinate's one
// float32 step moved the result by up to 2.9e-4 (1.6e-4 of the channel's range, on 9 of 7,680 cells; Blender's GLSL
// on its own stack: 7.9e-8). With the barrier the kernel computes zs as written, as numpy's twin and the GLSL do:
// worst 2.4e-7.
//
// Per cell, once a step: the layer's own threshold and creep factor at the cell's current height (strata_creep reads
// them for the cell and its 8 neighbours; looking them up there cost 9 table reads a neighbour pair).
// Twin: solvers/strata.py strata_cell.
//! sampler st     x: h (m)
//! sampler zoff   x: z - zs (m)
//! sampler ctab   x: tan(theta), y: creep factor (1 row of uTN texels from uTZ0 every uTDz metres)
//! image   outC rg32f   x: tan(theta) of the layer at the cell's zs, y: its creep factor
//! uniform float uTZ0
//! uniform float uTDz
//! uniform int uTN
//! include detail/exact

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let zs = exact(st_at(p).x - zoff_at(p).x, exact_zero(n));
  let t = clamp((zs - u.uTZ0) / u.uTDz, 0.0, f32(u.uTN - 1));
  let i0 = min(i32(floor(t)), u.uTN - 2);
  let f = t - f32(i0);
  let a = ctab_at(vec2<i32>(i0, 0)).xy;
  let b = ctab_at(vec2<i32>(i0 + 1, 0)).xy;
  outC_store(p, vec4<f32>(mix(a, b, vec2<f32>(f)), 0.0, 0.0));
}
