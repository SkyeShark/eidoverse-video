// height_at: RingMesh.height_at for many points, build/mesh.py (blender/eidoblend/terrain at f90c6fc), in its order:
// the point clamped to the outermost window; the finest ring whose window holds it; its lattice cell; the triangle
// by the (i, j) - (i + 1, j + 1) diagonal; and in a quad along the ring's hole, on the half its seam fan replaces,
// the fan's own triangle: the ray from the fan's apex through the point meets the hole's edge, where the height is
// np.interp along the child ring's border line.
//
// Blender (and build/mesh.js heightAt, per query) works in float64 on the float32 vertices; this is float32
// (PORT_PLAN.md 2.3): what samples the rendered ground under many points at once (the depth of the water under
// every lake and sea vertex), within float32 rounding of the triangles.
//! include prims/lib
//! sampler pts r32f      the points, 2 numbers a point: Blender (x, y)
//! sampler zs r32f       every ring's heights grid as written (ny x nx, row-major), one after another
//! sampler lines r32f    every ring's lattice lines in metres (xm[nx] then ym[ny]), one after another
//! sampler ring r32i     8 numbers a ring: nx, ny, its grid's first element in zs, its lines' first entry in lines,
//                        its hole's lattice lines jb, jt, il, ir (jb < 0: no hole)
//! image   outH r32f     one height a point
//! uniform int uCount    the points
//! uniform int uRings    the rings

fn ri(k: i32, f: i32) -> i32 { return ring_b[8 * k + f]; }

// np.searchsorted(a, v, 'right') - 1 over lines[first .. first + n), clamped to a cell: [0, n - 2]
fn locate(first: i32, n: i32, v: f32) -> i32 {
  var lo = 0;
  var hi = n;
  while (lo < hi) {
    let m = (lo + hi) / 2;
    if (lines_b[first + m] <= v) { lo = m + 1; } else { hi = m; }
  }
  return clamp(lo - 1, 0, n - 2);
}

// np.interp(v, xp, fp): xp = lines[first .. first + n), fp[q] = zs[zfirst + q * zstep]
fn interp(first: i32, n: i32, zfirst: i32, zstep: i32, v: f32) -> f32 {
  if (v > lines_b[first + n - 1]) { return zs_b[zfirst + (n - 1) * zstep]; }
  if (v < lines_b[first]) { return zs_b[zfirst]; }
  var lo = 0;
  var hi = n;
  while (lo < hi) {
    let m = (lo + hi) / 2;
    if (lines_b[first + m] <= v) { lo = m + 1; } else { hi = m; }
  }
  let j = lo - 1;
  let f0 = zs_b[zfirst + j * zstep];
  if (j == n - 1) { return f0; }
  let x0 = lines_b[first + j];
  if (x0 == v) { return f0; }
  let slope = (zs_b[zfirst + (j + 1) * zstep] - f0) / (lines_b[first + j + 1] - x0);
  return slope * (v - x0) + f0;
}

