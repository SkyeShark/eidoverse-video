// The port's own kernel (no Blender counterpart): the pins blender/eidoblend/terrain/solvers/fluvial.py makes with
// numpy at f90c6fc:
//   uMode 0   edge_pins(n, h, sea_level): pin_w 1 on the outer ring (and on sea cells, h <= sea), pin_h = h (0 without
//             h), min(pin_h, sea) on sea cells
//   uMode 1   op_fluvial's held channel (refine, an inherited 'incised' course): where incised > 0.5, pin_h = h and
//             pin_w = 1, else the pins as given
//   uMode 2   _sea_flat: 1 on rigid cells (h <= sea, or inside a flatten area: core/compose.js flattenMask > 0.5)
// Comparisons with the sea level are numpy's float32 comparisons (a Python float against a float32 array is cast to
// float32): uSea32 is the sea level rounded to float32.
//! sampler h
//! sampler a       mode 1: incised; mode 2: the flatten mask
//! sampler pw      mode 1: pin_w
//! sampler ph      mode 1: pin_h
//! image   outW r32f
//! image   outH r32f
//! uniform int uMode
//! uniform int uHasH
//! uniform int uSea
//! uniform float uSea32
//! uniform int uFlat

fn kmain(p: vec2<i32>) {
  let n = outW_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    var w = select(0.0, 1.0, on_edge(p, n));
    var hp = 0.0;
    if (u.uHasH == 1) {
      hp = h_at(p).x;
      if (u.uSea == 1 && hp <= u.uSea32) {
        w = 1.0;
        hp = min(hp, u.uSea32);
      }
    }
    outW_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
    outH_store(p, vec4<f32>(hp, 0.0, 0.0, 0.0));
    return;
  }
  if (u.uMode == 1) {
    var w = pw_at(p).x;
    var hp = ph_at(p).x;
    if (a_at(p).x > 0.5) {
      w = 1.0;
      hp = h_at(p).x;
    }
    outW_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
    outH_store(p, vec4<f32>(hp, 0.0, 0.0, 0.0));
    return;
  }
  var rig = false;
  if (u.uSea == 1 && h_at(p).x <= u.uSea32) { rig = true; }
  if (u.uFlat == 1 && a_at(p).x > 0.5) { rig = true; }
  outW_store(p, vec4<f32>(select(0.0, 1.0, rig), 0.0, 0.0, 0.0));
}
