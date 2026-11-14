// Port of blender/eidoblend/terrain/core/world_noise.py at f90c6fc: KERNEL_FIELD (field_gpu's kernel), transcribed
// from the design probe's tests/design_probes/wgsl/world_noise_field.wgsl, with GLSL_NOISE now kernels/noise.wgsl.
// A sum of lattice terms at a level's cells: each term two texels, (mode, 1/w, amp, period) and (base x, base y,
// frac x, frac y), built on the CPU from the field spec (core/world_noise.js leafTerms), as field_gpu builds them.
//! include noise
//! sampler terms     two texels per lattice term: (mode, 1/w, amp, period), (base x, base y, frac x, frac y)
//! sampler disp      x, y: the cell's displacement in metres (a warp), zero when unwarped
//! image   outF r32f
//! uniform int uTerms
//! uniform float uCell
//! uniform float uConst

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let local = (vec2<f32>(p) + 0.5) * u.uCell + disp_at(p).xy;
  var acc = u.uConst;
  for (var t = 0; t < u.uTerms; t++) {
    let a = terms_at(vec2<i32>(2 * t, 0));
    let b = terms_at(vec2<i32>(2 * t + 1, 0));
    let lc = b.zw + local * a.y;
    let fl = floor(lc);
    let v = eido_lattice(vec2<i32>(b.xy) + vec2<i32>(fl), lc - fl, i32(a.w));
    acc += a.z * select(v, abs(v), a.x > 0.5);
  }
  outF_store(p, vec4<f32>(acc, 0.0, 0.0, 0.0));
}
