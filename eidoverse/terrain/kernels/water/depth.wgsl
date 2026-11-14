// depth: the water's depth to the rendered ground under each vertex, build/water.py's eido_water attribute
// (blender/eidoblend/terrain at f90c6fc): max(level - height_at(x, y), 0), the water material's tint. The level is
// the vertex's own height (three.js y); the ground is kernels/mesh/height_at.wgsl's. float32, where Blender
// subtracts in float64 and rounds once.
//! include prims/lib
//! sampler pos r32f      positions, 3 numbers a vertex (three.js axes)
//! sampler ground r32f   the rendered ground under each vertex
//! image   outD r32f     one depth a vertex
//! uniform int uCount    the vertices

fn kmain(p: vec2<i32>) {
  let v = line_index(p);
  if (v >= u.uCount) { return; }
  outD_b[v] = max(pos_b[3 * v + 1] - ground_b[v], 0.0);
}
