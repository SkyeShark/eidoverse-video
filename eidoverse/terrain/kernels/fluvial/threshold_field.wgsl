// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/fluvial.py threshold() at
// f90c6fc and op_fluvial's Sc, which numpy makes in float64 from the GPU's float32 noise fields:
//     Sc = exp(log(tan threshold_deg) + threshold_noise nt + breakup nb)
//          x (1 + outcrops smoothstep((r - 0.45) / 0.4)) x (1 + threshold_gain)^below_main
//     or an earlier stage's Sc field (uMode.x)
//     Sc = Sc Sc_factor                                   (uMode.y)
//     Sc = max(Sc, 1.1 hypot(gx, gy))                     (uMode.z: mode 'refine', a real place's own slopes stand)
// The tangent's log and the gain's power are computed in doubles on the CPU (PORT_PLAN.md 2.3: kernels never take
// tan of a degree value). float32 here, in numpy's order.
//! sampler nt      unit noise at threshold_scale_m
//! sampler nb      unit noise at the breakup scales the level resolves
//! sampler nr      ridged noise at outcrop_scale_m
//! sampler sc0     an earlier stage's Sc
//! sampler scf     Sc_factor
//! sampler gx
//! sampler gy
//! image   outS r32f
//! uniform float uLnT    log(tan threshold_deg)
//! uniform float uTn
//! uniform float uB
//! uniform float uO
//! uniform float uGain   (1 + threshold_gain)^below_main
//! uniform ivec4 uHas    nt, nb, nr, gain
//! uniform ivec4 uMode   from the field, the factor, refine, 0

fn kmain(p: vec2<i32>) {
  if (!inside(p, outS_size())) { return; }
  var s = 0.0;
  if (u.uMode.x == 1) {
    s = sc0_at(p).x;
  } else {
    var lnS = u.uLnT;
    if (u.uHas.x == 1) { lnS = lnS + u.uTn * nt_at(p).x; }
    if (u.uHas.y == 1) { lnS = lnS + u.uB * nb_at(p).x; }
    s = exp(lnS);
    if (u.uHas.z == 1) {
      let tt = clamp((nr_at(p).x - 0.45) / 0.4, 0.0, 1.0);
      s = s * (1.0 + u.uO * tt * tt * (3.0 - 2.0 * tt));
    }
    if (u.uHas.w == 1) { s = s * u.uGain; }
  }
  if (u.uMode.y == 1) { s = s * scf_at(p).x; }
  if (u.uMode.z == 1) {
    let gxv = gx_at(p).x;
    let gyv = gy_at(p).x;
    s = max(s, 1.1 * sqrt(gxv * gxv + gyv * gyv));
  }
  outS_store(p, vec4<f32>(s, 0.0, 0.0, 0.0));
}
