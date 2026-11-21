// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/view: plants.py _view's choice (blender/eidoblend/terrain/build/plants.py at f9fba8c) over one species'
// placed plants: within its radius R of the focus, at least lod_m_per_m x their distance tall, and kept by
// _u(id, 14) < 1 - _smooth(f0 R, f1 R, d) over the fade band; with the key max_count's cap sorts by,
// size / max(d, 1) (the smallest for their distance go first). These never move a plant: they choose which the plan
// returns.
//! include plants/lib
//! sampler cand r32ui    the placed plants' records (16 numbers each: id 4-5, size 7, dist 9)
//! image   outF r32ui    1: returned
//! image   outK r32f     the cap's key
//! uniform vec4 uV       R, lod_m_per_m, f0 R, f1 R
//! uniform int  uFade    1 when the fade band is not empty (f1 > f0)
//! uniform int  uCount

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o = 16u * u32(i);
  let id = vec2<u32>(cand_b[o + 4u], cand_b[o + 5u]);
  let size = bitcast<f32>(cand_b[o + 7u]);
  let d = bitcast<f32>(cand_b[o + 9u]);
  var keep = d <= u.uV.x && size >= u.uV.y * d;
  if (keep && u.uFade != 0) {
    let t = clamp((d - u.uV.z) / (u.uV.w - u.uV.z), 0.0, 1.0);
    keep = u53_lt(u53(id, 14u), 1.0 - t * t * (3.0 - 2.0 * t));
  }
  outF_b[i] = select(0u, 1u, keep);
  outK_b[i] = size / max(d, 1.0);
}
