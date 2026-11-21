// plants/records: plants.py _view's records (blender/eidoblend/terrain/build/plants.py at f9fba8c): per spot the 12
// FIELDS, x, y, z, yaw, scale, age, tint, nx, ny, nz, variant, level, float32: x and y the position rounded once,
// z the rendered ground's height (build/mesh.js heightField), yaw 2 pi _u(id, 15), scale size / size_m[1], the
// normal the triangle's (plants/ground_normal), variant min(floor(_u(id, 16) n), n - 1) exactly on the uniform's
// integer, the finest level holding the spot.
//! include plants/lib
//! sampler kp r32ui      the spots' records (16 numbers each: position 0-3, id 4-5, age 6, size 7, tone 8, level 14)
//! sampler zs r32f       per spot: z
//! sampler nrm r32f      per spot: nx, ny, nz
//! image   outR r32f     12 numbers a spot
//! uniform vec4 uR       size_m[1], the individuals (nvar), 0, 0
//! uniform int  uCount

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o = 16u * u32(i);
  let id = vec2<u32>(kp_b[o + 4u], kp_b[o + 5u]);
  let r = 12 * i;
  outR_b[r] = coord_f32(vec2<f32>(bitcast<f32>(kp_b[o]), bitcast<f32>(kp_b[o + 1u])));
  outR_b[r + 1] = coord_f32(vec2<f32>(bitcast<f32>(kp_b[o + 2u]), bitcast<f32>(kp_b[o + 3u])));
  outR_b[r + 2] = zs_b[i];
  outR_b[r + 3] = 6.2831853071795864769 * u53f(u53(id, 15u));
  outR_b[r + 4] = bitcast<f32>(kp_b[o + 7u]) / u.uR.x;
  outR_b[r + 5] = bitcast<f32>(kp_b[o + 6u]);
  outR_b[r + 6] = bitcast<f32>(kp_b[o + 8u]);
  outR_b[r + 7] = nrm_b[3 * i];
  outR_b[r + 8] = nrm_b[3 * i + 1];
  outR_b[r + 9] = nrm_b[3 * i + 2];
  // floor(k n / 2^53) for the 53-bit k = (hi, lo) and a small n: (hi n + (lo n >> 32)) >> 21
  let nv = u32(u.uR.y);
  let k = u53(id, 16u);
  let t = k.x * nv + mul32(k.y, nv).x;
  outR_b[r + 10] = f32(min(t >> 21u, max(nv, 1u) - 1u));
  outR_b[r + 11] = f32(kp_b[o + 14u]);
}
