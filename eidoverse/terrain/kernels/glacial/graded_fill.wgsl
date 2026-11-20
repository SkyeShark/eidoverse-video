// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py graded_fill at f90c6fc (with fill0 = 0 and
// outlet = zc, as centrelines calls it), numpy's own relaxation, repeated until nothing changes:
//     top = zf;  top = max(top, zc) where the seed has no receiver (a stream's last seed: it meets the river)
//     top = max(top, top[rcv] + grade L) where rcv >= 0,  L = hypot(x - x[rcv], y - y[rcv])
//     fill = top - zf
// numpy relaxes top, heights of thousands of metres, in float64. Here the same relaxation runs on the fill itself
// (fill = top - zf, from 0 to a few hundred metres), so float32 rounds at the fill's size, not the height's:
//   uMode 0  fill = 0;  fill = max(0, zc - zf) where rcv < 0
//   uMode 1  fill = max(fill, fill[rcv] + (zf[rcv] - zf) + grade L) where rcv >= 0
// (top - zf on both sides of numpy's max: the same fixed point; zf[rcv] - zf is the difference of nearby floors).
//! sampler T                per seed: the fill so far
//! sampler V                per seed: x, y, zc
//! sampler P                per seed: W, H, d, zf
//! sampler rcv r32i
//! image   outT r32f
//! image   changed atomic_u32  with uCounted 1: [0] gains the seeds this sweep changed
//! uniform int uMode
//! uniform float uGrade     floor_grade (m/m)
//! uniform int uCount
//! uniform int uCounted

fn kmain(p: vec2<i32>) {
  let w = outT_size().x;
  let s = p.y * w + p.x;
  if (p.x >= w || s >= u.uCount) { return; }
  let r = rcv_b[s];
  let zf = P_b[s].w;
  if (u.uMode == 0) {
    var f0 = 0.0;
    if (r < 0) { f0 = max(0.0, V_b[s].z - zf); }
    outT_b[s] = f0;
    return;
  }
  let t = T_b[s];
  var nt = t;
  if (r >= 0) {
    let d = V_b[s].xy - V_b[r].xy;
    nt = max(t, T_b[r] + (P_b[r].w - zf) + u.uGrade * sqrt(d.x * d.x + d.y * d.y));
  }
  if (u.uCounted != 0 && nt != t) { atomicAdd(&changed_b[0], 1u); }
  outT_b[s] = nt;
}
