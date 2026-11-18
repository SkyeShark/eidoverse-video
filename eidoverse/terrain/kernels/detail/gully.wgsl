// gully: the gully octaves' relief and their slope mask, cell by cell (the port's own kernel, PORT_PLAN.md 3.2: numpy
// code of blender/eidoblend/terrain/solvers/detail.py gully_relief at f90c6fc moved to the GPU; the plan's "Phacelle
// gully octave, from Ekigar's src/nodes/phacelle.js", through kernels/detail/phacelle.wgsl). It replaces
//   mask = _smoothstep(a0, a1, s) * (1 - _smoothstep(a2, a3, s))      s: the slope of the surface smoothed over 1 cell
//   for each octave o (while lam >= 3 cells; the CPU counts them):
//       c, sn, sdx, sdy = phacelle_noise(X / lam, Y / lam, gxs, gys, 1.0, 0.25, normalization, lattice_offset(seed + 4242, o))
//       out += amp * c
//       gx = -sn * sdx / lam;  gy = -sn * sdy / lam                   this octave's own gully walls
//       gxs += steer * gx * lam / TAU;  gys likewise;  (gxs, gys) /= max(hypot(gxs, gys), 1e-12)
//       lam *= 0.5;  amp *= gain
// Each cell's octaves depend only on its own direction, so one invocation runs them all. numpy evaluates in float64;
// this is float32 on lattice coordinates kept as an integer cell and a fraction (phacelle.wgsl), graded against it.
//! include noise
//! include detail/phacelle
//! sampler dx            x: the flow direction's x (solvers/detail.js flowDirection)
//! sampler dy            x: its y
//! sampler s             x: the slope in degrees of the surface smoothed over 1 cell
//! sampler oct           two texels per octave: (lam, amp, frac x, frac y), (base x, base y, num, lo)
//                        (the base holds the octave's lattice offset: solvers/detail.js gullyTable)
//! image   outG r32f     the relief, metres (before the mask)
//! image   outM r32f     the mask
//! image   outGM r32f    the relief times the mask: the op's change
//! uniform int uOct
//! uniform float uSteer
//! uniform float uNorm
//! uniform float uA0     slope_deg[0]
//! uniform float uD1     max(slope_deg[1] - slope_deg[0], 1e-12)
//! uniform float uA2     slope_deg[2]
//! uniform float uD2     max(slope_deg[3] - slope_deg[2], 1e-12)

fn kmain(p: vec2<i32>) {
  let n = outG_size();
  if (!inside(p, n)) { return; }
  let sl = s_at(p).x;
  let t1 = clamp((sl - u.uA0) / u.uD1, 0.0, 1.0);
  let t2 = clamp((sl - u.uA2) / u.uD2, 0.0, 1.0);
  let mask = (t1 * t1 * (3.0 - 2.0 * t1)) * (1.0 - t2 * t2 * (3.0 - 2.0 * t2));
  var gxs = dx_at(p).x;
  var gys = dy_at(p).x;
  var g = 0.0;
  for (var o = 0; o < u.uOct; o++) {
    let a = oct_at(vec2<i32>(2 * o, 0));
    let b = oct_at(vec2<i32>(2 * o + 1, 0));
    let lam = a.x;
    let at = phacelle_coord(p, vec2<i32>(b.xy), a.zw, i32(b.z), b.w);
    let r = phacelle_noise(at.c, at.f, vec2<f32>(gxs, gys), 1.0, 0.25, u.uNorm, vec2<i32>(0, 0));
    g += a.y * r.x;
    // steer the next octave down this octave's own gully walls (Ekigar's gully-weight feedback)
    let gx = -r.y * r.z / lam;
    let gy = -r.y * r.w / lam;
    gxs = gxs + u.uSteer * gx * lam / TAU;
    gys = gys + u.uSteer * gy * lam / TAU;
    let L = sqrt(gxs * gxs + gys * gys);
    gxs = gxs / max(L, 1e-12);
    gys = gys / max(L, 1e-12);
  }
  outG_store(p, vec4<f32>(g, 0.0, 0.0, 0.0));
  outM_store(p, vec4<f32>(mask, 0.0, 0.0, 0.0));
  outGM_store(p, vec4<f32>(g * mask, 0.0, 0.0, 0.0));
}
