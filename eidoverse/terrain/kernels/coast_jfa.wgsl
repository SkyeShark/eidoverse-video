// Port of the inline kernel coast_jfa of blender/eidoblend/terrain/solvers/coast.py (JFA) at f90c6fc.
//
// One jump-flooding pass at a step: each cell keeps the nearest of the seeds its 9 probes see (the coast's signed
// distances and the payload they carry: the exposure, the face angle).
//
// Differences from the GLSL, forced by WGSL: `precise` values go through exact() (kernels/detail/exact.wgsl), so
// d.x * d.x + d.y * d.y is two products and a sum each rounded as written (no fused multiply-add), as the twin's
// float32 is; a near-tie between two seeds then falls the twin's way.

//! sampler st     x, y: the nearest seed known (cell units), z: its payload, w: 1 when a seed is known
//! image   outS rgba32f
//! uniform int uStep   the probe step, cells
//! include detail/exact
fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let z = exact_zero(n);
  var best = st_at(p);
  let pc = vec2<f32>(p);
  let d0 = vec2<f32>(exact(best.x - pc.x, z), exact(best.y - pc.y, z));
  var bd = 1e30;
  if (best.w > 0.5) { bd = exact(exact(d0.x * d0.x, z) + exact(d0.y * d0.y, z), z); }
  for (var dy = -1; dy <= 1; dy++) {
    for (var dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) { continue; }
      let q = p + vec2<i32>(dx, dy) * u.uStep;
      if (!inside(q, n)) { continue; }
      let c = st_at(q);
      if (c.w < 0.5) { continue; }
      let d = vec2<f32>(exact(c.x - pc.x, z), exact(c.y - pc.y, z));
      let dd = exact(exact(d.x * d.x, z) + exact(d.y * d.y, z), z);
      if (dd < bd) {
        bd = dd;
        best = c;
      }
    }
  }
  outS_store(p, best);
}
