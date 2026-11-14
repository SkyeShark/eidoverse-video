// ring_fans: the seam fans of one ring into the index buffer, build/mesh.py _ring_triangles and _fan (blender/
// eidoblend/terrain at f90c6fc). Each quad along the hole has one edge on the hole, where the child ring has
// vertices between this ring's two: the half of the quad on that edge is drawn as a fan from its far corner p
// through q, the child's in-between vertices, and r, so no T-junction is left: triangles (p, pts[s], pts[s + 1]),
// pts = [q, mids..., r]. Blender's order: for every column of the hole, the fan below it (p = a, q = c, r = d,
// the child's bottom row from right to left) then the one above (p = c, q = a, r = b, its top row left to right);
// then for every row, the fan to the left (p = a, q = b, r = c, its left column upwards) and to the right (p = c,
// q = d, r = a, its right column downwards). build/mesh.js lists the fans (a few thousand a ring) with each one's
// first triangle; one invocation per triangle finds its fan by bisection. Exact.
//! include prims/lib
//! sampler ig r32ui      this ring's vertex numbers, ny x nx
//! sampler cg r32ui      the child ring's vertex numbers, cny x cnx
//! sampler fan r32i      the rings' fan tables (build/mesh.js FANS layout); this ring's at uFan.x
//! image   outT r32ui    the index buffer
//! uniform ivec4 uDims   nx, cnx, cny, the number of fans
//! uniform ivec4 uFan    this ring's first fan entry, its first fan triangle, its fan triangles, 0

fn kmain(p: vec2<i32>) {
  let t = line_index(p);
  if (t >= u.uFan.z) { return; }
  let nf = u.uDims.w;
  let f0 = u.uFan.x;
  // the fan holding triangle t: starts[f] <= t < starts[f + 1] (starts at f0, nf + 1 of them)
  var lo = 0;
  var hi = nf;
  while (hi - lo > 1) {
    let mid = (lo + hi) / 2;
    if (fan_b[f0 + mid] <= t) { lo = mid; } else { hi = mid; }
  }
  let f = lo;
  let s = t - fan_b[f0 + f];
  let e = f0 + nf + 1 + 5 * f;
  let j = fan_b[e];
  let i = fan_b[e + 1];
  let kind = fan_b[e + 2];
  let mlo = fan_b[e + 3];
  let mhi = fan_b[e + 4];
  let nmid = mhi - mlo;
  let nx = u.uDims.x;
  let cnx = u.uDims.y;
  let cny = u.uDims.z;
  let a = ig_b[j * nx + i];
  let b = ig_b[j * nx + i + 1];
  let c = ig_b[(j + 1) * nx + i + 1];
  let d = ig_b[(j + 1) * nx + i];
  var pp: u32;
  var q: u32;
  var r: u32;
  switch kind {
    case 0: { pp = a; q = c; r = d; }
    case 1: { pp = c; q = a; r = b; }
    case 2: { pp = a; q = b; r = c; }
    default: { pp = c; q = d; r = a; }
  }
  // pts[k], k = 0 .. nmid + 1
  var ends: array<u32, 2>;
  for (var w = 0; w < 2; w++) {
    let k = s + w;
    var v: u32;
    if (k == 0) {
      v = q;
    } else if (k == nmid + 1) {
      v = r;
    } else {
      let m = k - 1;                                  // the m-th in-between vertex, in the fan's order
      switch kind {
        case 0: { v = cg_b[mhi - 1 - m]; }                          // the child's bottom row, falling x
        case 1: { v = cg_b[(cny - 1) * cnx + mlo + m]; }            // its top row, rising x
        case 2: { v = cg_b[(mlo + m) * cnx]; }                      // its left column, rising y
        default: { v = cg_b[(mhi - 1 - m) * cnx + cnx - 1]; }       // its right column, falling y
      }
    }
    ends[w] = v;
  }
  let o = 3u * u32(u.uFan.y + t);
  outT_b[o] = pp;
  outT_b[o + 1u] = ends[0];
  outT_b[o + 2u] = ends[1];
}
