// Port of blender/eidoblend/flora/field.py, plantgeo.py and vegetation.py (create_flora's blade prototype as a Blender
// mesh) as used by blender/eidoblend/terrain/build/plant_instances.py at f9fba8c, as a GPU kernel (the port's own
// step: the header of build/plant_instances.js says why).
// plants/blade_vertices: per vertex of a createFlora blade prototype what Blender's blade material reads: its smooth
// normal (the corner-angle-weighted face normals of plants/blade_corners, summed and unit: a Blender mesh's own vertex
// normal, which create_flora's blades keep, custom_normals=False), its UV tangent (the angle-weighted dP/du, made
// orthogonal to the normal and unit, with MikkTSpace's sign: +1 where normal x tangent runs along dP/dv), and the
// 'across' coordinate vegetation.py bunch_geometry gives the blades (-1, +1 at each loop's two edges, by vertex order:
// np.tile([-1, 1], n / 2)). Per vertex 8 numbers: normal 0-2, tangent 3-5, its sign 6, across 7.
//! include plants/lib
//! sampler crn r32f      per corner its 9 numbers (plants/blade_corners)
//! sampler order r32ui   the corners sorted by their vertex
//! sampler starts r32ui  per vertex its first corner in `order`
//! sampler counts r32ui  per vertex its corners
//! image   outF r32f     per vertex its 8 numbers
//! uniform int uCount    the vertices

fn kmain(p: vec2<i32>) {
  let v = lin(p);
  if (v >= u.uCount) { return; }
  var n = vec3<f32>(0.0);
  var t = vec3<f32>(0.0);
  var b = vec3<f32>(0.0);
  let first = starts_b[v];
  let m = counts_b[v];
  for (var k = 0u; k < m; k++) {
    let o = 9u * order_b[first + k];
    n += vec3<f32>(crn_b[o], crn_b[o + 1u], crn_b[o + 2u]);
    t += vec3<f32>(crn_b[o + 3u], crn_b[o + 4u], crn_b[o + 5u]);
    b += vec3<f32>(crn_b[o + 6u], crn_b[o + 7u], crn_b[o + 8u]);
  }
  let ln = length(n);
  n = select(vec3<f32>(0.0, 1.0, 0.0), n / ln, ln > 0.0);
  t = t - n * dot(n, t);
  let lt = length(t);
  t = select(vec3<f32>(1.0, 0.0, 0.0), t / lt, lt > 0.0);
  let sgn = select(1.0, -1.0, dot(cross(n, t), b) < 0.0);
  let o = 8 * v;
  outF_b[o] = n.x;
  outF_b[o + 1] = n.y;
  outF_b[o + 2] = n.z;
  outF_b[o + 3] = t.x;
  outF_b[o + 4] = t.y;
  outF_b[o + 5] = t.z;
  outF_b[o + 6] = sgn;
  outF_b[o + 7] = select(-1.0, 1.0, (v & 1) == 1);
}
