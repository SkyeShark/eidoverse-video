// The port's own kernel (no Blender counterpart): the start of "floors never drop going upstream" of blender/
// eidoblend/terrain/solvers/fluvial.py op_valley_floor at f90c6fc. numpy visits the channel cells in the order of the
// surface (a stable sort: equal heights by index), downstream first, and raises each to its receiver's floor plus
// grade x its step:
//     for i in that order: j = the receiver's place (when it is a channel cell), Fc[i] = max(Fc[i], Fc[j] + gr[i])
// When the receiver comes earlier in that order (it is lower: always, except a breached outlet's lowest neighbour),
// Fc[j] is final by then, so the result is a path maximum along those edges (vf_floor_final.wgsl):
//     F[c] = L[c] + max over the cells q on c's path of (F0[q] - L[q]),  L the grade length to the path's end
// A receiver that comes later is read unraised, once: F0 = max(F, F[j] + gr). This kernel writes, per channel cell,
// F = h + lvl, the pointer (the forward edge's receiver, or the cell itself), the edge's grade length, and F0.
//! sampler rec r32i
//! sampler chan
//! sampler surf        the surface numpy sorts the channel cells by
//! sampler h
//! sampler lvl
//! image   outP r32ui
//! image   outL r32f
//! image   outF r32f   F0
//! uniform float uGrade
//! uniform float uCell

fn forward(i: i32, j: i32) -> bool {
  let si = surf_b[i];
  let sj = surf_b[j];
  return sj < si || (sj == si && j < i);
}

fn kmain(p: vec2<i32>) {
  let n = chan_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  if (!(chan_at(p).x > 0.5)) {
    outP_store(p, u32(i));
    outL_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    outF_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    return;
  }
  let F = h_at(p).x + lvl_at(p).x;
  var F0 = F;
  var nxt = u32(i);
  var gl = 0.0;
  let r = rec_at(p);
  if (r >= 0 && chan_b[r] > 0.5) {
    let di = r % n.x - p.x;
    let dj = r / n.x - p.y;
    let gr = u.uGrade * (u.uCell * sqrt(f32(di * di + dj * dj)));
    if (forward(i, r)) {
      nxt = u32(r);
      gl = gr;
    } else {
      F0 = max(F, (h_b[r] + lvl_b[r]) + gr);
    }
  }
  outP_store(p, nxt);
  outL_store(p, vec4<f32>(gl, 0.0, 0.0, 0.0));
  outF_store(p, vec4<f32>(F0, 0.0, 0.0, 0.0));
}
