// collider_index: the collider proxy's index buffer (build/collider.js; PORT_PLAN.md 7.5): a run of the mesh's
// triangles (the rings near the focus) with every vertex number counted from the proxy's first vertex, so the proxy
// carries only its own stretch of the vertex buffer and a physics engine is handed no vertex it never uses. The
// triangles and their order are the visual mesh's. Integers only: exact.
//! include prims/lib
//! sampler tri r32ui     the mesh's index buffer, 3 vertex numbers a triangle
//! image   outT r32ui    the proxy's index buffer
//! uniform int uFirst    the first index of the run (3 x its first triangle)
//! uniform int uCount    the run's indices
//! uniform int uBase     the proxy's first vertex

fn kmain(p: vec2<i32>) {
  let q = line_index(p);
  if (q >= u.uCount) { return; }
  outT_b[q] = tri_b[u.uFirst + q] - u32(u.uBase);
}
