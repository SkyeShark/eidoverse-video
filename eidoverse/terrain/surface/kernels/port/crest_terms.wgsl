// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). crest_terms: crest's term at fixed metre scales (bake.py _Baker._crest_metres), up to four at
// once from one blur4 of the padded height:
//     t_s = tanh((hp - G_s hp) / (tau s))       channel c of b holds G_s hp, uDen.c = float32(tau s)
// written to o0..o3 (a channel whose uDen is 0 writes nothing: its image is a stand-in). numpy's float32
// np.tanh((hp - b[..., c]) / F(tau * S[k])).
//! sampler hp
//! sampler b
//! image   o0 r32f
//! image   o1 r32f
//! image   o2 r32f
//! image   o3 r32f
//! uniform vec4 uDen

fn kmain(p: vec2<i32>) {
  let n = hp_size();
  if (!inside(p, n)) { return; }
  let h = hp_at(p).x;
  let g = b_at(p);
  if (u.uDen.x > 0.0) { o0_store(p, vec4<f32>(tanh((h - g.x) / u.uDen.x), 0.0, 0.0, 0.0)); }
  if (u.uDen.y > 0.0) { o1_store(p, vec4<f32>(tanh((h - g.y) / u.uDen.y), 0.0, 0.0, 0.0)); }
  if (u.uDen.z > 0.0) { o2_store(p, vec4<f32>(tanh((h - g.z) / u.uDen.z), 0.0, 0.0, 0.0)); }
  if (u.uDen.w > 0.0) { o3_store(p, vec4<f32>(tanh((h - g.w) / u.uDen.w), 0.0, 0.0, 0.0)); }
}
