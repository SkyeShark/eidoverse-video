// Port of blender/eidoblend/flora/field.py and plantgeo.py (create_flora's blade prototype as a Blender mesh) as used
// by blender/eidoblend/terrain/build/plant_instances.py at f9fba8c, as a GPU kernel (the port's own step: the header of
// build/plant_instances.js says why).
// plants/blade_corners: a createFlora blade prototype's triangles, per corner what its vertex gathers
// (plants/blade_vertices): the face's unit normal ((c - b) x (a - b), the winding three.js and Blender share), its
// UV gradients dP/du and dP/dv (unit), each weighted by the corner's angle (Blender's smooth vertex normals weigh
// the faces by their corner angles; MikkTSpace weighs its per-face tangents the same way), and the corner's vertex.
// Per corner 9 numbers: normal 0-2, tangent (dP/du) 3-5, bitangent (dP/dv) 6-8.
//! include plants/lib
//! sampler pos r32f      the prototype's positions, 3 numbers a vertex
//! sampler uvs r32f      its uvs, 2 a vertex
//! sampler idx r32ui     its triangles, 3 vertex indices each
//! image   outC r32f     per corner its 9 numbers
//! image   outK r32ui    per corner its vertex
//! uniform int uCount    the triangles

fn vtx(i: u32) -> vec3<f32> { return vec3<f32>(pos_b[3u * i], pos_b[3u * i + 1u], pos_b[3u * i + 2u]); }
fn tex(i: u32) -> vec2<f32> { return vec2<f32>(uvs_b[2u * i], uvs_b[2u * i + 1u]); }

fn unit(v: vec3<f32>) -> vec3<f32> {
  let l = length(v);
  return select(vec3<f32>(0.0), v / l, l > 0.0);
}

// the angle at a between the edges toward b and c
fn corner(a: vec3<f32>, b: vec3<f32>, c: vec3<f32>) -> f32 {
  let e1 = unit(b - a);
  let e2 = unit(c - a);
  return acos(clamp(dot(e1, e2), -1.0, 1.0));
}

fn kmain(p: vec2<i32>) {
  let t = lin(p);
  if (t >= u.uCount) { return; }
  let ia = idx_b[3 * t];
  let ib = idx_b[3 * t + 1];
  let ic = idx_b[3 * t + 2];
  let a = vtx(ia);
  let b = vtx(ib);
  let c = vtx(ic);
  let n = unit(cross(c - b, a - b));
  // the UV gradients of the face: e1 = du1 T + dv1 B, e2 = du2 T + dv2 B
  let e1 = b - a;
  let e2 = c - a;
  let d1 = tex(ib) - tex(ia);
  let d2 = tex(ic) - tex(ia);
  let det = d1.x * d2.y - d2.x * d1.y;
  var tu = vec3<f32>(0.0);
  var tv = vec3<f32>(0.0);
  if (abs(det) > 1.0e-20) {
    tu = unit((e1 * d2.y - e2 * d1.y) / det);
    tv = unit((e2 * d1.x - e1 * d2.x) / det);
  }
  var w = array<f32, 3>(corner(a, b, c), corner(b, c, a), corner(c, a, b));
  var vs = array<u32, 3>(ia, ib, ic);
  for (var k = 0; k < 3; k++) {
    let q = 3 * t + k;
    let o = 9 * q;
    let g = w[k];
    outC_b[o] = n.x * g;
    outC_b[o + 1] = n.y * g;
    outC_b[o + 2] = n.z * g;
    outC_b[o + 3] = tu.x * g;
    outC_b[o + 4] = tu.y * g;
    outC_b[o + 5] = tu.z * g;
    outC_b[o + 6] = tv.x * g;
    outC_b[o + 7] = tv.y * g;
    outC_b[o + 8] = tv.z * g;
    outK_b[q] = vs[k];
  }
}
