// sea_grid: the sea's surface, build/water.py sea_object (blender/eidoblend/terrain at f90c6fc): an n x n grid of
// vertices over the outermost window at sea level, verts[j n + i] = (xs[i], ys[j], sea level), and its quads
// (idx[j, i], idx[j, i + 1], idx[j + 1, i + 1], idx[j + 1, i]) in row-major order, each written as two triangles
// (a three.js index buffer holds triangles). xs and ys are np.linspace's float64 values rounded once to float32 in
// JavaScript (build/water.js). Positions in three.js axes (x, level, -y); flat water: every normal is up; and the
// points (x, y) for the ground sampler.
//! sampler xs r32f       n values
//! sampler ys r32f       n values
//! image   outP r32f     positions, 3 numbers a vertex
//! image   outN r32f     normals, 3 numbers a vertex
//! image   outQ r32f     Blender (x, y), 2 numbers a vertex
//! image   outT r32ui    6 vertex numbers a quad
//! uniform int uN        vertices a side
//! uniform float uLevel  the sea's level, metres

fn kmain(p: vec2<i32>) {
  let n = u.uN;
  if (p.x >= n || p.y >= n) { return; }
  let v = p.y * n + p.x;
  let x = xs_b[p.x];
  let y = ys_b[p.y];
  outP_b[3 * v] = x;
  outP_b[3 * v + 1] = u.uLevel;
  outP_b[3 * v + 2] = -y;
  outN_b[3 * v] = 0.0;
  outN_b[3 * v + 1] = 1.0;
  outN_b[3 * v + 2] = 0.0;
  outQ_b[2 * v] = x;
  outQ_b[2 * v + 1] = y;
  if (p.x < n - 1 && p.y < n - 1) {
    let o = 6 * (p.y * (n - 1) + p.x);
    let a = u32(v);
    let b = u32(v + 1);
    let c = u32(v + n + 1);
    let d = u32(v + n);
    outT_b[o] = a;
    outT_b[o + 1] = b;
    outT_b[o + 2] = c;
    outT_b[o + 3] = a;
    outT_b[o + 4] = c;
    outT_b[o + 5] = d;
  }
}
