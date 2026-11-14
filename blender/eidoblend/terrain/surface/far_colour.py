"""The far colour C (SURFACING_DESIGN.md 2.3, 3.1.7, 3.7): the palette's ground per texel, every layer at its scan's
mean, on the context and main levels' cells, from one generated GPU kernel per palette, compiled once (its numpy
twin is the material itself, read through palettes.evaluate and surface/noise.py; tests/terrain/surface_data compare
them). A hero level holds its parent's far colour: the far hand-off never reaches inside a hero window.

    from eidoblend.terrain.surface import far_colour as FC
    [(rgb (n, n, 3) linear, roughness (n, n))] = FC.bake(sd, palette)
    FC.kernel_source(palette)               # the generated GLSL (the footprint and sub-samples are uniforms)

Per texel, as build/surfacing.py's surface_group composes the near material, with each scan at its mean:
  coverage   the layer's weight expression, clamped (expr_glsl: Blender's noise where the expression has noise);
  colour     the layer's target (its colour, or the strata column's formation colour at the stratigraphic height plus
             strata_offset_m, mixed by a fractional `strata`), else its scan's mean; times its tint; its patches (the
             palette's ramps and satmap arrive as patches through palettes.get) mixed in by their noise, `where` and
             amount; the streaks' mean darkening on steep faces; times value; clamped to 0..0.95. A canopy layer far
             away is its crowns' mean tone over the gaps;
  roughness  the scan's mean roughness times the layer's (times the column's at the height);
  composite  the coverages in order, e_i = c_i prod_{j > i} (1 - c_j), then the material's height blend with every
             scan at its mean height (a_i = e_i + h_i k, kept within blend_depth of the tallest, normalised);
  then       ambient occlusion by the scans' mean AO, the tone expression (x clamp(1 + tone, 0.4, 1.6)), the macro
             octaves (hue, saturation and value by world noise), damp (darker, smoother).
Each texel is the mean of 4 x 4 sub-samples (SUB; the height interpolated at each), so terms finer than a texel are
box-filtered; a noise term finer than a sub-sample reads its mean (expr_glsl's footprint fade at a quarter texel, the
uniform uFoot).
Known differences from the near material: the overlay of 3.2 (not in the material yet); the strata beds' jitter,
partings and relief shading, the ledges' plants and the canopy's crown pattern enter as their means (the beds by their
formation's colour); the height is the field's, not the ring mesh's interpolated vertices.
"""
from __future__ import annotations

import glob
import json
import math
import os
import time
from pathlib import Path

import numpy as np

from . import bake as B
from . import expr_glsl as XG
from . import noise as BN
from . import twins as TW

F = np.float32
REPO = Path(__file__).resolve().parents[4]
SETS_DIR = REPO / 'eidoverse' / 'assets' / 'cache' / 'terrain_surface_sets'
COLUMN_TEXELS_PER_M = 1.0
CANOPY_COVER = 0.72            # the share of a far canopy texel in lit crowns (the rest the gaps' tone)
CANOPY_SHADE = 0.92


def scan_stats(set_name, prefer='2k'):
    """The packed scan set's stats (build/surfacing.py's pack_set: mean_albedo_linear, mean_roughness, mean_ao), or
    None when the set has not been packed on this machine yet."""
    cands = sorted(glob.glob(str(SETS_DIR / f'{set_name}_*_v*' / 'stats.json')))
    if not cands:
        return None
    pick = next((c for c in cands if f'_{prefer}_' in c.replace('\\', '/')), cands[0])
    try:
        return json.loads(Path(pick).read_text())
    except (OSError, ValueError):
        return None


def _lin(h):
    from ..build import palettes as P
    return tuple(float(v) for v in P.hex_linear(h))


def _v3(c):
    return 'vec3(' + ', '.join(XG._f(v) for v in c) + ')'


