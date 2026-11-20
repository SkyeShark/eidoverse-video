// Port of blender/eidoblend/terrain/solvers/volcanic.py _reach at f90c6fc, after core/prims.js label: 1 on the
// 8-connected parts of a mask that hold a seed, 0 elsewhere. numpy:
//     lab, n = label(mask); s = seeds | (the vent's cell); keep[unique(lab[s & mask])] = True; keep[0] = False
//     return keep[lab] (or the mask itself when no part holds a seed)
// uMode 0 marks the kept labels (keep[lab] = 1 where a seed lies on the mask; keep is atomic, zeroed first); uMode 1
// writes keep[lab] (or the mask when uAll is 1) as 0 / 1. The port's own kernel: integers only, exact.
//! sampler lab r32ui     the labels (0: off the mask)
//! sampler seeds         1 on the seeds (a stand-in when uSeeds is 0)
//! image   keep atomic_u32   one per label, n + 1
//! image   outF r32f         mode 1: the reach (a stand-in in mode 0)
//! uniform int uMode
//! uniform int uSeeds
//! uniform ivec2 uVent   the vent's cell (-1: off the level)
//! uniform int uAll

fn kmain(p: vec2<i32>) {
  let n = lab_size();
  if (!inside(p, n)) { return; }
  let L = lab_at(p);
  if (u.uMode == 0) {
    if (L == 0u) { return; }
    var s = all(p == u.uVent);
    if (u.uSeeds != 0) { s = s || seeds_at(p).x > 0.5; }
    if (s) { atomicStore(&keep_b[L], 1u); }
    return;
  }
  var v = 0.0;
  if (u.uAll != 0) { v = select(0.0, 1.0, L > 0u); } else if (L > 0u) { v = f32(atomicLoad(&keep_b[L])); }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
