// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). carry_io: debris provenance's inputs and outputs (bake.py step 10), cell by cell:
//   uMode 0  aux      outF = (cover, zs, pinned, 0): pinned 1 on a child's margin (uChild), 0 in its window
//   uMode 1  start    coarsest level: (a.x = zs, 1e9, 0, 0); a child: (a.x + shift, a.y, a.z, 0), a its parent's
//                     carry state cropped and upsampled (nearest, upsample2.wgsl: crop_upsample2 channel by channel),
//                     numpy's st0[..., 0] += F(shift)
//   uMode 2  out      at the window's cells (uM in), from the converged state a = (src zs, dist, valid):
//                         valid = a.z > 0.5, fade = (1 - smooth(0.7 reach, reach, a.y)) x valid
//                         outF.x = zs - h                                    strata_dz
//                         outF.y = zs + (a.x - zs) x fade - h                src_dz
//                         outF.z = valid ? clamp(a.y / reach, 0, 1) : 1      grain
//                     in numpy's float32 order (b = the padded zs, c = the padded h)
//! sampler a
//! sampler b
//! sampler c
//! image   outF rgba32f
//! uniform int uMode
//! uniform int uChild
//! uniform int uM
//! uniform float uShift
//! uniform float uReach
//! uniform vec2 uFade          smooth(0.7 reach, reach): (float32(0.7 reach), float32(reach - 0.7 reach))

fn ss(x: f32, e: vec2<f32>) -> f32 {
  let t = clamp((x - e.x) / e.y, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    var pinned = 0.0;
    if (u.uChild != 0) {
      let q = p - vec2<i32>(u.uM);
      let w = n - vec2<i32>(2 * u.uM);
      if (!inside(q, w)) { pinned = 1.0; }
    }
    outF_store(p, vec4<f32>(a_at(p).x, b_at(p).x, pinned, 0.0));
  } else if (u.uMode == 1) {
    let s = a_at(p);
    if (u.uChild == 0) {
      outF_store(p, vec4<f32>(s.x, 1.0e9, 0.0, 0.0));
    } else {
      outF_store(p, vec4<f32>(s.x + u.uShift, s.y, s.z, 0.0));
    }
  } else {
    let q = p + vec2<i32>(u.uM);
    let s = a_at(q);
    let zs = b_at(q).x;
    let h = c_at(q).x;
    let valid = s.z > 0.5;
    let fade = (1.0 - ss(s.y, u.uFade)) * select(0.0, 1.0, valid);
    let grain = select(1.0, clamp(s.y / u.uReach, 0.0, 1.0), valid);
    outF_store(p, vec4<f32>(zs - h, zs + (s.x - zs) * fade - h, grain, 0.0));
  }
}
