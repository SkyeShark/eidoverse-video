// plants/merge_instances: one foliage part of a SeedThree level (an InstancedMesh: a leaf or card geometry and a
// matrix per leaf) as the vertices of one plain mesh (build/plant_instances.js partGeometry; what the Blender
// edition's grown plant holds as mesh data): every instance's matrix applied to the part's vertices, its normals by
// the matrix's cofactors (the inverse transpose up to the determinant's sign), its instanced numbers copied onto its
// vertices. Per merged vertex 15 numbers: position 0-2, normal 3-5, uv 6-7, aThickness 8, aWindVec 9-11,
// aAnchorPos 12-14. Exact up to float32 rounding of one matrix product.
//! include plants/lib
//! sampler pos r32f      the part's vertex positions, 3 numbers each
//! sampler nrm r32f      its normals, 3 each
//! sampler uvs r32f      its uvs, 2 each
//! sampler mats r32f     per instance its matrix, 16 numbers, column-major (three.js)
//! sampler ith r32f      per instance its aThickness
//! sampler iwv r32f      per instance its aWindVec, 3 each
//! sampler iap r32f      per instance its aAnchorPos, 3 each
//! image   outV r32f     per merged vertex its 15 numbers
//! uniform vec4 uL0      the part's own matrix in the level's frame (columns; an identity for SeedThree's parts)
//! uniform vec4 uL1
//! uniform vec4 uL2
//! uniform vec4 uL3
//! uniform int uNv       the part's vertices
//! uniform int uCount    instances x uNv

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let j = q / u.uNv;
  let v = q - j * u.uNv;
  let m = 16 * j;
  let L = mat4x4<f32>(u.uL0, u.uL1, u.uL2, u.uL3);
  let Mi = mat4x4<f32>(vec4<f32>(mats_b[m], mats_b[m + 1], mats_b[m + 2], mats_b[m + 3]),
                       vec4<f32>(mats_b[m + 4], mats_b[m + 5], mats_b[m + 6], mats_b[m + 7]),
                       vec4<f32>(mats_b[m + 8], mats_b[m + 9], mats_b[m + 10], mats_b[m + 11]),
                       vec4<f32>(mats_b[m + 12], mats_b[m + 13], mats_b[m + 14], mats_b[m + 15]));
  let Mm = L * Mi;
  let c0 = Mm[0].xyz;
  let c1 = Mm[1].xyz;
  let c2 = Mm[2].xyz;
  let t = Mm[3].xyz;
  let P = vec3<f32>(pos_b[3 * v], pos_b[3 * v + 1], pos_b[3 * v + 2]);
  let N = vec3<f32>(nrm_b[3 * v], nrm_b[3 * v + 1], nrm_b[3 * v + 2]);
  let wp = c0 * P.x + c1 * P.y + c2 * P.z + t;
  // the inverse transpose times det: columns c1 x c2, c2 x c0, c0 x c1
  var wn = cross(c1, c2) * N.x + cross(c2, c0) * N.y + cross(c0, c1) * N.z;
  if (dot(c0, cross(c1, c2)) < 0.0) { wn = -wn; }
  let L = length(wn);
  if (L > 0.0) { wn = wn / L; }
  let o = 15 * q;
  outV_b[o] = wp.x;
  outV_b[o + 1] = wp.y;
  outV_b[o + 2] = wp.z;
  outV_b[o + 3] = wn.x;
  outV_b[o + 4] = wn.y;
  outV_b[o + 5] = wn.z;
  outV_b[o + 6] = uvs_b[2 * v];
  outV_b[o + 7] = uvs_b[2 * v + 1];
  outV_b[o + 8] = ith_b[j];
  outV_b[o + 9] = iwv_b[3 * j];
  outV_b[o + 10] = iwv_b[3 * j + 1];
  outV_b[o + 11] = iwv_b[3 * j + 2];
  outV_b[o + 12] = iap_b[3 * j];
  outV_b[o + 13] = iap_b[3 * j + 1];
  outV_b[o + 14] = iap_b[3 * j + 2];
}
