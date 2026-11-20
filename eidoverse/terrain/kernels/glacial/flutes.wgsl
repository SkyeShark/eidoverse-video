// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py wall_flutes at f90c6fc (numpy over the level;
// here float32 in numpy's order), one mode per step:
//   uMode 0  theta = mod(arctan2(dy, dx), pi) of the downhill direction (detail.flow_direction), and for each of the 8
//            orientations a = k pi / 8 whether any cell weighs on it (np.any(w_k): numpy skips an orientation no cell
//            weighs on, and with it that orientation's noise dispatch): counts[k] gains the cells with w_k > 0
//   uMode 1  orientation uK's displacement for the world-noise field (field_gpu's disp): (u - X, v - Y), with
//            u = X ta.x + Y ta.y, v = (X ga.x + Y ga.y) / flute_stretch, X, Y the cells' world centres
//   uMode 2  total += w_k n_k for orientation uK (n_k its ridged noise at the moved points)
//   uMode 3  t = clip((total / norm - 0.74) / 0.12, 0, 1); w = t^2 (3 - 2 t); flutes = strong (1 - w) - weak w,
//            times rock_flutes smoothstep((slope - rock_flute_deg) / 8) with uRock (refine_level's range flutes)
// w_k = clip(1 - |mod(theta - a + pi/2, pi) - pi/2| / (pi / 8), 0, 1).
//! sampler dx               mode 0: the downhill direction's x
//! sampler dy               mode 0: its y
//! sampler theta            modes 2: theta (mode 0's outA)
//! sampler nk               mode 2: the orientation's noise; mode 3: the total
//! sampler acc              mode 2: the total so far
//! sampler slope            mode 3 with uRock: the slope (degrees)
//! image   outA r32f        mode 0: theta; mode 2: the new total; mode 3: the flutes
//! image   outD rg32f       mode 1: the displacement (m)
//! image   counts atomic_u32  mode 0: [k] the cells weighing on orientation k
//! uniform int uMode
//! uniform int uK           the orientation (modes 1, 2)
//! uniform vec2 uOrigin     the level's corner, x0 and y0 (m)
//! uniform float uCell
//! uniform vec2 uTa         orientation uK's ta = (-sin a, cos a)
//! uniform vec2 uGa         its ga = (cos a, sin a)
//! uniform float uStretch   flute_stretch
//! uniform float uNorm      sum of 0.6^i over the resolved scales
//! uniform float uWeak      flute_weak
//! uniform float uStrong    flute_strong
//! uniform int uRock        mode 3: times the rock weight
//! uniform float uRockAmp   rock_flutes
//! uniform float uRockDeg   rock_flute_deg

const PI_F: f32 = 3.14159265358979;
const STEP_F: f32 = 0.392699081698724;

fn pmod(x: f32, m: f32) -> f32 { return x - m * floor(x / m); }

fn weight(th: f32, k: i32) -> f32 {
  let a = f32(k) * STEP_F;
  let d = abs(pmod(th - a + 0.5 * PI_F, PI_F) - 0.5 * PI_F);
  return clamp(1.0 - d / STEP_F, 0.0, 1.0);
}

fn kmain(p: vec2<i32>) {
  if (u.uMode == 1) {
    let n = outD_size();
    if (!inside(p, n)) { return; }
    let X = u.uOrigin.x + (f32(p.x) + 0.5) * u.uCell;
    let Y = u.uOrigin.y + (f32(p.y) + 0.5) * u.uCell;
    let uu = X * u.uTa.x + Y * u.uTa.y;
    let vv = (X * u.uGa.x + Y * u.uGa.y) / u.uStretch;
    outD_store(p, vec4<f32>(uu - X, vv - Y, 0.0, 0.0));
    return;
  }
  let n = outA_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    let th = pmod(atan2(dy_at(p).x, dx_at(p).x), PI_F);
    for (var k = 0; k < 8; k++) {
      if (weight(th, k) > 0.0) { atomicAdd(&counts_b[k], 1u); }
    }
    outA_store(p, vec4<f32>(th, 0.0, 0.0, 0.0));
    return;
  }
  if (u.uMode == 2) {
    outA_store(p, vec4<f32>(acc_at(p).x + weight(theta_at(p).x, u.uK) * nk_at(p).x, 0.0, 0.0, 0.0));
    return;
  }
  let t = clamp((nk_at(p).x / u.uNorm - 0.74) / 0.12, 0.0, 1.0);
  let w = t * t * (3.0 - 2.0 * t);
  var f = u.uStrong * (1.0 - w) - u.uWeak * w;
  if (u.uRock != 0) {
    let r = clamp((slope_at(p).x - u.uRockDeg) / 8.0, 0.0, 1.0);
    f = u.uRockAmp * r * r * (3.0 - 2.0 * r) * f;
  }
  outA_store(p, vec4<f32>(f, 0.0, 0.0, 0.0));
}
