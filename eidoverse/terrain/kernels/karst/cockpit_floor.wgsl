// Port of blender/eidoblend/terrain/solvers/karst.py _cockpit_floors at f90c6fc, its last lines, as a kernel:
//   uMode 0  fl = level[lab]               (each basin's floor level spread over its coarse cells; -inf elsewhere)
//   uMode 1  out = np.repeat(np.repeat(fl, f, 0), f, 1), padded to n x n with its edge (np.pad mode 'edge')
// (between the two, fl = max(fl, rolling_max_1(fl)): core/prims.js dilate, the same 3 x 3 maximum)

//! sampler lab r32ui
//! sampler lev               per label: its floor level (-inf: none)
//! sampler fl                uMode 1: the coarse floor levels
//! image   outF r32f
//! uniform int uMode
//! uniform int uF
//! uniform int uM            the coarse grid's side
fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    let l = i32(lab_at(p));
    outF_store(p, vec4<f32>(lev_at(vec2<i32>(l, 0)).x, 0.0, 0.0, 0.0));
    return;
  }
  let q = min(p / u.uF, vec2<i32>(u.uM - 1));
  outF_store(p, vec4<f32>(fl_at(q).x, 0.0, 0.0, 0.0));
}
