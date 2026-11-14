// lake_vertices: the vertices of a level's lake surfaces, build/water.py lake_geometry (blender/eidoblend/terrain at
// f90c6fc): v = (x0 + ci cell, y0 + cj cell, the lake's level) for each (lake, corner) of the sorted stream
// (lake_corners), written in three.js axes (x, level, -y) (PORT_PLAN.md 2.2). The corner lines are Blender's
// float64 values rounded once to float32 in JavaScript (build/water.js), and the levels likewise, so the positions
// are the float32 vertices Blender's mesh holds. Flat water: every normal is up. Also the points (x, y) for the
// ground sampler (kernels/mesh/height_at.wgsl), which gives the depth under each vertex.
//! include prims/lib
//! sampler vRank r32ui     the vertices in order: each one's lake
//! sampler vCorner r32ui   and its corner (row-major on the (n + 1) x (n + 1) corner lattice)
//! sampler xl r32f         the corner lines: x0 + ci cell, n + 1 of them
//! sampler yl r32f         y0 + cj cell
//! sampler level r32f      each lake's level, metres
//! image   outP r32f       positions, 3 numbers a vertex
//! image   outN r32f       normals, 3 numbers a vertex
//! image   outQ r32f       Blender (x, y), 2 numbers a vertex
//! uniform int uCount      the vertices
//! uniform int uN          the level's cells a side

fn kmain(p: vec2<i32>) {
  let v = line_index(p);
  if (v >= u.uCount) { return; }
  let c = i32(vCorner_b[v]);
  let m = u.uN + 1;
  let x = xl_b[c % m];
  let y = yl_b[c / m];
  let o = 3 * v;
  outP_b[o] = x;
  outP_b[o + 1] = level_b[vRank_b[v]];
  outP_b[o + 2] = -y;
  outN_b[o] = 0.0;
  outN_b[o + 1] = 1.0;
  outN_b[o + 2] = 0.0;
  outQ_b[2 * v] = x;
  outQ_b[2 * v + 1] = y;
}
