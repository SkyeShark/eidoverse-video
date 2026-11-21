// Port of blender/eidoblend/terrain/solvers/karst.py _Grid.smooth()'s bilinear step at f90c6fc, for a lattice of
// double-float values (karst/lobes.wgsl): numpy's float64 rows then columns,
//     rows = v[j0] * (1 - fy) + v[j0 + 1] * fy;   out = rows[:, i0] * (1 - fx) + rows[:, i0 + 1] * fx
// in double-float (karst/precise.wgsl), rounded to float32 once (G.smooth's caller's .astype(np.float32)). The axis
// tables come from the CPU in doubles: (i0, fx) per subsample column, fx = tx - i0 as a double-float (fx 0 and i0 one
// past the rim where G.smooth returns the lattice itself, k = 1 and ss = 1).

//! sampler v rg32f           the lattice (hi, lo)
//! sampler ax rgba32f        per subsample column: (i0, fx hi, fx lo, 0)
//! sampler ay rgba32f        per subsample row: (j0, fy hi, fy lo, 0)
//! image   outF r32f
//! include karst/lib
//! include detail/exact
//! include karst/precise

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  kprecise(n);
  let a = ax_at(vec2<i32>(p.x, 0));
  let b = ay_at(vec2<i32>(p.y, 0));
  let i0 = i32(a.x);
  let j0 = i32(b.x);
  let fx = a.yz;
  let fy = b.yz;
  let gx = kdd_add(kdd(1.0), -fx);
  let gy = kdd_add(kdd(1.0), -fy);
  let r0 = kdd_add(kdd_mul(v_at(vec2<i32>(i0, j0)).xy, gy), kdd_mul(v_at(vec2<i32>(i0, j0 + 1)).xy, fy));
  let r1 = kdd_add(kdd_mul(v_at(vec2<i32>(i0 + 1, j0)).xy, gy), kdd_mul(v_at(vec2<i32>(i0 + 1, j0 + 1)).xy, fy));
  let o = kdd_add(kdd_mul(r0, gx), kdd_mul(r1, fx));
  outF_store(p, vec4<f32>(o.x, 0.0, 0.0, 0.0));
}
