// ring_attribute: one point attribute of the mesh, build/mesh.py _assemble (blender/eidoblend/terrain at 3dda52e):
// vals[name][v] = lat[j, i] for the lattice points a ring adds (uMode 0, a pass over the ring's lattice), then the
// skirt's copies, vals[name][perim] twice after the terrain's vertices (uMode 1, a pass over ring 0's perimeter,
// counter-clockwise from the south-west corner as kernels/mesh/skirt.wgsl walks it). The lattice is ring_heights'
// with uKind 1 (a mask, bilinear) or 2. With uLevel >= 0 the value written is that number instead: eido_level, the
// level each vertex's ring draws. A debug option (makeTerrain's meshMasks): the material reads data textures, not
// attributes.
//! include prims/lib
//! sampler zg r32f       the ring's lattice of the attribute, ny x nx (any field when uLevel >= 0)
//! sampler ig r32ui      the ring's vertex numbers (ring_index)
//! image   outA r32f     the attribute, one number a vertex
//! uniform ivec4 uDims   nx, ny, v0 (uMode 0) or nv, the first skirt vertex (uMode 1), m (the perimeter's points)
//! uniform int uMode     0: the ring's own vertices; 1: the skirt's copies of ring 0's perimeter
//! uniform int uLevel    -1: the lattice's values; else this number

// the lattice point (i, j) of perimeter point k (kernels/mesh/skirt.wgsl)
fn perimeter(k: i32, nx: i32, ny: i32) -> vec2<i32> {
  if (k < nx) { return vec2<i32>(k, 0); }
  if (k < nx + ny - 1) { return vec2<i32>(nx - 1, k - nx + 1); }
  if (k < 2 * nx + ny - 2) { return vec2<i32>(nx - 2 - (k - (nx + ny - 1)), ny - 1); }
  return vec2<i32>(0, ny - 2 - (k - (2 * nx + ny - 2)));
}

fn kmain(p: vec2<i32>) {
  let nx = u.uDims.x;
  let ny = u.uDims.y;
  if (u.uMode == 1) {
    let k = line_index(p);
    let m = u.uDims.w;
    if (k >= m) { return; }
    let q = perimeter(k, nx, ny);
    var a = f32(u.uLevel);
    if (u.uLevel < 0) { a = zg_b[q.y * nx + q.x]; }
    outA_b[u32(u.uDims.z + k)] = a;
    outA_b[u32(u.uDims.z + m + k)] = a;
    return;
  }
  if (p.x >= nx || p.y >= ny) { return; }
  let v = ig_b[p.y * nx + p.x];
  if (v == NONE || v < u32(u.uDims.z)) { return; }
  var a = f32(u.uLevel);
  if (u.uLevel < 0) { a = zg_b[p.y * nx + p.x]; }
  outA_b[v] = a;
}