fn kmain(p: vec2<i32>) {
  let q = line_index(p);
  if (q >= u.uCount) { return; }
  // the outermost window, and the point clamped to it
  let nx0 = ri(0, 0);
  let ny0 = ri(0, 1);
  let l0 = ri(0, 3);
  let x = clamp(pts_b[2 * q], lines_b[l0], lines_b[l0 + nx0 - 1]);
  let y = clamp(pts_b[2 * q + 1], lines_b[l0 + nx0], lines_b[l0 + nx0 + ny0 - 1]);
  // the finest ring that holds it
  var k = 0;
  for (var c = u.uRings - 1; c >= 1; c--) {
    let cl = ri(c, 3);
    let cnx = ri(c, 0);
    let cny = ri(c, 1);
    if (x >= lines_b[cl] && x <= lines_b[cl + cnx - 1] && y >= lines_b[cl + cnx] && y <= lines_b[cl + cnx + cny - 1]) {
      k = c;
      break;
    }
  }
  let nx = ri(k, 0);
  let ny = ri(k, 1);
  let z0 = ri(k, 2);
  let lx = ri(k, 3);
  let ly = lx + nx;
  let i = locate(lx, nx, x);
  let j = locate(ly, ny, y);
  let xa = lines_b[lx + i];
  let ya = lines_b[ly + j];
  let fx = (x - xa) / (lines_b[lx + i + 1] - xa);
  let fy = (y - ya) / (lines_b[ly + j + 1] - ya);
  let ha = zs_b[z0 + j * nx + i];
  let hb = zs_b[z0 + j * nx + i + 1];
  let hc = zs_b[z0 + (j + 1) * nx + i + 1];
  let hd = zs_b[z0 + (j + 1) * nx + i];
  let lower = fx >= fy;
  var z: f32;
  if (lower) {
    z = ha + fx * (hb - ha) + fy * (hc - hb);
  } else {
    z = ha + fy * (hd - ha) + fx * (hc - hd);
  }
  let jb = ri(k, 4);
  if (jb >= 0) {
    let jt = ri(k, 5);
    let il = ri(k, 6);
    let ir = ri(k, 7);
    let inx = i >= il && i < ir;
    let iny = j >= jb && j < jt;
    // the child ring: its lines, its grid
    let cnx = ri(k + 1, 0);
    let cny = ri(k + 1, 1);
    let cz = ri(k + 1, 2);
    let cl = ri(k + 1, 3);
    var kind = -1;
    if (j == jb - 1 && inx && !lower) {
      kind = 0;              // below the hole: fanned from a = (i, jb - 1) to the child's bottom row
    } else if (j == jt && inx && lower) {
      kind = 1;              // above: from c = (i + 1, jt + 1) to its top row
    } else if (i == il - 1 && iny && lower) {
      kind = 2;              // left: from a = (il - 1, j) to its left column
    } else if (i == ir && iny && !lower) {
      kind = 3;              // right: from c = (ir + 1, j + 1) to its right column
    }
    if (kind >= 0) {
      var qx: f32;
      var qy: f32;
      var qz: f32;
      var edge: f32;
      var s: f32;
      var ze: f32;
      if (kind == 0) {
        qx = lines_b[lx + i]; qy = lines_b[ly + jb - 1]; qz = zs_b[z0 + (jb - 1) * nx + i]; edge = lines_b[ly + jb];
      } else if (kind == 1) {
        qx = lines_b[lx + i + 1]; qy = lines_b[ly + jt + 1]; qz = zs_b[z0 + (jt + 1) * nx + i + 1]; edge = lines_b[ly + jt];
      } else if (kind == 2) {
        qx = lines_b[lx + il - 1]; qy = lines_b[ly + j]; qz = zs_b[z0 + j * nx + il - 1]; edge = lines_b[lx + il];
      } else {
        qx = lines_b[lx + ir + 1]; qy = lines_b[ly + j + 1]; qz = zs_b[z0 + (j + 1) * nx + ir + 1]; edge = lines_b[lx + ir];
      }
      if (kind < 2) {
        // the edge is a row: the ray meets it at y = edge
        s = (y - qy) / (edge - qy);
        let hit = qx + (x - qx) / max(s, 1.0e-30);
        if (kind == 0) { ze = interp(cl, cnx, cz, 1, hit); } else { ze = interp(cl, cnx, cz + (cny - 1) * cnx, 1, hit); }
      } else {
        // a column: at x = edge
        s = (x - qx) / (edge - qx);
        let hit = qy + (y - qy) / max(s, 1.0e-30);
        if (kind == 2) { ze = interp(cl + cnx, cny, cz, cnx, hit); } else { ze = interp(cl + cnx, cny, cz + cnx - 1, cnx, hit); }
      }
      z = qz + s * (ze - qz);
    }
  }
  outH_b[q] = z;
}
