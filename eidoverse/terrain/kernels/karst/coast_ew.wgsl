// Port of the cell-by-cell numpy lines of blender/eidoblend/terrain/solvers/coast.py at f90c6fc, as one kernel with a
// mode per line (numpy's float64 is float32 here):
//   0  sea_phi:      phi = a - uSea (outF); wet = phi <= 0 (outU, for core/prims.js label)
//   1  sea_phi:      where(wet (a > 0.5), minimum(phi (b), -1e-4), maximum(phi, 1e-4)) (outF)
//   2  plan_shore:   sea = phi (a) < 0; phi = where(sea, min(phi, -1e-4), max(phi, 1e-4)) (outF); sea as 1 / 0 (outG)
//   3  plan_shore:   pay = where(E_shore (a) >= 0, E_shore, E_REF) (outF); the shore cells (E_shore >= 0) as 1 / 0
//                    (outG, the percentiles' mask)
//   4  op_coast:     cut = phi (a) < 0 (outU, for label); sea0 = d0 (b) < 0 as 1 / 0 (outG)
//   5  op_coast:     phi = where(cut (a > 0.5), min(phi (b), -1e-3), max(phi, 1e-3)) (outF); ~cut (outU, the stacks'
//                    label of the land)
//   6  _band_pins / _band_weight: t = clip((d (a) - 2) / max(band - 2, 1), 0, 1); 1 - t^2 (3 - 2t) (outF)
//   7  refine_land:  hb (a) (1 - w (c)) + land (b) w (outF)
//   8  _child_land:  coast_cut (a) > 1e-3 as 1 / 0 (outF, for the maximum filter)
//   9  min(a, b) (outF)                                             (bed = minimum(bed, h))
//   10 op_coast:     theta = clip(face_deg + face_spread_deg n (a; uHas 0: 0), 30, 88.5); theta += (stack_face_deg -
//                    theta) sw (b; uHas2 0: 0) (outF)
//   11 op_coast:     theta = where(isfinite(dist), theta_foot, theta): the crossing field d (y payload, z found) or a
//                    (outF)
//   12 op_coast:     sd = where(cut (a > 0.5), -1e7, 1e7) (outF)  (no foot line: all cut or none)

//! sampler a
//! sampler b
//! sampler c
//! sampler d rgba32f
//! image   outF r32f
//! image   outG r32f
//! image   outU r32ui
//! uniform int uMode
//! uniform int uHas
//! uniform int uHas2
//! uniform float uK0
//! uniform float uK1
//! uniform float uK2
fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let m = u.uMode;
  if (m == 0) {
    let phi = a_at(p).x - u.uK0;
    outF_store(p, vec4<f32>(phi, 0.0, 0.0, 0.0));
    outU_store(p, select(0u, 1u, phi <= 0.0));
  } else if (m == 1) {
    let phi = b_at(p).x;
    outF_store(p, vec4<f32>(select(max(phi, 1e-4), min(phi, -1e-4), a_at(p).x > 0.5), 0.0, 0.0, 0.0));
  } else if (m == 2) {
    let phi = a_at(p).x;
    let sea = phi < 0.0;
    outF_store(p, vec4<f32>(select(max(phi, 1e-4), min(phi, -1e-4), sea), 0.0, 0.0, 0.0));
    outG_store(p, vec4<f32>(select(0.0, 1.0, sea), 0.0, 0.0, 0.0));
  } else if (m == 3) {
    let e = a_at(p).x;
    outF_store(p, vec4<f32>(select(0.5, e, e >= 0.0), 0.0, 0.0, 0.0));
    outG_store(p, vec4<f32>(select(0.0, 1.0, e >= 0.0), 0.0, 0.0, 0.0));
  } else if (m == 4) {
    outU_store(p, select(0u, 1u, a_at(p).x < 0.0));
    outG_store(p, vec4<f32>(select(0.0, 1.0, b_at(p).x < 0.0), 0.0, 0.0, 0.0));
  } else if (m == 5) {
    let cut = a_at(p).x > 0.5;
    let phi = b_at(p).x;
    outF_store(p, vec4<f32>(select(max(phi, 1e-3), min(phi, -1e-3), cut), 0.0, 0.0, 0.0));
    outU_store(p, select(1u, 0u, cut));
  } else if (m == 6) {
    let t = clamp((a_at(p).x - 2.0) / u.uK0, 0.0, 1.0);
    outF_store(p, vec4<f32>(1.0 - t * t * (3.0 - 2.0 * t), 0.0, 0.0, 0.0));
  } else if (m == 7) {
    let w = c_at(p).x;
    outF_store(p, vec4<f32>(a_at(p).x * (1.0 - w) + b_at(p).x * w, 0.0, 0.0, 0.0));
  } else if (m == 8) {
    outF_store(p, vec4<f32>(select(0.0, 1.0, a_at(p).x > 1e-3), 0.0, 0.0, 0.0));
  } else if (m == 9) {
    outF_store(p, vec4<f32>(min(a_at(p).x, b_at(p).x), 0.0, 0.0, 0.0));
  } else if (m == 10) {
    var nz = 0.0;
    if (u.uHas != 0) { nz = a_at(p).x; }
    var th = clamp(u.uK0 + u.uK1 * nz, 30.0, 88.5);
    if (u.uHas2 != 0) { th = th + (u.uK2 - th) * b_at(p).x; }
    outF_store(p, vec4<f32>(th, 0.0, 0.0, 0.0));
  } else if (m == 11) {
    let q = d_at(p);
    outF_store(p, vec4<f32>(select(a_at(p).x, q.y, q.z > 0.5), 0.0, 0.0, 0.0));
  } else {
    outF_store(p, vec4<f32>(select(1e7, -1e7, a_at(p).x > 0.5), 0.0, 0.0, 0.0));
  }
}
