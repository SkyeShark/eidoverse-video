// normals: the terrain vertices' shading normals, build/mesh.py RingMesh.vertex_normals (blender/eidoblend/terrain at
// f90c6fc): at each vertex the sum over its triangles (the skirt's excluded) of the triangle's unit face normal
// times the triangle's angle at that corner, normalised. Blender scatters the sums with np.bincount; this is a
// gather, with no atomics (PORT_PLAN.md 7.3): the corners are sorted by vertex once (core/prims.js sortPairs, a
// stable radix sort, so each vertex's corners stay in triangle order), and every vertex sums its own in that fixed
// order. float32 cross products and angles against Blender's float64 (within 1e-5 rad). The angle is
// atan2(|e1 x e2|, e1 . e2), Blender's arccos(e1 . e2 / (|e1| |e2|)) written in the form that keeps float32 accuracy
// at every angle (arccos loses it near 0 and pi). Positions are three.js's axes (x, z, -y): a rotation, under which
// cross products and angles are the same, so the normals come out in those axes.
//! include prims/lib
//! sampler pos r32f      positions, 3 numbers a vertex
//! sampler tri r32ui     the index buffer, 3 vertex numbers a triangle
//! sampler start r32ui   each vertex's first corner in the sorted list (an exclusive scan of the counts)
//! sampler count r32ui   each vertex's corners
//! sampler corner r32ui  corner numbers (3 x triangle + its corner) sorted by vertex
//! image   outN r32f     normals, 3 numbers a vertex
//! uniform int uCount    the terrain's vertices (the skirt's after them are not touched)

fn vtx(v: u32) -> vec3<f32> { return vec3<f32>(pos_b[3u * v], pos_b[3u * v + 1u], pos_b[3u * v + 2u]); }

fn kmain(p: vec2<i32>) {
  let v = line_index(p);
  if (v >= u.uCount) { return; }
  let s0 = start_b[v];
  let nc = count_b[v];
  var acc = vec3<f32>(0.0);
  for (var s = 0u; s < nc; s++) {
    let c = corner_b[s0 + s];
    let t = c / 3u;
    let q = c % 3u;
    let p0 = vtx(tri_b[3u * t]);
    let p1 = vtx(tri_b[3u * t + 1u]);
    let p2 = vtx(tri_b[3u * t + 2u]);
    var fnv = cross(p1 - p0, p2 - p0);
    let len = length(fnv);
    if (len > 0.0) { fnv = fnv / len; }
    var pa = p0;
    var pb = p1;
    var pc = p2;
    if (q == 1u) { pa = p1; pb = p2; pc = p0; }
    if (q == 2u) { pa = p2; pb = p0; pc = p1; }
    let e1 = pb - pa;
    let e2 = pc - pa;
    let ang = atan2(length(cross(e1, e2)), dot(e1, e2));
    acc += fnv * ang;
  }
  let l = length(acc);
  if (l > 0.0) { acc = acc / l; }
  let o = 3u * u32(v);
  outN_b[o] = acc.x;
  outN_b[o + 1u] = acc.y;
  outN_b[o + 2u] = acc.z;
}