def _streak_mean(lo, hi, n3, seed=19.7):
    """E[smoothstep(lo, hi, n)] of the streak noise (detail 3, roughness 0.55) over the plane: its darkening's mean."""
    rng = np.random.default_rng(7)
    co = rng.uniform(-5000, 5000, (20000, 3)).astype(F)
    if n3:
        off = np.array([37.7 * seed + 11.3, -51.9 * seed + 7.1, 23.3 * seed - 3.7], F)
        n = BN.noise_node3(co + off, 1.0, 3.0, 0.55)
    else:
        n = BN.noise_node4(co, seed, 1.0, 3.0, 0.55)
    t = np.clip((n - lo) / max(hi - lo, 1e-6), 0, 1)
    return float((t * t * (3 - 2 * t)).mean())


def _column(pal):
    """(rgba (1, W, 4) float32: formation colour, roughness multiplier; z_lo, z_hi, repeat) of the palette's strata
    column at COLUMN_TEXELS_PER_M, the end formations run on past the ends by pad_m; None without strata layers."""
    from ..build import palettes as P
    st = pal.get('strata') or {}
    if not (st.get('column') and any(L.get('strata') for L in pal['layers'])):
        return None
    layers = P.column_layers(st['column'], looks=bool(st.get('looks', False)))
    rep = P.column_repeats(st['column'])
    z_lo, z_hi = layers[0][1], layers[-1][2]
    if not rep:
        pad = float(st.get('pad_m', 0.0))
        z_lo, z_hi = z_lo - pad, z_hi + pad
    W = int(min(16384, max(16, math.ceil((z_hi - z_lo) * COLUMN_TEXELS_PER_M))))
    zc = z_lo + (np.arange(W) + 0.5) / W * (z_hi - z_lo)
    out = np.zeros((1, W, 4), F)
    tops = np.array([L[2] for L in layers])
    idx = np.clip(np.searchsorted(tops, zc, side='right'), 0, len(layers) - 1)
    for k, L in enumerate(layers):
        col = L[3]
        if isinstance(col, list):
            w = np.array([c[1] for c in col])
            col = (np.array([c[0] for c in col]) * w[:, None]).sum(0) / max(w.sum(), 1e-9)
        sel = idx == k
        out[0, sel, :3] = np.clip(np.asarray(col, F), 0.0, 0.95)
        out[0, sel, 3] = float(L[4])
    return out, float(z_lo), float(z_hi), bool(rep)


class _Gen:
    """The kernel's generator: reads of maps by name become channels of packed samplers."""

    def __init__(self, pal, texel_m):
        self.pal = pal
        self.opt = pal['options']
        self.n3 = self.opt.get('detile') == 'rotate'
        self.comp = XG.Compiler(read=lambda nm: f'@@{nm}@@', constants=pal.get('constants'), noise3=self.n3,
                                texel_m=texel_m)
        self.texel = texel_m
        self.lines = []

    def e(self, src):
        return self.comp.expr(src)

    def noise(self, scale_m, detail, roughness, seed):
        """surface_group's noise(): 3D on a landscape palette, else the old 4D (w = seed), faded by the footprint."""
        fade = self.comp._fade(scale_m)
        det = self.comp._detail(scale_m, detail)
        if self.n3:
            n = self.comp.node3(scale_m, det, roughness, seed)
        else:
            n = f'bn_noise_node4(uPos, {XG._f(seed)}, {XG._f(1.0 / scale_m)}, {XG._d(det)}, {XG._f(roughness)})'
        if not isinstance(fade, str) and fade >= 1.0:
            return n
        return f'(0.5 + ({n} - 0.5) * {XG._d(fade)})'


SUB = 4                 # sub-samples per texel side


