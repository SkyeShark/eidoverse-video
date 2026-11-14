// Port of blender/eidoblend/terrain/core/world_noise.py and core/fields.py at f90c6fc: the numpy array arithmetic
// between their kernels, as GPU work (PORT_PLAN.md 2.4): field_gpu's sums and products of parts and
// `off + amp * out`, Fields.thickness (h - bed), a constant fill (a Fields entry set to a number), and the stacking of
// a warp's displacement (np.stack([d[..., 0] + dx, d[..., 1] + dy], -1)).
// numpy does these on float32 arrays with Python numbers, in float32 (NEP 50: the number takes the array's
// dtype), one rounding per operation; so does this kernel, with no fused multiply-add asked for.
//! sampler a                the first operand (its first channel; for op 5, a displacement (x, y))
//! sampler b                the second operand (its first channel)
//! sampler c                op 5: the y displacement (its first channel)
//! image   outF r32f        ops 0-4 and 6
//! image   outD rg32f       op 5
//! uniform int uOp          0 a + b, 1 a * b, 2 uOff + uAmp * a, 3 a - b, 4 the constant uOff,
//                           5 outD = (a.x + b, a.y + c), 6 a * uAmp
//! uniform float uAmp
//! uniform float uOff

fn kmain(p: vec2<i32>) {
  if (u.uOp == 5) {
    if (!inside(p, outD_size())) { return; }
    let d = a_at(p).xy;
    outD_store(p, vec4<f32>(d.x + b_at(p).x, d.y + c_at(p).x, 0.0, 0.0));
    return;
  }
  if (!inside(p, outF_size())) { return; }
  var v: f32;
  switch u.uOp {
    case 0: { v = a_at(p).x + b_at(p).x; }
    case 1: { v = a_at(p).x * b_at(p).x; }
    case 2: { let m = u.uAmp * a_at(p).x; v = u.uOff + m; }
    case 3: { v = a_at(p).x - b_at(p).x; }
    case 4: { v = u.uOff; }
    default: { v = a_at(p).x * u.uAmp; }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
