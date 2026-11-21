// plants/grid.wgsl (`//! include plants/grid`, after plants/lib): the hashed grid the neighbour searches share
// (plants.py _pairs: every pair of points at most `reach` apart, on a grid of reach-sized cells; here the cells are
// hashed into a table of a power of two buckets, and every candidate pair is still tested by its distance). A kernel
// that includes it declares the grid's uniforms: uGO (vec4: the origin's x and y, integer part and fraction), uGW
// (ivec2: 2^40 / cell, hi and lo as int bits), uGInv (float: 1 / cell) and uGMask (int: buckets - 1).

fn gcell(pos: vec4<f32>) -> vec2<i32> {
  let W = vec2<u32>(bitcast<u32>(u.uGW.x), bitcast<u32>(u.uGW.y));
  let gx = coord_div(coord_add(vec2<f32>(pos.x - u.uGO.x, 0.0), pos.y - u.uGO.y), W, 40u, u.uGInv);
  let gy = coord_div(coord_add(vec2<f32>(pos.z - u.uGO.z, 0.0), pos.w - u.uGO.w), W, 40u, u.uGInv);
  return vec2<i32>(i32(gx.x), i32(gy.x));
}

fn gkey(c: vec2<i32>) -> u32 {
  var h = bitcast<u32>(c.x) * 0x9E3779B1u ^ (bitcast<u32>(c.y) * 0x85EBCA77u + 0x165667B1u);
  h = (h ^ (h >> 15u)) * 0x2C1B3C6Du;
  h = h ^ (h >> 12u);
  return h & bitcast<u32>(u.uGMask);
}
