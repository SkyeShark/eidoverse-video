// The port's own kernel (no Blender counterpart): the end of "floors never drop going upstream" of blender/
// eidoblend/terrain/solvers/fluvial.py op_valley_floor at f90c6fc (vf_floor_init.wgsl says how numpy's sequential
// pass is a path maximum): per channel cell the raised floor F0[q*] + (L - L[q*]), q* the cell of the largest
// F0 - L on its path (hydro/jump_argmax.wgsl), made from that cell's own floor so it does not cancel; `count` the
// channel cells raised above their own floor (numpy's `raised`). 0 off the channels (numpy's NaN, never read).
//! sampler chan
//! sampler h
//! sampler lvl
//! sampler F0
//! sampler L           the grade length to the path's end
//! sampler arg r32ui   q*
//! image   outF r32f
//! image   count atomic_u32

fn kmain(p: vec2<i32>) {
  let n = chan_size();
  if (!inside(p, n)) { return; }
  if (!(chan_at(p).x > 0.5)) {
    outF_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    return;
  }
  let q = i32(arg_at(p));
  let f = F0_b[q] + (L_at(p).x - L_b[q]);
  outF_store(p, vec4<f32>(f, 0.0, 0.0, 0.0));
  if (f > h_at(p).x + lvl_at(p).x) { atomicAdd(&count_b[0], 1u); }
}
