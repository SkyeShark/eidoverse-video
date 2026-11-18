// The port's own kernel (no Blender counterpart): the floors' widths and channel cells of blender/eidoblend/terrain/
// solvers/fluvial.py op_valley_floor at f90c6fc, which numpy makes in float64:
//     W    = min(width_m (max(A, 0) / area_ref_m2)^width_exp, width_max_m)        the floor's width, metres
//     chan = (max(A, 0) >= area_min_m2) & (W / cell >= min_width_cells) (& h > sea)
// uAmin is the smallest float32 at or above area_min_m2, so a float32 area passes exactly when numpy's test does.
//! sampler A
//! sampler h
//! image   outW r32f
//! image   outC r32f     1 on channel cells
//! image   count atomic_u32   the channel cells
//! uniform float uWidth
//! uniform float uAref
//! uniform float uExp
//! uniform float uWmax
//! uniform float uAmin
//! uniform float uMinCells
//! uniform float uCell
//! uniform int uSea
//! uniform float uSea32

fn kmain(p: vec2<i32>) {
  if (!inside(p, outW_size())) { return; }
  let a = max(A_at(p).x, 0.0);
  let w = min(u.uWidth * pow(a / u.uAref, u.uExp), u.uWmax);
  var c = a >= u.uAmin && w / u.uCell >= u.uMinCells;
  if (u.uSea == 1 && !(h_at(p).x > u.uSea32)) { c = false; }
  outW_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
  outC_store(p, vec4<f32>(select(0.0, 1.0, c), 0.0, 0.0, 0.0));
  if (c) { atomicAdd(&count_b[0], 1u); }
}
