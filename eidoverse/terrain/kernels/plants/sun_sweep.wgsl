// plants/sun_sweep: plant_instances.py sun_shade's sweep over one level's heights (a grid laid along the light: s
// away from the sun, w across it, cells of the level's cell): per line w the running maximum of h + s tan(el) over
// the cells before each cell (-1e9 before the first; h bilinear in the level, -1e9 more than half a cell off it), so a
// point is shaded where that maximum stands over its own z + s tan(el). One thread per line, its cells in order.
//! include plants/lib
//! sampler h r32f        the level's heights, n x n, row 0 south (Blender frame)
//! image   outM r32f     nw lines of ns cells
//! uniform vec4 uLv      x0, y0, the cell, n
//! uniform vec4 uDir     ux, uy (toward the sun, horizontal, unit), tan(el), 0
//! uniform vec4 uGrid    s0, w0, ns, nw

fn hb(n: i32, i: i32, j: i32) -> f32 { return h_b[j * n + i]; }

fn kmain(p: vec2<i32>) {
  let w = lin(p);
  let ns = i32(u.uGrid.z);
  if (w >= i32(u.uGrid.w)) { return; }
  let c = u.uLv.z;
  let n = i32(u.uLv.w);
  let nf = f32(n);
  let ux = u.uDir.x;
  let uy = u.uDir.y;
  let W = u.uGrid.y + f32(w) * c;
  var run = -1.0e9;
  for (var s = 0; s < ns; s++) {
    let S = u.uGrid.x + f32(s) * c;
    let gx = -S * ux - W * uy;
    let gy = -S * uy + W * ux;
    let fi = (gx - u.uLv.x) / c - 0.5;
    let fj = (gy - u.uLv.y) / c - 0.5;
    var H = -1.0e9;
    if (!(fi < -0.5 || fi > nf - 0.5 || fj < -0.5 || fj > nf - 0.5)) {
      let ci = clamp(fi, 0.0, nf - 1.001);
      let cj = clamp(fj, 0.0, nf - 1.001);
      let i0 = i32(ci);
      let j0 = i32(cj);
      let ti = ci - f32(i0);
      let tj = cj - f32(j0);
      H = (hb(n, i0, j0) * (1.0 - ti) + hb(n, i0 + 1, j0) * ti) * (1.0 - tj) +
          (hb(n, i0, j0 + 1) * (1.0 - ti) + hb(n, i0 + 1, j0 + 1) * ti) * tj;
    }
    outM_b[w * ns + s] = run;
    run = max(run, H + S * u.uDir.z);
  }
}
