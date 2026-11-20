// Port of blender/eidoblend/terrain/solvers/coast.py op_coast at f90c6fc, from "band" to its writes, as a kernel over a
// level's cells (numpy's float64 is float32 here):
//     h        = h (1 - w) + pin_h w                    (a child's border band, uBand 1)
//     bed      = min(where(changed, rock, where(near, h, bed_in)), h)
//     wear     = max(where(changed, base + wear_add, base), 0);  talus, deposit = max(where(changed, add, base), 0)
//                (base: the level's own layer, 0 near the parent's cut on a child: there this level's coast layers
//                replace the parent's smeared ones)
//     Sc       = the face's value (coast_cliff.wgsl), where(changed, sc, Sc) on the first level when it has one
//     coast_cut = max(land - h, 0);  zs = h - col_off (a rock column)

//! sampler A rgba32f         coast_cliff.wgsl: (h, rock, apron_part, deposit_add)
//! sampler B rgba32f         coast_cliff.wgsl: (wear_add, changed, sc, col_off)
//! sampler land
//! sampler bedIn
//! sampler zone              a child's zone near the parent's cut (uChild)
//! sampler bw                the border band's weight (uBand)
//! sampler pinH              the band's pin values (uBand)
//! sampler wearIn            (uHas & 1)
//! sampler talusIn           (uHas & 2)
//! sampler depIn             (uHas & 4)
//! sampler scIn              (uHas & 8, and not a child)
//! image   outH r32f
//! image   outBed r32f
//! image   outWear r32f
//! image   outTalus r32f
//! image   outDep r32f
//! image   outSc r32f
//! image   outCut r32f
//! image   outZs r32f
//! uniform int uChild
//! uniform int uBand
//! uniform int uHas
fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let a = A_at(p);
  let b = B_at(p);
  var h = a.x;
  if (u.uBand != 0) {
    let w = bw_at(p).x;
    h = h * (1.0 - w) + pinH_at(p).x * w;
  }
  let changed = b.y > 0.5;
  var near = false;
  if (u.uChild != 0) { near = zone_at(p).x > 0.5; }
  let land = land_at(p).x;
  var bed = bedIn_at(p).x;
  if (near) { bed = h; }
  if (changed) { bed = a.y; }
  bed = min(bed, h);
  var wear = 0.0;
  var talus = 0.0;
  var dep = 0.0;
  if ((u.uHas & 1) != 0 && !near) { wear = wearIn_at(p).x; }
  if ((u.uHas & 2) != 0 && !near) { talus = talusIn_at(p).x; }
  if ((u.uHas & 4) != 0 && !near) { dep = depIn_at(p).x; }
  if (changed) {
    wear = wear + b.x;
    talus = a.z;
    dep = a.w;
  }
  var sc = b.z;
  if ((u.uHas & 8) != 0 && u.uChild == 0 && !changed) { sc = scIn_at(p).x; }
  outH_store(p, vec4<f32>(h, 0.0, 0.0, 0.0));
  outBed_store(p, vec4<f32>(bed, 0.0, 0.0, 0.0));
  outWear_store(p, vec4<f32>(max(wear, 0.0), 0.0, 0.0, 0.0));
  outTalus_store(p, vec4<f32>(max(talus, 0.0), 0.0, 0.0, 0.0));
  outDep_store(p, vec4<f32>(max(dep, 0.0), 0.0, 0.0, 0.0));
  outSc_store(p, vec4<f32>(sc, 0.0, 0.0, 0.0));
  outCut_store(p, vec4<f32>(max(land - h, 0.0), 0.0, 0.0, 0.0));
  outZs_store(p, vec4<f32>(h - b.w, 0.0, 0.0, 0.0));
}
