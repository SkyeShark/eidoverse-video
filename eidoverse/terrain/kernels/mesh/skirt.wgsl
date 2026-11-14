// skirt: the outermost ring's skirt, build/mesh.py _assemble (blender/eidoblend/terrain at f90c6fc). The perimeter
// of ring 0 counter-clockwise from above (idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]: m points) is
// copied twice after the terrain's nv vertices: the top copies where they are, the bottom copies at the lowest
// border height less the drop (float32(z_min - drop): the subtraction of two float32 values is correctly rounded, as
// numpy's float64 one rounded to float32 is). Triangles (t0, b0, b1) for every edge of the perimeter, then (t0, b1,
// t1). The skirt is flat-shaded in Blender (its faces' own normals); its vertices here take their side's outward
// normal (a corner the diagonal), which is that face normal on every face but the four at the corners.
//! include prims/lib
//! sampler zg r32f       ring 0's heights grid, ny x nx
//! sampler ig r32ui      ring 0's vertex numbers
//! sampler lines r32f    the rings' lattice lines (ring 0's first: xm[nx], ym[ny])
//! sampler zmin r32f     the perimeter's lowest height (skirt_min), 1 x 1
//! image   outP r32f     positions, 3 numbers a vertex
//! image   outU r32f     uv, 2 numbers a vertex
//! image   outN r32f     normals, 3 numbers a vertex
//! image   outT r32ui    the index buffer
//! uniform ivec4 uDims   nx, ny, nv (the first skirt vertex), m (the perimeter's points)
//! uniform ivec4 uBase   the first skirt triangle, 0, 0, 0
//! uniform float uDrop   metres

// the lattice point (i, j) of perimeter point k
fn perimeter(k: i32, nx: i32, ny: i32) -> vec2<i32> {
  if (k < nx) { return vec2<i32>(k, 0); }
  if (k < nx + ny - 1) { return vec2<i32>(nx - 1, k - nx + 1); }
  if (k < 2 * nx + ny - 2) { return vec2<i32>(nx - 2 - (k - (nx + ny - 1)), ny - 1); }
  return vec2<i32>(0, ny - 2 - (k - (2 * nx + ny - 2)));
}

fn kmain(p: vec2<i32>) {
  let k = line_index(p);
  let nx = u.uDims.x;
  let ny = u.uDims.y;
  let nv = u32(u.uDims.z);
  let m = u.uDims.w;
  if (k >= m) { return; }
  let q = perimeter(k, nx, ny);
  let x = lines_b[q.x];
  let y = lines_b[nx + q.y];
  let z = zg_b[q.y * nx + q.x];
  let zb = zmin_b[0] - u.uDrop;
  let top = nv + u32(k);
  let bot = nv + u32(m + k);
  outP_b[3u * top] = x;
  outP_b[3u * top + 1u] = z;
  outP_b[3u * top + 2u] = -y;
  outP_b[3u * bot] = x;
  outP_b[3u * bot + 1u] = zb;
  outP_b[3u * bot + 2u] = -y;
  outU_b[2u * top] = x;
  outU_b[2u * top + 1u] = y;
  outU_b[2u * bot] = x;
  outU_b[2u * bot + 1u] = y;
  // outward: +x east, +y north (three.js -z)
  var dx = 0.0;
  var dy = 0.0;
  if (q.x == nx - 1) { dx = 1.0; }
  if (q.x == 0) { dx = -1.0; }
  if (q.y == ny - 1) { dy = 1.0; }
  if (q.y == 0) { dy = -1.0; }
  let nrm = normalize(vec3<f32>(dx, 0.0, -dy));
  for (var c = 0u; c < 3u; c++) {
    outN_b[3u * top + c] = nrm[c];
    outN_b[3u * bot + c] = nrm[c];
  }
  let k1 = (k + 1) % m;
  let t1 = nv + u32(k1);
  let b1 = nv + u32(m + k1);
  let s0 = 3u * u32(u.uBase.x + k);
  outT_b[s0] = top;
  outT_b[s0 + 1u] = bot;
  outT_b[s0 + 2u] = b1;
  let s1 = 3u * u32(u.uBase.x + m + k);
  outT_b[s1] = top;
  outT_b[s1 + 1u] = b1;
  outT_b[s1 + 2u] = t1;
}
