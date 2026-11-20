// Port of blender/eidoblend/terrain/solvers/coast.py _child_land at f90c6fc, its blend, as a kernel over a level's
// cells: the uncut land on a child level, the parent's land (coast_land, bilinear) near the parent's cut and the
// parent's surface (h, Catmull-Rom) beyond, blended over three cells:
//     w = 1 inside the zone (the cut dilated by CHILD_ZONE cells: r0), then 0.75 / 0.5 / 0.25 on the next three rings
//         (r1, r2, r3: the zone dilated by 1, 2 and 3 more cells, core/prims.js dilate)
//     land = w coast_land + (1 - w) h
// outC: (land, w).

//! sampler h
//! sampler landBl
//! sampler r0
//! sampler r1
//! sampler r2
//! sampler r3
//! image   outC rg32f
fn kmain(p: vec2<i32>) {
  let n = outC_size();
  if (!inside(p, n)) { return; }
  var w = 0.0;
  if (r0_at(p).x > 0.5) { w = 1.0; } else if (r1_at(p).x > 0.5) { w = 0.75; } else if (r2_at(p).x > 0.5) { w = 0.5; } else if (r3_at(p).x > 0.5) { w = 0.25; }
  outC_store(p, vec4<f32>(w * landBl_at(p).x + (1.0 - w) * h_at(p).x, w, 0.0, 0.0));
}