def kernel_source(pal, texel_m=None):
    """(GLSL source, the maps it reads in sampler order, uniforms' constants): the far colour kernel of a palette
    (module doc). One source serves every level: the footprint (a quarter texel, uFoot) and the sub-sample count
    (uSub) are uniforms, so the GLSL compiles once per palette and the sub-sample loop is not unrolled. texel_m is
    not used (kept for callers)."""
    from ..build import palettes as P
    _ = texel_m
    g = _Gen(pal, 'uniform')            # the sub-samples' spacing: finer terms fade to their mean, coarser are filtered
    opt = g.opt
    L_ = pal['layers']
    col_info = _column(pal)
    body = []
    strata_zs = None
    if col_info is not None:
        st = pal['strata']
        if st.get('source', 'attribute') == 'attribute':
            zs = '@@strata@@'
            g.comp.names.add('strata')
        else:
            dip = math.tan(math.radians(float(st.get('dip_deg', 0.0))))
            az = math.radians(float(st.get('dip_azimuth_deg', st.get('azimuth_deg', 0.0))))
            zs = f'(uPos.z - (uPos.x * {XG._f(math.cos(az))} + uPos.y * {XG._f(math.sin(az))}) * {XG._f(dip)})'
        zs = f'({zs} + {XG._f(float(st.get("z_offset_m", 0.0)))})'
        for f in st.get('faults', []) or []:
            s = math.radians(float(f.get('strike_deg', 0.0)))
            nx, ny = math.cos(s), -math.sin(s)
            want = {'west': (-1, 0), 'east': (1, 0), 'north': (0, 1), 'south': (0, -1)}[f.get('down', 'west')]
            if nx * want[0] + ny * want[1] < 0:
                nx, ny = -nx, -ny
            w = max(float(f.get('width_m', 50.0)), 1e-3)
            d = (f'((uPos.x - {XG._f(float(f.get("x", 0.0)))}) * {XG._f(nx)} + (uPos.y - '
                 f'{XG._f(float(f.get("y", 0.0)))}) * {XG._f(ny)})')
            zs = f'({zs} + xg_smooth({XG._f(-0.5 * w)}, {XG._f(0.5 * w)}, {d}) * {XG._f(float(f.get("throw_m", 0)))})'
        for k, (scale, amp) in enumerate(st.get('warp', []) or []):
            n = (f'bn_noise_node4(uPos, {XG._f(41.3 + 3.7 * k)}, {XG._f(1.0 / float(scale))}, '
                 f'{XG._d(g.comp._detail(float(scale), 2.0))}, 0.5)')
            fade = g.comp._fade(float(scale))
            zs = f'({zs} + ({n} - 0.5) * {XG._mul(2.0 * float(amp), fade)})'
        body.append(f'  float zsS = {zs};')
        strata_zs = 'zsS'
    pers = []
    hmeans = []
    for i, L in enumerate(L_):
        stats = scan_stats(L['set'])
        mean = tuple(stats['mean_albedo_linear']) if stats else (_lin(L['colour']) if L.get('colour') else (0.3,) * 3)
        mrough = float(stats['mean_roughness']) if stats else 0.8
        mao = float(stats['mean_ao']) if stats else 1.0
        hmeans.append(0.5)          # the packed height's mean: pack_set stores 0.5 + 0.15 (d - mean) / std
        cov = f'clamp({g.e(L["weight"])}, 0.0, 1.0)'
        body.append(f'  float cov{i} = {cov};')
        own = _lin(L['colour']) if L.get('colour') else None
        smix = float(L['strata']) if L.get('strata') is not True else 1.0
        rough = f'{XG._f(mrough * float(L.get("roughness", 1.0)))}'
        if smix > 0 and col_info is not None and L.get('strata'):
            off = float(L.get('strata_offset_m', 0.0))
            body.append(f'  vec4 band{i} = column({strata_zs} + {XG._f(off)});')
            target = (f'band{i}.rgb' if (smix >= 1.0 or own is None) else
                      f'mix({_v3(own)}, band{i}.rgb, {XG._f(smix)})')
            rough = (f'({rough} * band{i}.a)' if smix >= 1.0 else
                     f'({rough} * mix(1.0, band{i}.a, {XG._f(smix)}))')
        elif own is not None:
            target = _v3(own)
        else:
            target = _v3(mean)
        body.append(f'  vec3 col{i} = {target};')
        if L.get('tint') is not None:
            body.append(f'  col{i} *= {_v3(tuple(L["tint"])[:3])};')
        if L.get('strata') and smix >= 1.0 and col_info is not None and L.get('relief', True) \
                and float((pal['strata'] or {}).get('relief_m', 0.0) or 0.0) > 0:
            shade = float(pal['strata'].get('relief_shade', 0.15))
            body.append(f'  col{i} *= {XG._f(1.0 - 0.5 * shade)};       // the beds\' relief shade, at its mean')
        if L.get('canopy'):
            cn = L['canopy']
            lit = tuple(0.5 * (a + b) * CANOPY_SHADE for a, b in zip(_lin(cn.get('colour', '#26371f')),
                                                                     _lin(cn.get('light', '#3d522c'))))
            gap = _lin(cn.get('gap', '#11160d'))
            body.append(f'  col{i} = mix({_v3(gap)}, {_v3(lit)}, {XG._f(CANOPY_COVER)});   // crowns far away')
            rough = '0.9'
        pts = L.get('patches') or []
        for k, pt in enumerate([pts] if isinstance(pts, dict) else list(pts)):
            amount = float(pt.get('amount', 0.6))
            if pt.get('scale_m') is None:
                pm = XG._f(amount)
            else:
                pn = g.noise(float(pt['scale_m']), float(pt.get('detail', 3.0)), 0.55, 33.7 + 2.3 * i + 5.1 * k)
                pm = (f'(xg_smooth({XG._f(float(pt.get("lo", 0.42)))}, {XG._f(float(pt.get("hi", 0.62)))}, {pn}) * '
                      f'{XG._f(amount)})')
            if pt.get('where'):
                pm = f'({pm} * clamp({g.e(pt["where"])}, 0.0, 1.0))'
            if pt.get('tint'):
                ratio = tuple(float(v) for v in pt['tint'][:3])
            else:
                ref = np.array(_lin(L['colour'])) if L.get('colour') else np.maximum(np.array(mean), 1e-4)
                ratio = tuple(float(v) for v in np.array(_lin(pt['colour'])) / np.maximum(ref, 1e-4))
            body.append(f'  col{i} = mix(col{i}, col{i} * {_v3(ratio)}, {pm});')
        if L.get('streaks'):
            stv = [float(v) for v in L['streaks']]
            lo, hi = (stv[2], stv[3]) if len(stv) >= 4 else (0.45, 0.68)
            mean_dark = stv[1] * _streak_mean(lo, hi, g.n3, 19.7 + 3.3 * i)
            dark = f'({XG._f(mean_dark)} * steepFace)'
            if L.get('streaks_where'):
                dark = f'({dark} * clamp({g.e(L["streaks_where"])}, 0.0, 1.0))'
            body.append(f'  col{i} *= 1.0 - {dark};')
        if float(L.get('value', 1.0)) != 1.0:
            body.append(f'  col{i} *= {XG._f(float(L["value"]))};')
        body.append(f'  col{i} = clamp(col{i}, 0.0, 0.95);')
        body.append(f'  float rough{i} = {rough};')
        pers.append(mao)
    # the composite: coverage in order, then the material's height blend with every scan at its mean height
    # (a_i = e_i + h_i k, keep what lies within blend_depth of the tallest, normalise)
    n = len(L_)
    body.append('  float rem = 1.0;')
    for i in range(n - 1, -1, -1):
        body.append(f'  float e{i} = cov{i} * rem;')
        body.append(f'  rem *= 1.0 - cov{i};')
    k_hb = float(opt.get('height_blend', 0.0) or 0.0)
    bd = float(opt.get('blend_depth', 0.2) or 0.2)
    if n > 1:
        for i in range(n):
            body.append(f'  float a{i} = e{i} + {XG._f(hmeans[i] * k_hb)};')
        mx = f'a{n - 1}'
        for i in range(n - 2, -1, -1):
            mx = f'max(a{i}, {mx})'
        body.append(f'  float ma = {mx} - {XG._f(bd)};')
        for i in range(n):
            body.append(f'  float w{i} = max(a{i} - ma, 0.0);')
        body.append('  float ws = max(' + ' + '.join(f'w{i}' for i in range(n)) + ', 1e-5);')
        for i in range(n):
            body.append(f'  w{i} /= ws;')
    else:
        body.append('  float w0 = 1.0;')
    body.append('  vec3 albedo = ' + ' + '.join(f'w{i} * col{i}' for i in range(n)) + ';')
    body.append('  float rough = ' + ' + '.join(f'w{i} * rough{i}' for i in range(n)) + ';')
    ao = float(opt.get('ao', 0.0) or 0.0)
    if ao > 0:
        body.append(f'  albedo *= {XG._f(1.0 - ao)} + ({" + ".join(f"w{i} * {XG._f(pers[i])}" for i in range(n))}) * '
                    f'{XG._f(ao)};')
    if opt.get('tone'):
        body.append(f'  albedo *= clamp(1.0 + ({g.e(opt["tone"])}), 0.4, 1.6);')
    macro = opt.get('macro') or []
    if macro:
        val, hue, sat = [], [], []
        for k, o in enumerate(macro):
            seed = o.get('w', 1.7 + 2.9 * k)
            nm = g.noise(float(o['scale_m']), float(o.get('detail', 2.0)), float(o.get('roughness', 0.5)), seed)
            body.append(f'  float mac{k} = {nm};')
            t = f'clamp((mac{k} - 0.3) / 0.4, 0.0, 1.0)'
            if o.get('value'):
                val.append(f'({XG._f(1.0 - o["value"])} + {t} * {XG._f(2.0 * o["value"])})')
            if o.get('hue'):
                hue.append(f'({XG._f(-o["hue"])} + {t} * {XG._f(2.0 * o["hue"])})')
            if o.get('saturation'):
                lo, hi = o['saturation']
                sat.append(f'({XG._f(lo)} + {t} * {XG._f(hi - lo)})')
        body.append(f'  albedo = hue_sat({" + ".join(hue) if hue else "0.0"}, {" * ".join(sat) if sat else "1.0"}, '
                    f'{" * ".join(val) if val else "1.0"}, albedo);')
    if float(opt.get('damp', 0.0) or 0.0) > 0 or opt.get('damp_where'):
        dm = '0.0'
        if float(opt.get('damp', 0.0) or 0.0) > 0:
            dn = g.noise(float(opt.get('damp_scale_m', 6.25)), 3.0, 0.6, 13.3)
            dm = f'(xg_smooth(0.5, 0.68, {dn}) * {XG._f(float(opt["damp"]))})'
        if opt.get('damp_where'):
            dw = f'clamp({g.e(opt["damp_where"])}, 0.0, 1.0)'
            dm = dw if dm == '0.0' else f'max({dm}, {dw})'
        body.append(f'  float damp = {dm};')
        body.append('  albedo *= 1.0 - damp * 0.38;')
        body.append('  rough *= 1.0 - damp * 0.32;')
    body.append('  albedo = min(albedo, vec3(0.95));')
    body.append('  return vec4(max(albedo, vec3(0.0)), clamp(rough, 0.02, 1.0));')
    # the maps it reads: packed four to a sampler, after the noise terms are known
    names = sorted(g.comp.names | {'slope'})
    slot = {nm: (k // 4, k % 4) for k, nm in enumerate(names)}
    n_s = (len(names) + 3) // 4
    code = '\n'.join(body)
    decl = g.comp.declarations()
    for nm, (s, c) in slot.items():
        rep = f'texelFetch(maps{s}, p, 0).{"xyzw"[c]}'
        code = code.replace(f'@@{nm}@@', rep)
        decl = decl.replace(f'@@{nm}@@', rep)
    head = ['/* far_colour: the palette\'s ground per texel, generated by surface/far_colour.py (its doc). */']
    for s in range(n_s):
        head.append(f'//! sampler maps{s}       maps ' + ', '.join(nm for nm, (k, _c) in slot.items() if k == s))
    head.append('//! sampler hT          x: the ground height (Blender z)')
    head.append('//! sampler colT        the strata column: rgb, roughness multiplier (one row)')
    head.append('//! image   outC rgba32f   linear albedo, roughness')
    head.append('//! uniform vec3 uLevel    (x0, y0, texel) of the level, metres')
    head.append('//! uniform vec3 uColumn   (z_lo, z_hi, repeat)')
    head.append('//! uniform float uFoot    the footprint the noise terms fade at: the sub-samples\' spacing, metres')
    head.append('//! uniform float uSub     sub-samples per texel side')
    src = '\n'.join(head) + '\n' + XG.HELPERS + XG.FOOTPRINT + '\n' + BN.source() + '\n' + _HSV + r'''
vec4 column(float zs) {
  ivec2 n = textureSize(colT, 0);
  float u = (zs - uColumn.x) / max(uColumn.y - uColumn.x, 1e-6);
  if (uColumn.z > 0.5) u = u - floor(u);
  int i = clamp(int(floor(u * float(n.x))), 0, n.x - 1);
  return texelFetch(colT, ivec2(i, 0), 0);
}

/* the ground's height at a point inside texel p (offset in texels from its centre): bilinear on the cell centres */
float hsample(ivec2 p, vec2 off) {
  ivec2 n = textureSize(hT, 0);
  vec2 c = vec2(p) + off;
  vec2 fl = floor(c);
  vec2 t = c - fl;
  ivec2 i0 = clamp(ivec2(fl), ivec2(0), n - 1);
  ivec2 i1 = clamp(ivec2(fl) + 1, ivec2(0), n - 1);
  return mix(mix(texelFetch(hT, i0, 0).x, texelFetch(hT, ivec2(i1.x, i0.y), 0).x, t.x),
             mix(texelFetch(hT, ivec2(i0.x, i1.y), 0).x, texelFetch(hT, i1, 0).x, t.x), t.y);
}

/* the near material's colour logic at one point (its maps read at the texel holding it) */
vec4 shade(vec3 uPos, ivec2 p) {
  float slopeDeg = ''' + f'texelFetch(maps{slot["slope"][0]}, p, 0).{"xyzw"[slot["slope"][1]]}' + r''';
  float steepFace = xg_smooth(0.78, 0.5, cos(radians(slopeDeg)));
''' + decl + '\n' + code + r'''
}

/* each texel the mean of uSub x uSub sub-samples: terms finer than a texel are box-filtered, not point-sampled (the
   count is a uniform, so the compiler keeps one copy of shade() in a loop instead of unrolling sixteen) */
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(hT, 0);
  if (!inside(p, n)) return;
  int ns = max(int(uSub + 0.5), 1);
  float inv = 1.0 / float(ns);
  vec4 acc = vec4(0.0);
  for (int k = 0; k < ns * ns; k++) {
    vec2 off = (vec2(float(k % ns), float(k / ns)) + 0.5) * inv - 0.5;
    vec3 pos = vec3(uLevel.xy + (vec2(p) + 0.5 + off) * uLevel.z, hsample(p, off));
    acc += shade(pos, p);
  }
  /* 1 for any real value: every uniform and sampler stays in the compiled kernel, also on a palette with no strata
     column or no noise term (a uniform the compiler drops cannot be set) */
  float keep = step(max(max(uColumn.x, uColumn.y), max(uColumn.z, uFoot)), 3.0e38)
             * step(texelFetch(colT, ivec2(0), 0).w, 3.0e38);
  imageStore(outC, p, acc * (inv * inv) * keep);
}
'''
    return src, names, col_info


_HSV = r'''
vec3 rgb_to_hsv_b(vec3 rgb) {
  float cmax = max(rgb.x, max(rgb.y, rgb.z));
  float cmin = min(rgb.x, min(rgb.y, rgb.z));
  float cdelta = cmax - cmin;
  float v = cmax, s = 0.0, h = 0.0;
  if (cmax != 0.0) s = cdelta / cmax;
  if (s != 0.0) {
    vec3 c = (vec3(cmax) - rgb) / cdelta;
    if (rgb.x == cmax) h = c.z - c.y;
    else if (rgb.y == cmax) h = 2.0 + c.x - c.z;
    else h = 4.0 + c.y - c.x;
    h /= 6.0;
    if (h < 0.0) h += 1.0;
  }
  return vec3(h, s, v);
}
vec3 hsv_to_rgb_b(vec3 hsv) {
  float h = hsv.x, s = hsv.y, v = hsv.z;
  if (s == 0.0) return vec3(v);
  if (h == 1.0) h = 0.0;
  h *= 6.0;
  float i = floor(h);
  float f = h - i;
  float p = v * (1.0 - s), q = v * (1.0 - s * f), t = v * (1.0 - s * (1.0 - f));
  if (i == 0.0) return vec3(v, t, p);
  if (i == 1.0) return vec3(q, v, p);
  if (i == 2.0) return vec3(p, v, t);
  if (i == 3.0) return vec3(p, q, v);
  if (i == 4.0) return vec3(t, p, v);
  return vec3(v, p, q);
}
/* Blender's Hue/Saturation/Value node with Fac 1 (the material's _macro: Hue = 0.5 + shift) */
vec3 hue_sat(float shift, float sat, float val, vec3 col) {
  vec3 hsv = rgb_to_hsv_b(col);
  hsv.x = fract(hsv.x + shift + 1.0);
  hsv.y = clamp(hsv.y * sat, 0.0, 1.0);
  hsv.z *= val;
  return hsv_to_rgb_b(hsv);
}
'''


def bake(sd, pal, log=print):
    """[(rgb (n, n, 3), roughness (n, n))] per level: the far colour on the context and main levels' cells (GPU in
    Blender; the kernel needs Blender's GPU module). A hero level holds its parent's far colour, bilinear: the far
    hand-off never reaches inside a hero window (SURFACING_DESIGN.md 3.7), so its tile is only read across the gutter."""
    import hashlib
    from ..solvers import fluvial as FL
    from . import atlas as AT
    dev = FL.device('gpu')
    out = []
    src, names, col = kernel_source(pal)
    # named by its source: a device caches kernels by name, and every palette has its own
    k = FL.Inline(f'surface_far_colour_{hashlib.sha1(src.encode("utf-8")).hexdigest()[:12]}', src)
    for i, lv in enumerate(sd.levels):
        t0 = time.perf_counter()
        texel = float(lv.cell)
        if lv.role == 'hero' and lv.parent is not None:
            prgb, prough = out[lv.parent]
            plv = sd.levels[lv.parent]
            X, Y = lv.xy()
            rgb = np.stack([AT.sample_bilinear(prgb[..., c], plv.x0, plv.y0, plv.cell, X, Y) for c in range(3)],
                           -1).astype(F)
            rough = AT.sample_bilinear(prough, plv.x0, plv.y0, plv.cell, X, Y).astype(F)
            out.append((np.ascontiguousarray(rgb), np.ascontiguousarray(rough)))
            if log:
                log(f'[surface] palette bake: far colour on level {i} (hero: its parent\'s) in '
                    f'{time.perf_counter() - t0:.2f} s')
            continue
        m = sd.maps(i)
        n = lv.n
        h = np.asarray(sd.terrain.fields(i)['h'], F)
        samp = {'hT': dev.texture(h)}
        for s in range((len(names) + 3) // 4):
            a = np.zeros((n, n, 4), F)
            for c, nm in enumerate(names[4 * s:4 * s + 4]):
                v = m.get(nm)
                if v is None and nm == 'height':
                    v = h
                if v is not None:
                    a[..., c] = np.asarray(v, F) if np.shape(v) == (n, n) else _to_cells(np.asarray(v, F), n)
            samp[f'maps{s}'] = dev.texture(a)
        if col is not None:
            rgba, z_lo, z_hi, rep = col
            samp['colT'] = dev.texture(rgba)
            ucol = (z_lo, z_hi, 1.0 if rep else 0.0)
        else:
            samp['colT'] = dev.texture(np.zeros((1, 1, 4), F))
            ucol = (0.0, 1.0, 0.0)
        o = dev.empty((n, n), 4)
        dev.run(k, samp, {'outC': o}, {'uLevel': (float(lv.x0), float(lv.y0), texel), 'uColumn': ucol,
                                      'uFoot': texel / SUB, 'uSub': float(SUB)})
        r = dev.read(o)
        out.append((np.ascontiguousarray(r[..., :3]), np.ascontiguousarray(r[..., 3])))
        if log:
            log(f'[surface] palette bake: far colour on level {i} in {time.perf_counter() - t0:.2f} s')
    return out


def _to_cells(a, n):
    m = a.shape[0]
    if m == 2 * n:
        return a.reshape(n, 2, n, 2).mean(axis=(1, 3)).astype(F)
    raise ValueError(f'a map of {m} texels on a level of {n} cells')


_ = (B, TW, os)
__all__ = ['bake', 'kernel_source', 'scan_stats', 'CANOPY_COVER']
