// Port of blender/eidoblend/terrain/solvers/volcanic.py AzimuthSampler at f90c6fc (`//! include volcanic/az`, after
// volcanic/math): linear reads of closed periodic tables of azimuth. The tables (azimuth_noise, scallop_outline,
// embayment_outline, impact.polygon_factor, the streak bands) are 1D, built in JavaScript doubles as numpy builds them
// (solvers/volcanic.js AzTables), and held in one field, `azt` (r32f, one row of AZ_SAMPLES + 1 per table, the last
// entry the first). A kernel that includes this declares `//! sampler azt r32f`.
//
// AzimuthSampler: u = np.mod(az, TAU) * (8192 / TAU); i = min(floor(u), 8191); f = u - i; a + (b - a) f. In float32
// u carries about 5e-4 of a sample (the angle's own rounding), graded against numpy's float64.

const AZ_SAMPLES: i32 = 8192;

struct AzS { i: i32, f: f32 }

fn az_sampler(az: f32) -> AzS {
  let u = v_mod(az, VTAU) * (f32(AZ_SAMPLES) / VTAU);
  let i = min(i32(floor(u)), AZ_SAMPLES - 1);
  return AzS(i, u - f32(i));
}

// table `row` at the sampler's place
fn az_read(row: i32, s: AzS) -> f32 {
  let a = azt_at(vec2<i32>(s.i, row)).x;
  let b = azt_at(vec2<i32>(s.i + 1, row)).x;
  return a + (b - a) * s.f;
}
