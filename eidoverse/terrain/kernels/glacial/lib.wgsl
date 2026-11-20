// kernels/glacial/lib.wgsl: what the port's own glacial kernels share (`//! include glacial/lib`): the trough's
// cross-section of blender/eidoblend/terrain/solvers/glacial.py at f90c6fc (cliff, prof, fillz, seed_floor and
// trough_target), which numpy evaluates in float64 over whole levels (profile_fields, sharpen_walls): here float32, in
// numpy's order. A kernel that includes it declares the profile uniforms (uToe, uLip, uFloorFrac, uFloorRise, uShW,
// uShH, uShB, uOut: glacial.py profile_uniforms), as jump_flood.wgsl and u_carve.wgsl do, and they read them the same
// way. The difference from those Blender kernels' own copies: np.power(s, e) is exact for e = 1 and 2 (numpy), so
// g_pow is too; pow() otherwise.

fn g_pow(s: f32, e: f32) -> f32 {
  if (e == 1.0) { return s; }
  if (e == 2.0) { return s * s; }
  if (e == 0.0) { return 1.0; }
  return pow(s, e);
}

// glacial.py cliff(t, toe, lip): the wall's rise over its run, C1 at both ends
fn g_cliff(t0: f32) -> f32 {
  let t = clamp(t0, 0.0, 1.0);
  let c = 1.0 / (1.0 - 0.5 * (u.uToe + u.uLip));
  if (t < u.uToe) { return c * t * t / (2.0 * max(u.uToe, 1e-6)); }
  if (t > 1.0 - u.uLip) {
    let s = 1.0 - t;
    return 1.0 - c * s * s / (2.0 * max(u.uLip, 1e-6));
  }
  return c * (t - 0.5 * u.uToe);
}

// glacial.py prof(rho, u, ff): 0 on the floor, the cliff to the lip, the shoulder, the upper wall
fn g_prof(rho: f32, ff: f32) -> f32 {
  if (rho <= 1.0) { return g_cliff((rho - ff) / (1.0 - ff)); }
  if (u.uShW <= 0.0) { return 1.0 + u.uOut * (rho - 1.0); }
  let s = max(rho - 1.0, 0.0) / u.uShW;
  if (s <= 1.0) { return 1.0 + u.uShH * g_pow(s, u.uShB); }
  return 1.0 + u.uShH + u.uOut * (rho - 1.0 - u.uShW);
}

// glacial.py fillz(rho, fill, H, u, ff, rise): the valley fill's top above zf
fn g_fillz(rho: f32, fill: f32, H: f32, ff: f32, rise: f32) -> f32 {
  let t = min(rho / max(ff, 1e-3), 1.0);
  return fill + rise * H * t * t;
}

// glacial.py seed_floor(u, Cc): (ff, rise) of a seed from its seedC texel
fn g_seed_floor(e: vec4<f32>) -> vec2<f32> {
  return vec2<f32>(clamp(u.uFloorFrac * e.x, 0.0, 0.95), u.uFloorRise * e.y);
}

// glacial.py trough_target(rho, zf, H, ff, fill, rise, u, rock): zf + max(H prof, fillz), or the bedrock zf + H prof
fn g_target(rho: f32, zf: f32, H: f32, ff: f32, fill: f32, rise: f32, rock: bool) -> f32 {
  let wall = H * g_prof(rho, ff);
  if (rock) { return zf + wall; }
  return zf + max(wall, g_fillz(rho, fill, H, ff, rise));
}
