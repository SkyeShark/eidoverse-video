// Port of blender/eidoblend/terrain/solvers/hydro.py inflow at f90c6fc, as a gather on the child window's edge
// cells (PORT_PLAN.md 3.2). numpy works on the window plus two parent cells around it:
//     ws[c]   = sum_k (s > 0) s^p,  s = (r[c] - r[c + OFF[k]]) / (DIST[k] pc)      every cell's downhill weight
//     inA[c]  = sum_k A[q] share,   q = c + OFF[k] outside the window, c inside, r[q] > r[c],
//               share = ((r[q] - r[c]) / (DIST[k] pc))^p / max(ws[q], 1e-30)       what crosses the edge into c
// and then shares each parent cell's inA (and inQ, the same for qs) equally among the child cells of its f x f
// block that lie on the child window's edge. A child edge cell here finds its parent cell c, gathers inA and inQ
// over c's eight neighbours (each q's ws over q's own eight, in the same order as numpy's loops), and divides by its
// block's count of edge cells. The two-cell margin of numpy's slice holds every neighbour a q one cell outside the
// window has, so the sums are the same. DIST is hydro.py's float64 sqrt(2) (not the kernels' float32 LEN): the
// two lengths arrive as float32 uniforms made in doubles, DIST[k] * pc.
//
// numpy computes in float64 and rounds A_in and qs_in to float32 once; this is float32 throughout (within 1e-6 of
// the range with p = 1; pow()'s error with p != 1).
//! sampler r                the parent's routing surface (metres)
//! sampler A                the parent's drainage area (m^2)
//! sampler qs               uQs 1: the parent's sediment flux (m^3/yr); else a 1 x 1 stand-in
//! image   outA r32f        A_in on the child's grid
//! image   outQ r32f        qs_in
//! uniform ivec2 uOrigin    the child's window in parent cells: (i0, j0)
//! uniform int uM           the window's side in parent cells
//! uniform int uF           round(parent cell / child cell)
//! uniform int uQs
//! uniform float uP         the flow exponent
//! uniform float uLs        DIST of a side neighbour times the parent cell: pc
//! uniform float uLd        DIST of a diagonal neighbour times the parent cell: sqrt(2) pc

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

fn dist(k: i32) -> f32 {
  if (k == 0 || k == 2 || k == 5 || k == 7) { return u.uLd; }
  return u.uLs;
}

fn in_window(q: vec2<i32>) -> bool {
  let w = q - u.uOrigin;
  return w.x >= 0 && w.y >= 0 && w.x < u.uM && w.y < u.uM;
}

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  var a = 0.0;
  var qv = 0.0;
  if (on_edge(p, n)) {
    let pn = r_size();
    let c = u.uOrigin + p / u.uF;
    let rc = r_at(c).x;
    var inA = 0.0;
    var inQ = 0.0;
    for (var k = 0; k < 8; k++) {
      let q = c + OFF[k];
      if (!inside(q, pn) || in_window(q)) { continue; }
      let rq = r_at(q).x;
      if (!(rq > rc)) { continue; }
      var ws = 0.0;
      for (var kk = 0; kk < 8; kk++) {
        let q2 = q + OFF[kk];
        if (!inside(q2, pn)) { continue; }
        let s = (rq - r_at(q2).x) / dist(kk);
        if (s > 0.0) { ws += wpow(s, u.uP); }
      }
      let share = wpow((rq - rc) / dist(k), u.uP) / max(ws, 1e-30);
      inA += A_at(q).x * share;
      if (u.uQs != 0) { inQ += qs_at(q).x * share; }
    }
    // the child cells of c's block on the child window's edge (numpy's cnt)
    let base = (c - u.uOrigin) * u.uF;
    var cnt = 0;
    for (var oy = 0; oy < u.uF; oy++) {
      for (var ox = 0; ox < u.uF; ox++) {
        let b = base + vec2<i32>(ox, oy);
        if (inside(b, n) && on_edge(b, n)) { cnt++; }
      }
    }
    if (cnt > 0) {
      a = inA / f32(cnt);
      qv = inQ / f32(cnt);
    }
  }
  outA_store(p, vec4<f32>(a, 0.0, 0.0, 0.0));
  outQ_store(p, vec4<f32>(qv, 0.0, 0.0, 0.0));
}
