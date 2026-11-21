// plants/ground_normal: RingMesh.normal_at(x, y, smooth=False) for many points (build/mesh.py at f90c6fc, as
// build/mesh.js normalAt transcribes it), the face normal the spots carry (plants.py _Ground.normal_at): the point
// clamped to the outermost window, the finest ring whose window holds it, its lattice cell, the triangle by the
// (i, j) - (i + 1, j + 1) diagonal, (-gx, -gy, 1) normalised. The rings' tables are build/mesh.js heightField's
// (kernels/mesh/height_at.wgsl reads the same three, in the same layout). Blender locates the spot's float64
// position; here the spot's position as integer part and fraction (plants/lib.wgsl) is compared with the lattice
// lines and gives the fractions in the cell, so the triangle a spot near a diagonal stands on is Blender's but for
// micrometre ties (a float32 position would decide it within 1 mm). The normal is float32 arithmetic on the float32
// vertices, as Blender's is float64 on the same vertices.
//! include prims/lib
//! include plants/lib
//! sampler kp r32ui      the spots' records (16 numbers each: the position at 0-3)
//! sampler zs r32f       every ring's heights grid as written (ny x nx, row-major), one after another
//! sampler lines r32f    every ring's lattice lines in metres (xm[nx] then ym[ny]), one after another
//! sampler ring r32i     8 numbers a ring: nx, ny, its grid's first element in zs, its lines' first entry in lines,
//                        its hole's lattice lines (unread here)
//! image   outN r32f     3 numbers a point: nx, ny, nz (Blender axes)
//! uniform int uCount    the points
//! uniform int uRings    the rings

fn ri(k: i32, f: i32) -> i32 { return ring_b[8 * k + f]; }

// a lattice line as a coordinate (integer part, fraction): exact
fn line_c(k: i32) -> vec2<f32> {
  let v = lines_b[k];
  let i = floor(v);
  return vec2<f32>(i, v - i);
}

// v - line k, metres
fn from_line(c: vec2<f32>, k: i32) -> f32 { return coord_sub(c, line_c(k)); }

// np.searchsorted(lines[first .. first + n), v, 'right') - 1, clamped to a cell: [0, n - 2]
fn locate(first: i32, n: i32, c: vec2<f32>) -> i32 {
  var lo = 0;
  var hi = n;
  while (lo < hi) {
    let m = (lo + hi) / 2;
    if (from_line(c, first + m) >= 0.0) { lo = m + 1; } else { hi = m; }
  }
  return clamp(lo - 1, 0, n - 2);
}

// a coordinate clamped to [line a, line b]
fn clamp_c(c: vec2<f32>, a: i32, b: i32) -> vec2<f32> {
  if (from_line(c, a) < 0.0) { return line_c(a); }
  if (from_line(c, b) > 0.0) { return line_c(b); }
  return c;
}

fn kmain(p: vec2<i32>) {
  let q = line_index(p);
  if (q >= u.uCount) { return; }
  let o = 16u * u32(q);
  var cx = vec2<f32>(bitcast<f32>(kp_b[o]), bitcast<f32>(kp_b[o + 1u]));
  var cy = vec2<f32>(bitcast<f32>(kp_b[o + 2u]), bitcast<f32>(kp_b[o + 3u]));
  let nx0 = ri(0, 0);
  let ny0 = ri(0, 1);
  let l0 = ri(0, 3);
  cx = clamp_c(cx, l0, l0 + nx0 - 1);
  cy = clamp_c(cy, l0 + nx0, l0 + nx0 + ny0 - 1);
  var k = 0;
  for (var c = u.uRings - 1; c >= 1; c--) {
    let cl = ri(c, 3);
    let cnx = ri(c, 0);
    let cny = ri(c, 1);
    if (from_line(cx, cl) >= 0.0 && from_line(cx, cl + cnx - 1) <= 0.0 &&
        from_line(cy, cl + cnx) >= 0.0 && from_line(cy, cl + cnx + cny - 1) <= 0.0) {
      k = c;
      break;
    }
  }
  let nx = ri(k, 0);
  let z0 = ri(k, 2);
  let lx = ri(k, 3);
  let ly = lx + nx;
  let ny = ri(k, 1);
  let i = locate(lx, nx, cx);
  let j = locate(ly, ny, cy);
  let dx = lines_b[lx + i + 1] - lines_b[lx + i];
  let dy = lines_b[ly + j + 1] - lines_b[ly + j];
  let fx = from_line(cx, lx + i) / dx;
  let fy = from_line(cy, ly + j) / dy;
  let ha = zs_b[z0 + j * nx + i];
  let hb = zs_b[z0 + j * nx + i + 1];
  let hc = zs_b[z0 + (j + 1) * nx + i + 1];
  let hd = zs_b[z0 + (j + 1) * nx + i];
  var gx: f32;
  var gy: f32;
  if (fx >= fy) {
    gx = (hb - ha) / dx;
    gy = (hc - hb) / dy;
  } else {
    gx = (hc - hd) / dx;
    gy = (hd - ha) / dy;
  }
  let l = sqrt(gx * gx + gy * gy + 1.0);
  outN_b[3 * q] = -gx / l;
  outN_b[3 * q + 1] = -gy / l;
  outN_b[3 * q + 2] = 1.0 / l;
}
