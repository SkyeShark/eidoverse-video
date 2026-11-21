// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). snow: the snowpack's arithmetic on the padded cell grid (bake.py _Baker._snowpack, step 7), in
// numpy's float32 order; the two relaxations between are solvers/detail.js relax (pipes_thermal.wgsl), as Blender's.
//   uMode 0  fall     outA = depth_m x smooth(line - band, line + band, alt + aspect_m x north), the fall; outB the
//                     melt: melt_sun_m x max(insol - s_el, 0) / max(1 - s_el, 1e-3) + melt_low_m x (1 - smooth(line -
//                     band, line, alt)); alt = hp + float32(href + base), north = -gy / max(g, 1e-12) x smooth(1, 3,
//                     slope), insol = max((-gx sun.x - gy sun.y + sun.z) / sqrt(1 + g g), 0)
//   uMode 1  start    outA = a + max(b - c, 0): a fresh fall plus what the parent gathered beyond its own (rest0,
//                     flow0: fall + max(inherit(rest) - inherit(fall), 0))
//   uMode 2  pack     outA = max(a - b, 0) (pack = max(rest - melt, 0)); with uFlow, max(that, max(c - b, 0))
//   uMode 3  repose   outA = tan_slip + (tan_flow - tan_slip) x smooth(f0, f1, a): the flowing pass's repose by the
//                     flow mask
// A smoothstep is bake.py's TW.smoothstep: t = clip((x - float32(e0)) / float32(e1 - e0), 0, 1), t t (3 - 2 t); its
// edges come as (float32(e0), float32(e1 - e0)) pairs computed in doubles, as numpy takes them.
//! sampler a
//! sampler b
//! sampler c
//! sampler g
//! image   outA r32f
//! image   outB r32f
//! uniform int uMode
//! uniform int uFlow
//! uniform float uAlt          float32(href + base_elevation_m)
//! uniform vec2 uLine          the snowline's smoothstep (line - band, 2 band)
//! uniform vec2 uLow           (line - band, band): the melt below the line
//! uniform vec2 uNorth         (1, 2): northness faded in over 1-3 degrees
//! uniform vec4 uSnow          depth_m, aspect_m, melt_sun_m, melt_low_m
//! uniform vec4 uSun           the sun's unit vector (x east, y north, z up), and its z again (s_el)
//! uniform vec4 uRep           tan_slip, tan_flow, the flow mask's smoothstep (f0, f1 - f0)

fn ss(x: f32, e: vec2<f32>) -> f32 {
  let t = clamp((x - e.x) / e.y, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    let hp = a_at(p).x;
    let gr = g_at(p);
    let gx = gr.x;
    let gy = gr.y;
    let gg = gr.z;
    let alt = hp + u.uAlt;
    let slope_deg = degrees(atan(gg));
    let north = -gy / max(gg, 1e-12) * ss(slope_deg, u.uNorth);
    let fall = u.uSnow.x * ss(alt + u.uSnow.y * north, u.uLine);
    let nl = sqrt(1.0 + gg * gg);
    let insol = max((-gx * u.uSun.x - gy * u.uSun.y + u.uSun.z) / nl, 0.0);
    let s_el = u.uSun.w;
    let melt = u.uSnow.z * max(insol - s_el, 0.0) / max(1.0 - s_el, 1e-3) + u.uSnow.w * (1.0 - ss(alt, u.uLow));
    outA_store(p, vec4<f32>(fall, 0.0, 0.0, 0.0));
    outB_store(p, vec4<f32>(melt, 0.0, 0.0, 0.0));
  } else if (u.uMode == 1) {
    outA_store(p, vec4<f32>(a_at(p).x + max(b_at(p).x - c_at(p).x, 0.0), 0.0, 0.0, 0.0));
  } else if (u.uMode == 2) {
    var v = max(a_at(p).x - b_at(p).x, 0.0);
    if (u.uFlow != 0) { v = max(v, max(c_at(p).x - b_at(p).x, 0.0)); }
    outA_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
  } else {
    let wf = ss(a_at(p).x, u.uRep.zw);
    outA_store(p, vec4<f32>(u.uRep.x + (u.uRep.y - u.uRep.x) * wf, 0.0, 0.0, 0.0));
  }
}
