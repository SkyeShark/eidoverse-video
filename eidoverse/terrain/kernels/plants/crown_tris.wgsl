// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c (its SeedThree plants' sky light as EEVEE gives
// it inside a crown), as a GPU kernel (the port's own step: the header of build/plant_instances.js says why).
// plants/crown_tris: per triangle of a SeedThree level's merged foliage part (plants/merge_instances' 15 numbers a
// vertex), its area and where its centroid lies from the crown's centre: across (the horizontal distance) and along
// (the vertical one, unsigned), for the crown's leaf area and its extent (build/plant_instances.js crownOf).
//! include plants/lib
//! sampler vtx r32f      the merged vertices, 15 numbers each (position 0-2)
//! sampler idx r32ui     the triangles, 3 vertex indices each
//! image   outA r32f     per triangle its area
//! image   outH r32f     per triangle its centroid's horizontal distance from the centre
//! image   outV r32f     per triangle its centroid's vertical distance from the centre
//! uniform vec4 uC       the crown's centre in the level's frame (xyz)
//! uniform int uCount    the triangles

fn vpos(i: u32) -> vec3<f32> { return vec3<f32>(vtx_b[15u * i], vtx_b[15u * i + 1u], vtx_b[15u * i + 2u]); }

fn kmain(p: vec2<i32>) {
  let t = lin(p);
  if (t >= u.uCount) { return; }
  let a = vpos(idx_b[3 * t]);
  let b = vpos(idx_b[3 * t + 1]);
  let c = vpos(idx_b[3 * t + 2]);
  outA_b[t] = 0.5 * length(cross(b - a, c - a));
  let g = (a + b + c) / 3.0 - u.uC.xyz;
  outH_b[t] = length(g.xz);
  outV_b[t] = abs(g.y);
}
