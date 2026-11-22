// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c (its flora strokes' sky light as EEVEE gives it
// inside a sward), as a GPU kernel (the port's own step: the header of build/plant_instances.js says why).
// plants/tri_area: per triangle of a geometry (positions 3 numbers a vertex, an index), its area: a flora prototype's
// card area, for the leaf area a plant carries.
//! include plants/lib
//! sampler pos r32f      the positions, 3 numbers a vertex
//! sampler idx r32ui     the triangles, 3 vertex indices each
//! image   outA r32f     per triangle its area
//! uniform int uCount    the triangles

fn vp(i: u32) -> vec3<f32> { return vec3<f32>(pos_b[3u * i], pos_b[3u * i + 1u], pos_b[3u * i + 2u]); }

fn kmain(p: vec2<i32>) {
  let t = lin(p);
  if (t >= u.uCount) { return; }
  let a = vp(idx_b[3 * t]);
  let b = vp(idx_b[3 * t + 1]);
  let c = vp(idx_b[3 * t + 2]);
  outA_b[t] = 0.5 * length(cross(b - a, c - a));
}
