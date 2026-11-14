"""LOOKDEV renderer (GPU, Warp ray casting; for my eyes): a UV-mapped mesh with its texture set, shaded as the engine
shades it, so references can be studied WITH their materials (Skye 10-20: "load the texture directly onto the meshes
... it'll help you learn how they did materials") and my own bakes judged before the engine.

Per material: albedo (sRGB), tangent normal (green up or down), roughness, metalness, AO, and the scalars 'ior' (the
specular F0 = ((n - 1) / (n + 1))^2: three's default 1.5 gives 0.04, water's 1.33 0.020) or 'f0', 'clearcoat',
'clearcoat_rough', 'specular_intensity'.
Shading = three.js r184's MeshPhysicalNodeMaterial (nodes/functions/PhysicalLightingModel.js), so lookdev and the
engine judge the same response (review r4, material lens):
  * the key light: Lambert + GGX (D_GGX, height-correlated Smith, Epic's exp2 Schlick; alpha = roughness^2) with three's
    multiscatter compensation (BRDF_GGX_Multiscatter over its 16 x 16 DFG LUT); the roughness as getRoughness: the map
    floored at 0.0525 plus the geometry roughness (the per-pixel change of the vertex normal);
  * the environment: an analytic sky/ground (radiance over elevation, ENV), its exact irradiance for the diffuse and
    its split-sum GGX prefilter for the specular (the lookup bent toward N by roughness^4, as EnvironmentNode), split
    by the DFG multiscatter terms (the diffuse x (1 - Ess - Ems)); AO on the environment only (the diffuse x ao, the
    specular x Frostbite's specular occlusion), as three;
  * clearcoat: three's fixed coat F0 0.04 on the geometry normal, the base attenuated by 1 - cc F_cc(N.V);
  * textures: trilinear mips (2x2 box levels) at a per-pixel footprint from ray differentials (the engine's LOD: the
    uv change over one screen pixel, the same at every ss; the GPU's isotropic rho = max(|duv/dx|, |duv/dy|)); the
    albedo decoded per texel with the exact sRGB EOTF before filtering (an sRGB texture's order);
  * display: AgX as three r184 (the default; exposure), 'legacy' (the old 1.25 x / (1 + x)), 'linear'; the exact sRGB
    OETF; the background a display colour composited by coverage; on the device (k_display; display() is its float64
    twin on the host).
Tangent frames per triangle from UV derivatives, or the mesh's own TAN (three's TSL math).

    lookdev.render(mesh_dict, materials, out_png, views=..., size=...)
    mesh_dict: V (n,3), F (m,3), UV (n,2), mat (m,) material index per triangle
    materials: list of dicts {albedo: HxWx3 uint8 sRGB, normal: HxWx3 uint8 | None, rough: HxW uint8 | None,
               metal: HxW uint8 | None, ao: HxW uint8 | None, normal_green_down: bool,
               ior | f0: float, clearcoat: float, clearcoat_rough: float, specular_intensity: float}
"""
import numpy as np
import warp as wp
from PIL import Image, ImageDraw

from . import material as MT

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile

# the default light: the key's irradiance (the old renderer's 3.2) and a neutral sky/ground whose irradiance is the old
# hemisphere ambient's 0.30 + 0.20 N.y (exactly, for a step sky 0.5 over ground 0.1; within 0.001 with the soft horizon:
# soft = its half width in elevation sine, so mirror-smooth skin reflects no razor line); the old background's sRGB8
KEY = 3.2
ENV = dict(sky=0.5, ground=0.1, soft=0.15)
BG = (94, 94, 100)


@wp.func
def tex_rgb(tex: wp.array(dtype=wp.vec4), off: int, w: int, h: int, uv: wp.vec2):
    """bilinear, wrapping; v measured from the image's top (glTF convention)"""
    x = (uv[0] - wp.floor(uv[0])) * float(w) - 0.5
    y = (uv[1] - wp.floor(uv[1])) * float(h) - 0.5
    x0 = int(wp.floor(x))
    y0 = int(wp.floor(y))
    fx = x - float(x0)
    fy = y - float(y0)
    x0 = (x0 % w + w) % w
    y0 = (y0 % h + h) % h
    x1 = (x0 + 1) % w
    y1 = (y0 + 1) % h
    a = tex[off + y0 * w + x0]
    b = tex[off + y0 * w + x1]
    c = tex[off + y1 * w + x0]
    d = tex[off + y1 * w + x1]
    return (a * (1.0 - fx) + b * fx) * (1.0 - fy) + (c * (1.0 - fx) + d * fx) * fy


INV_PI = wp.constant(0.3183098861837907)


@wp.func
def tex_bilinear(tex: wp.array(dtype=wp.vec3), off: int, w: int, h: int, uv: wp.vec2):
    """tex_rgb on one mip level of the vec3 store"""
    x = (uv[0] - wp.floor(uv[0])) * float(w) - 0.5
    y = (uv[1] - wp.floor(uv[1])) * float(h) - 0.5
    x0 = int(wp.floor(x))
    y0 = int(wp.floor(y))
    fx = x - float(x0)
    fy = y - float(y0)
    x0 = (x0 % w + w) % w
    y0 = (y0 % h + h) % h
    x1 = (x0 + 1) % w
    y1 = (y0 + 1) % h
    a = tex[off + y0 * w + x0]
    b = tex[off + y0 * w + x1]
    c = tex[off + y1 * w + x0]
    d = tex[off + y1 * w + x1]
    return (a * (1.0 - fx) + b * fx) * (1.0 - fy) + (c * (1.0 - fx) + d * fx) * fy


@wp.func
def tex_mip(tex: wp.array(dtype=wp.vec3), lv_off: wp.array(dtype=wp.int32), lv_w: wp.array(dtype=wp.int32),
            lv_h: wp.array(dtype=wp.int32), first: int, nlv: int, uv: wp.vec2, uvx: wp.vec2, uvy: wp.vec2,
            bias: float):
    """trilinear: the level from the footprint (uvx, uvy: the uv change over one pixel) in level-0 texels by the
    GPU's isotropic rule rho = max(|duv/dx|, |duv/dy|), bilinear in the two nearest levels"""
    w0 = float(lv_w[first])
    h0 = float(lv_h[first])
    rho = wp.max(wp.length(wp.vec2(uvx[0] * w0, uvx[1] * h0)), wp.length(wp.vec2(uvy[0] * w0, uvy[1] * h0)))
    lod = wp.clamp(wp.log2(wp.max(rho, 1.0e-12)) + bias, 0.0, float(nlv - 1))
    l0 = int(wp.floor(lod))
    f = lod - float(l0)
    c = tex_bilinear(tex, lv_off[first + l0], lv_w[first + l0], lv_h[first + l0], uv)
    if f > 0.0:
        l1 = wp.min(l0 + 1, nlv - 1)
        c = c * (1.0 - f) + tex_bilinear(tex, lv_off[first + l1], lv_w[first + l1], lv_h[first + l1], uv) * f
    return c


@wp.func
def dfg_at(dfg: wp.array(dtype=wp.vec2), rough: float, ndv: float):
    """three's DFG LUT (16 x 16, linear filter, clamped to the edge) at uv = (roughness, N.V): (F0 scale, F90 bias)"""
    x = wp.clamp(rough * 16.0 - 0.5, 0.0, 15.0)
    y = wp.clamp(ndv * 16.0 - 0.5, 0.0, 15.0)
    x0 = int(wp.floor(x))
    y0 = int(wp.floor(y))
    x1 = wp.min(x0 + 1, 15)
    y1 = wp.min(y0 + 1, 15)
    fx = x - float(x0)
    fy = y - float(y0)
    a = dfg[y0 * 16 + x0] * (1.0 - fx) + dfg[y0 * 16 + x1] * fx
    b = dfg[y1 * 16 + x0] * (1.0 - fx) + dfg[y1 * 16 + x1] * fx
    return a * (1.0 - fy) + b * fy


@wp.func
def env_irr_at(tab: wp.array(dtype=wp.vec3), n_mu: int, mu: float):
    """the sky/ground's irradiance / pi at a normal of elevation sine mu"""
    x = (wp.clamp(mu, -1.0, 1.0) + 1.0) * 0.5 * float(n_mu - 1)
    i0 = wp.min(int(wp.floor(x)), n_mu - 2)
    f = x - float(i0)
    return tab[i0] * (1.0 - f) + tab[i0 + 1] * f


@wp.func
def env_rad_at(tab: wp.array(dtype=wp.vec3), n_mu: int, n_r: int, mu: float, rough: float):
    """the sky/ground's prefiltered radiance for a reflection of elevation sine mu at a roughness"""
    x = (wp.clamp(mu, -1.0, 1.0) + 1.0) * 0.5 * float(n_mu - 1)
    y = wp.clamp(rough, 0.0, 1.0) * float(n_r - 1)
    i0 = wp.min(int(wp.floor(x)), n_mu - 2)
    j0 = wp.min(int(wp.floor(y)), n_r - 2)
    fx = x - float(i0)
    fy = y - float(j0)
    a = tab[j0 * n_mu + i0] * (1.0 - fx) + tab[j0 * n_mu + i0 + 1] * fx
    b = tab[(j0 + 1) * n_mu + i0] * (1.0 - fx) + tab[(j0 + 1) * n_mu + i0 + 1] * fx
    return a * (1.0 - fy) + b * fy


@wp.func
def f_schlick(f0: wp.vec3, f90: float, vdh: float):
    """three's F_Schlick (Epic's exp2 fit of (1 - v)^5)"""
    fr = wp.pow(2.0, (-5.55473 * vdh - 6.98316) * vdh)
    return f0 * (1.0 - fr) + wp.vec3(f90, f90, f90) * fr


@wp.func
def brdf_ggx(n: wp.vec3, V: wp.vec3, L: wp.vec3, f0: wp.vec3, f90: float, rough: float):
    """three's BRDF_GGX: F_Schlick x V_GGX_SmithCorrelated x D_GGX, alpha = roughness^2 (rough >= 0.0525 here)"""
    alpha = rough * rough
    a2 = alpha * alpha
    H = wp.normalize(L + V)
    ndl = wp.clamp(wp.dot(n, L), 0.0, 1.0)
    ndv = wp.clamp(wp.dot(n, V), 0.0, 1.0)
    ndh = wp.clamp(wp.dot(n, H), 0.0, 1.0)
    vdh = wp.clamp(wp.dot(V, H), 0.0, 1.0)
    gv = ndl * wp.sqrt(a2 + (1.0 - a2) * ndv * ndv)
    gl = ndv * wp.sqrt(a2 + (1.0 - a2) * ndl * ndl)
    dd = 1.0 - ndh * ndh * (1.0 - a2)
    return f_schlick(f0, f90, vdh) * (0.5 / wp.max(gv + gl, 1.0e-6) * a2 / (dd * dd) * INV_PI)


@wp.func
def brdf_ggx_ms(n: wp.vec3, V: wp.vec3, L: wp.vec3, f0: wp.vec3, rough: float, dfg: wp.array(dtype=wp.vec2)):
    """three's BRDF_GGX_Multiscatter (the direct light: GGX plus Turquin's compensation; f90 = 1)"""
    ndl = wp.clamp(wp.dot(n, L), 0.0, 1.0)
    ndv = wp.clamp(wp.dot(n, V), 0.0, 1.0)
    gv = dfg_at(dfg, rough, ndv)
    gl = dfg_at(dfg, rough, ndl)
    one = wp.vec3(1.0, 1.0, 1.0)
    fe_v = f0 * gv[0] + one * gv[1]
    fe_l = f0 * gl[0] + one * gl[1]
    em = (1.0 - gv[0] - gv[1]) * (1.0 - gl[0] - gl[1])
    fav = f0 + (one - f0) * 0.047619
    fms = wp.cw_div(wp.cw_mul(wp.cw_mul(fe_v, fe_l), fav),
                    one - wp.cw_mul(fav, fav) * em + wp.vec3(1.0e-6, 1.0e-6, 1.0e-6))
    return brdf_ggx(n, V, L, f0, 1.0, rough) + fms * em


@wp.func
def spec_occlusion(ndv: float, ao: float, rough: float):
    """three's specular occlusion of the environment (Frostbite: (N.V + ao)^(2^(-16 r - 1)) - 1 + ao)"""
    return wp.clamp(wp.pow(ndv + ao, wp.pow(2.0, -16.0 * rough - 1.0)) - 1.0 + ao, 0.0, 1.0)


@wp.struct
class Shade:
    rgb: wp.vec3          # the outgoing radiance
    spec: wp.vec3         # its key-light specular (base + coat)
    env_spec: wp.vec3     # its environment specular (base + coat)


@wp.func
def shade(nn: wp.vec3, ng: wp.vec3, V: wp.vec3, L: wp.vec3, key: wp.vec3, alb: wp.vec3, rough_map: float,
          metal: float, ao: float, mp: wp.vec4, geo_r: float, dfg: wp.array(dtype=wp.vec2),
          env_rad: wp.array(dtype=wp.vec3), env_irr: wp.array(dtype=wp.vec3), n_mu: int, n_r: int):
    """three r184's PhysicalLightingModel for one key light and the sky/ground: nn the shading (normal-mapped) normal,
    ng the geometry normal (the coat's), mp = (F0, clearcoat, clearcoat roughness, specular intensity)"""
    one = wp.vec3(1.0, 1.0, 1.0)
    r = wp.min(wp.max(rough_map, 0.0525) + geo_r, 1.0)
    si = mp[3]
    f0d = one * (wp.min(mp[0], 1.0) * si)                       # specularColor (dielectric)
    f0b = f0d * (1.0 - metal) + alb * metal                     # specularColorBlended
    f90 = si * (1.0 - metal) + metal                            # specularF90
    dc = alb * (1.0 - metal)                                    # diffuseContribution
    # the key light (irradiance = key N.L)
    irr = key * wp.clamp(wp.dot(nn, L), 0.0, 1.0)
    spec_d = wp.cw_mul(irr, brdf_ggx_ms(nn, V, L, f0b, r, dfg))
    diff_d = wp.cw_mul(irr, dc) * INV_PI
    # the environment (computeMultiscattering for the dielectric and the metallic F0, mixed by metalness)
    ndv = wp.clamp(wp.dot(nn, V), 0.0, 1.0)
    fab = dfg_at(dfg, r, ndv)
    ems = 1.0 - fab[0] - fab[1]
    fss_d = f0d * fab[0] + one * (f90 * fab[1])
    fav_d = f0d + (one - f0d) * 0.047619
    mul_d = wp.cw_div(wp.cw_mul(fss_d, fav_d), one - fav_d * ems) * ems
    fss_m = alb * fab[0] + one * (f90 * fab[1])
    fav_m = alb + (one - alb) * 0.047619
    mul_m = wp.cw_div(wp.cw_mul(fss_m, fav_m), one - fav_m * ems) * ems
    single = fss_d * (1.0 - metal) + fss_m * metal
    multi = mul_d * (1.0 - metal) + mul_m * metal
    e_irr = env_irr_at(env_irr, n_mu, nn[1])                     # iblIrradiance / pi
    R = nn * (2.0 * wp.dot(V, nn)) - V
    r4 = r * r * r * r
    R = wp.normalize(R * (1.0 - r4) + nn * r4)
    rad = env_rad_at(env_rad, n_mu, n_r, R[1], r)
    diff_e = wp.cw_mul(wp.cw_mul(dc, one - fss_d - mul_d), e_irr) * ao
    spec_e = (wp.cw_mul(rad, single) + wp.cw_mul(multi, e_irr)) * spec_occlusion(ndv, ao, r)
    s = Shade()
    s.rgb = diff_d + spec_d + diff_e + spec_e
    s.spec = spec_d
    s.env_spec = spec_e
    cc = mp[1]
    if cc > 0.0:
        rc = wp.min(wp.max(mp[2], 0.0525) + geo_r, 1.0)
        f0c = wp.vec3(0.04, 0.04, 0.04)
        ccd = wp.cw_mul(key * wp.clamp(wp.dot(ng, L), 0.0, 1.0), brdf_ggx(ng, V, L, f0c, 1.0, rc))
        ndvc = wp.clamp(wp.dot(ng, V), 0.0, 1.0)
        fc = dfg_at(dfg, rc, ndvc)
        Rc = ng * (2.0 * wp.dot(V, ng)) - V
        rc4 = rc * rc * rc * rc
        Rc = wp.normalize(Rc * (1.0 - rc4) + ng * rc4)
        cce = env_rad_at(env_rad, n_mu, n_r, Rc[1], rc) * ((0.04 * fc[0] + fc[1]) * ao)
        att = one - f_schlick(f0c, 1.0, ndvc) * cc
        s.rgb = wp.cw_mul(s.rgb, att) + (ccd + cce) * cc
        s.spec = wp.cw_mul(spec_d, att) + ccd * cc
        s.env_spec = wp.cw_mul(spec_e, att) + cce * cc
    return s


@wp.kernel
def k_look(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), tri: wp.array(dtype=wp.int32),
           vn: wp.array(dtype=wp.vec3), uvs: wp.array(dtype=wp.vec2), tmat: wp.array(dtype=wp.int32),
           tang: wp.array(dtype=wp.vec3), bitang: wp.array(dtype=wp.vec3),
           tex: wp.array(dtype=wp.vec3), s_first: wp.array(dtype=wp.int32), s_nlv: wp.array(dtype=wp.int32),
           lv_off: wp.array(dtype=wp.int32), lv_w: wp.array(dtype=wp.int32), lv_h: wp.array(dtype=wp.int32),
           m_flags: wp.array(dtype=wp.int32), vtan: wp.array(dtype=wp.vec4), use_vtan: int,
           m_par: wp.array(dtype=wp.vec4), dfg: wp.array(dtype=wp.vec2), env_rad: wp.array(dtype=wp.vec3),
           env_irr: wp.array(dtype=wp.vec3), n_mu: int, n_r: int,
           origin0: wp.vec3, du: wp.vec3, dv: wp.vec3, dirv: wp.vec3, size: int, ss: int, light: wp.vec3,
           key: wp.vec3, lod_bias: float, out: wp.array(dtype=wp.vec3), out_cov: wp.array(dtype=float),
           out_spec: wp.array(dtype=wp.vec3), out_envs: wp.array(dtype=wp.vec3)):
    tid = wp.tid()
    px = tid % size
    py = tid // size
    V = -dirv
    ex = wp.normalize(du)                  # the view space (x right, y up, z = V): three's geometry roughness
    ey = -wp.normalize(dv)
    inv = 1.0 / float(ss)
    acc = wp.vec3(0.0)
    acc_s = wp.vec3(0.0)
    acc_e = wp.vec3(0.0)
    hits = float(0.0)
    for i in range(ss):
        for j in range(ss):
            o = origin0 + du * (float(px) + (float(i) + 0.5) * inv) + dv * (float(py) + (float(j) + 0.5) * inv)
            q = wp.mesh_query_ray(mesh, o, dirv, 1.0e3)
            if not q.result:
                continue
            hits = hits + 1.0
            f = q.face
            w0 = q.u
            w1 = q.v
            w2 = 1.0 - q.u - q.v
            i0 = tri[3 * f]
            i1 = tri[3 * f + 1]
            i2 = tri[3 * f + 2]
            ni = vn[i0] * w0 + vn[i1] * w1 + vn[i2] * w2
            li = wp.max(wp.length(ni), 1.0e-20)
            n = ni / li
            uv = uvs[i0] * w0 + uvs[i1] * w1 + uvs[i2] * w2
            # ray differentials (orthographic: parallel rays whose origin steps du / dv a pixel): the hit's motion in
            # the triangle's plane, then its barycentric (P = p2 + w0 e0 + w1 e1), uv and normal derivatives
            e0 = pts[i0] - pts[i2]
            e1 = pts[i1] - pts[i2]
            nf = wp.cross(e0, e1)
            den = wp.dot(dirv, nf)
            lim = 1.0e-4 * wp.length(nf)
            if wp.abs(den) < lim:
                if den < 0.0:
                    den = -lim
                else:
                    den = lim
            dpx = du - dirv * (wp.dot(du, nf) / den)
            dpy = dv - dirv * (wp.dot(dv, nf) / den)
            g00 = wp.dot(e0, e0)
            g01 = wp.dot(e0, e1)
            g11 = wp.dot(e1, e1)
            idet = 1.0 / wp.max(g00 * g11 - g01 * g01, 1.0e-30)
            ax = (g11 * wp.dot(e0, dpx) - g01 * wp.dot(e1, dpx)) * idet
            bx = (g00 * wp.dot(e1, dpx) - g01 * wp.dot(e0, dpx)) * idet
            ay = (g11 * wp.dot(e0, dpy) - g01 * wp.dot(e1, dpy)) * idet
            by = (g00 * wp.dot(e1, dpy) - g01 * wp.dot(e0, dpy)) * idet
            t0 = uvs[i0] - uvs[i2]
            t1 = uvs[i1] - uvs[i2]
            uvx = t0 * ax + t1 * bx                # one pixel's footprint: the engine's LOD, the same at every ss
            uvy = t0 * ay + t1 * by
            m0 = vn[i0] - vn[i2]
            m1 = vn[i1] - vn[i2]
            dnx = m0 * ax + m1 * bx
            dny = m0 * ay + m1 * by
            dnx = (dnx - n * wp.dot(n, dnx)) / li  # the normalised normal's change over one pixel (three's dFdx)
            dny = (dny - n * wp.dot(n, dny)) / li
            geo_r = wp.max(wp.max(wp.max(wp.abs(wp.dot(dnx, ex)), wp.abs(wp.dot(dny, ex))),
                                  wp.max(wp.abs(wp.dot(dnx, ey)), wp.abs(wp.dot(dny, ey)))),
                           wp.max(wp.abs(wp.dot(dnx, V)), wp.abs(wp.dot(dny, V))))
            if wp.dot(n, dirv) > 0.0:
                n = -n
            m = tmat[f]
            # texture slots per material: 0 albedo (linear), 1 normal, 2 packed (r rough, g metal, b ao)
            base = m * 3
            alb = wp.vec3(0.7, 0.7, 0.7)
            if s_nlv[base] > 0:
                alb = tex_mip(tex, lv_off, lv_w, lv_h, s_first[base], s_nlv[base], uv, uvx, uvy, lod_bias)
            nn = n
            if s_nlv[base + 1] > 0:
                t4 = tex_mip(tex, lv_off, lv_w, lv_h, s_first[base + 1], s_nlv[base + 1], uv, uvx, uvy, lod_bias)
                tx = t4[0] * 2.0 - 1.0
                ty = t4[1] * 2.0 - 1.0
                if m_flags[m] == 1:
                    ty = -ty                       # DirectX convention (green down)
                if use_vtan == 1:
                    # the engine's own math (material.engine_tbn: three r184's TSL with a tangent attribute, the one
                    # copy the bake encodes with): its T and B, the interpolated normal n (the frame's N; turned on a
                    # back face as above), the stored z, mat3(T, B, N) * n, normalised
                    tz = t4[2] * 2.0 - 1.0
                    fr = MT.engine_tbn(vn[i0], vn[i1], vn[i2], vtan[i0], vtan[i1], vtan[i2], w0, w1, w2)
                    T = wp.vec3(fr[0, 0], fr[1, 0], fr[2, 0])
                    B = wp.vec3(fr[0, 1], fr[1, 1], fr[2, 1])
                    nn = wp.normalize(T * tx + B * ty + n * tz)
                else:
                    tz = wp.sqrt(wp.max(1.0 - tx * tx - ty * ty, 0.0))
                    T = wp.normalize(tang[f] - n * wp.dot(tang[f], n))
                    B = wp.normalize(bitang[f] - n * wp.dot(bitang[f], n) - T * wp.dot(bitang[f], T))
                    nn = wp.normalize(T * tx + B * ty + n * tz)
            rough = 0.5
            metal = 0.0
            ao = 1.0
            if s_nlv[base + 2] > 0:
                p4 = tex_mip(tex, lv_off, lv_w, lv_h, s_first[base + 2], s_nlv[base + 2], uv, uvx, uvy, lod_bias)
                rough = p4[0]
                metal = p4[1]
                ao = p4[2]
            sh = shade(nn, n, V, light, key, alb, rough, metal, ao, m_par[m], geo_r, dfg, env_rad, env_irr, n_mu,
                       n_r)
            acc = acc + sh.rgb
            acc_s = acc_s + sh.spec
            acc_e = acc_e + sh.env_spec
    w = 1.0 / float(ss * ss)
    out[tid] = acc * w                     # premultiplied by the coverage
    out_cov[tid] = hits * w
    out_spec[tid] = acc_s * w
    out_envs[tid] = acc_e * w


def tangent_frames(V, F, UV):
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    t0, t1, t2 = UV[F[:, 0]], UV[F[:, 1]], UV[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = t1 - t0, t2 - t0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-12, 1e-12, r)
    T = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
    B = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    # glTF UV v runs down the image: flip the bitangent so +v (image up) is the normal map's +g
    B = -B
    nrm = lambda x: x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-20)
    return nrm(T), nrm(B)


def render(mesh, materials, out_png, views=('threeq', 'side', 'front'), size=900, ss=2, label='', box=None,
           center=None, span=None, light_mix=(0.45, 0.75, 0.45), tone='agx', exposure=1.0, key=KEY, env=None,
           bg=BG, lod_bias=0.0, aov=None):
    """center/span frame the shot exactly as voxel.trace_views does (A/B against the SDF high); light_mix = the key
    light's (camera, up, right) weights (trace_views uses (0.55, 0.65, 0.35)); tone 'agx' (three r184, the engine's),
    'legacy' or 'linear', after exposure; key = the key light's irradiance (scalar or RGB); env = the sky/ground
    (ENV's keys; radiance scalar or RGB); bg = the background's display sRGB8; lod_bias shifts every mip level;
    aov: a dict that receives per view name the linear buffers (rgb premultiplied by cov, cov, spec = the key's
    specular, env_spec = the environment's), the display image and the frame (cx, cy, span)"""
    V = np.asarray(mesh['V'], np.float32)
    F = np.asarray(mesh['F'], np.int32)
    UV = np.asarray(mesh['UV'], np.float32)
    M = np.asarray(mesh['mat'], np.int32)
    if box is not None:
        b = np.asarray(box, np.float32)
        c = V[F].mean(1)
        keep = np.all((c >= b[:3]) & (c <= b[3:]), axis=1)
        F, M = F[keep], M[keep]
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)
    if mesh.get('N') is not None:
        vn = np.asarray(mesh['N'], np.float32)            # the asset's own (welded) normals
    vtan = np.asarray(mesh['TAN'], np.float32) if mesh.get('TAN') is not None else np.zeros((1, 4), np.float32)
    T, B = tangent_frames(V.astype(np.float64), F, UV.astype(np.float64))
    tex = _textures(materials)
    pts = wp.array(V, dtype=wp.vec3)
    mesh_d = wp.Mesh(points=pts, indices=wp.array(F.ravel(), dtype=wp.int32))
    args = [mesh_d.id, pts, wp.array(F.ravel(), dtype=wp.int32), wp.array(vn, dtype=wp.vec3),
            wp.array(UV, dtype=wp.vec2), wp.array(M, dtype=wp.int32), wp.array(T.astype(np.float32), dtype=wp.vec3),
            wp.array(B.astype(np.float32), dtype=wp.vec3)] + tex + [
            wp.array(vtan, dtype=wp.vec4), 1 if mesh.get('TAN') is not None else 0,
            _material_params(materials), _dfg_device()] + _env_device(env)
    return _shoot(args, V, F, views, size, ss, label, center, span, light_mix, out_png, tone=tone,
                  exposure=exposure, key=key, bg=bg, lod_bias=lod_bias, aov=aov)


_TEX_CACHE = {}


def srgb_eotf(s):
    """sRGB (0..1) -> linear, exact (the GPU's decode of an sRGB texture): the house helper (forge/material.py)"""
    from .material import srgb_eotf as eotf
    return eotf(s)


def srgb_oetf(L):
    """linear -> sRGB (0..1), exact (three's outputColorSpace = SRGBColorSpace): the house helper (forge/material.py)"""
    from .material import srgb_oetf as oetf
    return oetf(L)


def _texels(img, srgb):
    """an image as float32 (h, w, 3): sRGB decoded per texel (an sRGB texture's order: decode, then filter) or data"""
    a = np.asarray(img)
    if a.ndim == 2:
        a = a[..., None]
    a = a[..., :3]
    if a.shape[2] == 1:
        a = np.repeat(a, 3, axis=2)
    if a.dtype == np.uint8:
        lut = srgb_eotf(np.arange(256) / 255.0) if srgb else np.arange(256) / 255.0
        return lut.astype(np.float32)[a]
    a = np.clip(a.astype(np.float32) / 255.0, 0.0, 1.0)
    return srgb_eotf(a).astype(np.float32) if srgb else a


def _mip_shapes(h, w):
    out = [(h, w)]
    while h > 1 or w > 1:
        h, w = max(h // 2, 1), max(w // 2, 1)
        out.append((h, w))
    return out


def _mip_down(a):
    """the next mip level: 2x2 box averages, an odd last row / column dropped (generateMipmap)"""
    h, w = a.shape[:2]
    if h > 1:
        a = 0.5 * (a[0:h - h % 2:2] + a[1:h - h % 2:2])
    if w > 1:
        a = 0.5 * (a[:, 0:w - w % 2:2] + a[:, 1:w - w % 2:2])
    return a


def _textures(materials):
    """the materials' textures in one device buffer (per material 3 slots: albedo, normal, packed rough/metal/ao), each
    slot's whole mip chain (level offsets and sizes in a table), cached on the identity of the image arrays (a motion
    probe re-renders the same 4K maps every frame)"""
    key = tuple(id(m.get(k)) for m in materials for k in ('albedo', 'normal', 'rough', 'metal', 'ao')) + \
        tuple(bool(m.get('normal_green_down')) for m in materials)
    hit = _TEX_CACHE.get(key)
    if hit is not None:
        return hit[0]
    _TEX_CACHE.clear()                     # one material set at a time on the GPU (freed before the next is built)
    slots, flags = [], []
    for mtl in materials:
        packed = None
        if mtl.get('rough') is not None or mtl.get('metal') is not None or mtl.get('ao') is not None:
            ref = next(x for x in (mtl.get('rough'), mtl.get('metal'), mtl.get('ao')) if x is not None)
            hh, ww = ref.shape[:2]
            ch = lambda x, d: (np.asarray(Image.fromarray(x).resize((ww, hh))) if x is not None and x.shape[:2] != (hh, ww)
                               else x) if x is not None else np.full((hh, ww), d, np.uint8)
            packed = np.stack([ch(mtl.get('rough'), 128), ch(mtl.get('metal'), 0), ch(mtl.get('ao'), 255)], -1)
        slots += [(mtl.get('albedo'), True), (mtl.get('normal'), False), (packed, False)]
        flags.append(1 if mtl.get('normal_green_down') else 0)
    shapes = [None if img is None else _mip_shapes(*np.asarray(img).shape[:2]) for img, _ in slots]
    texbuf = np.zeros((max(sum(h * w for sh in shapes if sh for h, w in sh), 1), 3), np.float32)
    s_first, s_nlv, lv_off, lv_w, lv_h = [], [], [], [], []
    cur = 0
    for (img, srgb), sh in zip(slots, shapes):
        if sh is None:
            s_first.append(0)
            s_nlv.append(0)
            continue
        s_first.append(len(lv_off))
        s_nlv.append(len(sh))
        a = _texels(img, srgb)
        for k, (hh, ww) in enumerate(sh):
            if k:
                a = _mip_down(a)
            texbuf[cur:cur + hh * ww] = a.reshape(-1, 3)
            lv_off.append(cur)
            lv_w.append(ww)
            lv_h.append(hh)
            cur += hh * ww
    i32 = lambda x: wp.array(np.asarray(x if x else [0], np.int32), dtype=wp.int32)
    out = [wp.array(texbuf, dtype=wp.vec3), i32(s_first), i32(s_nlv), i32(lv_off), i32(lv_w), i32(lv_h), i32(flags)]
    _TEX_CACHE[key] = (out, [m for m in materials])
    return out


def _material_params(materials):
    """per material (F0, clearcoat, clearcoat roughness, specular intensity); F0 = 'f0', else from 'ior' as three's
    MeshPhysicalMaterial: ((n - 1) / (n + 1))^2 (its default ior 1.5: 0.04)"""
    rows = []
    for m in materials:
        f0 = m.get('f0')
        if f0 is None:
            n = float(m.get('ior', 1.5))
            f0 = ((n - 1.0) / (n + 1.0)) ** 2
        rows.append((min(float(f0), 1.0), float(m.get('clearcoat', 0.0)), float(m.get('clearcoat_rough', 0.0)),
                     float(m.get('specular_intensity', 1.0))))
    return wp.array(np.asarray(rows or [(0.04, 0.0, 0.0, 1.0)], np.float32), dtype=wp.vec4)


def _rgb(x):
    """a scalar or an RGB triple as an RGB float64 array"""
    return np.broadcast_to(np.asarray(x, np.float64), (3,)).copy()


_ENV_CACHE = {}
_ENV_DEV = {}


def env_tables(env=None, n_mu=129, n_r=17, n_dir=40000, n_ggx=4096):
    """the analytic sky/ground (ENV's keys: sky and ground radiance, scalar or RGB; soft = the horizon's half width in
    elevation sine) as two tables over the elevation sine mu in [-1, 1] (n_mu points): irr (n_mu, 3) = the irradiance
    / pi of a normal at mu (the diffuse), rad (n_r, n_mu, 3) = the split-sum GGX prefilter of a reflection at mu for the
    roughness j / (n_r - 1) (Karis 2013: N = V = R, GGX samples weighted by N.L: what three's PMREM approximates)"""
    e = dict(ENV, **(env or {}))
    sky, ground, soft = _rgb(e['sky']), _rgb(e['ground']), float(e['soft'])
    key = (tuple(sky), tuple(ground), soft, n_mu, n_r, n_dir, n_ggx)
    hit = _ENV_CACHE.get(key)
    if hit is not None:
        return hit

    def radiance(y):
        y = np.asarray(y, np.float64)
        if soft > 0.0:
            t = np.clip((y + soft) / (2.0 * soft), 0.0, 1.0)
            s = t * t * (3.0 - 2.0 * t)
        else:
            s = np.where(y > 0.0, 1.0, np.where(y < 0.0, 0.0, 0.5))
        return ground + (sky - ground) * s[..., None]

    mu = np.linspace(-1.0, 1.0, n_mu)
    sn = np.sqrt(np.maximum(1.0 - mu * mu, 0.0))
    k = np.arange(n_dir) + 0.5
    y = 1.0 - 2.0 * k / n_dir                               # a Fibonacci sphere: equal-area directions
    x = np.sqrt(np.maximum(1.0 - y * y, 0.0)) * np.cos(k * np.pi * (3.0 - np.sqrt(5.0)))
    irr = np.maximum(np.outer(sn, x) + np.outer(mu, y), 0.0) @ radiance(y) * (4.0 / n_dir)
    i = np.arange(n_ggx)
    u1 = (i + 0.5) / n_ggx
    u2 = np.zeros(n_ggx)                                    # Hammersley: the radical inverse in base 2
    b, f = i.copy(), 0.5
    while b.any():
        u2 += f * (b & 1)
        b >>= 1
        f *= 0.5
    rad = np.empty((n_r, n_mu, 3))
    for j in range(n_r):
        a = (j / (n_r - 1)) ** 2
        if a == 0.0:
            rad[j] = radiance(mu)
            continue
        ch = np.sqrt((1.0 - u1) / (1.0 + (a * a - 1.0) * u1))
        sh = np.sqrt(np.maximum(1.0 - ch * ch, 0.0))
        lx = 2.0 * ch * sh * np.cos(2.0 * np.pi * u2)       # L = 2 (N.H) H - N in the frame (T, B, N); N.H = ch
        lz = 2.0 * ch * ch - 1.0
        w = np.maximum(lz, 0.0)
        ly = np.clip(np.outer(sn, lx) + np.outer(mu, lz), -1.0, 1.0)   # N = (sn, mu, 0), T = (-mu, sn, 0)
        rad[j] = (radiance(ly) * w[None, :, None]).sum(1) / w.sum()
    _ENV_CACHE[key] = (irr, rad)
    return irr, rad


def _env_device(env):
    """the sky/ground tables on the device (kernel arguments: rad, irr, n_mu, n_r), cached with the host tables"""
    irr, rad = env_tables(env)
    dev = _ENV_DEV.get(id(irr))
    if dev is None:
        dev = _ENV_DEV[id(irr)] = [wp.array(rad.reshape(-1, 3).astype(np.float32), dtype=wp.vec3),
                                   wp.array(irr.astype(np.float32), dtype=wp.vec3), int(rad.shape[1]),
                                   int(rad.shape[0])]
    return dev


# three r184's DFG LUT (nodes/functions/BSDF/DFGLUT.js: 16 x 16 RG16F, 4096 samples a texel), the half floats as hex:
# 16 rows by N.V (two strings each), each 16 (scale, bias) pairs by roughness
_DFG_HEX = (
    '30b53ad1314c3a4d33d2391c35ef382837f336a638d135393979341039f83252',
    '3a5330f03a942fc93abf2e353ada2d053ae82c1f3aed2ae03aea29d13ae128ff',
    '363838e4364a38ce3699385e374e372c383935a438dc3462396e32c439de3134',
    '3a2b30033a592e3a3a6d2ce13a6e2bba3a5f2a333a49290a3a2d28263a0a26e8',
    '389436d7389736c938a3367538bc35ac38ee349c393e33323997318639e23038',
    '3a132e753a292cf53a2d2bac3a2129ff3a0428bc39dc279039ad261a397824fa',
    '39ac34a839ac34a339ae348039ae342339b1330e39c231a939e0306339fc2eb5',
    '3a0c2d1d3a142bcf3a0729ff39e928a339be273c398925b3394a248839072345',
    '3a7732233a76321f3a7332043a6a31b33a5831143a45303b3a342eb63a262d31',
    '3a1e2bef3a0b2a0d39ec28a139c0271b398725803944244938fa22bd38ac2155',
    '3b072fca3b062fca3b002fb83af42f7c3adb2eea3ab42e003a852cec3a5e2bc5',
    '3a362a003a0d289939dc270739a02562395a2424390b226838b720fd385f1fd1',
    '3b692cb93b682cbb3b622cbb3b562cae3b3b2c783b0d2c0a3acf2ae33a922998',
    '3a5428673a1726d039d3253c398924023935222638dc20bd387d1f54381d1db3',
    '3ba9296b3ba8296f3ba3297b3b9829873b7f29763b4e29273b0e28953ac227b7',
    '3a73263b3a2324e739d0239b397621d93917207e38b21ee7384b1d5337c71c1e',
    '3bd225cb3bd125d33bcd25f03bc2261f3bad26453b7d262d3b3e25c43aec250f',
    '3a93243a3a3222ce39d0215b3969202a38fe1e6e388f1cf1381f1b9b376219dd',
    '3be921ab3be921b73be521e53bdd22413bc922a73ba022ec3b6222cd3b0f2247',
    '3aae21753a44208839d41f4939601dbe38e91c7738701ae837f119533708181b',
    '3bf61cea3bf61cfb3bf31d383bec1dbd3bda1e7c3bb71f253b7d1f793b2c1f4c',
    '3ac61ea63a551dbb39da1cbd395a1b9d38d81a00385518ac37ab173c36b71598',
    '3bfc17363bfc17593bf917e73bf418963be419973bc61aa83b911b843b431bd2',
    '3ade1b8a3a651acd39e219d3395718cd38ca17b3383e1613376d14bf366f135e',
    '3bff101b3bff10393bfc10c83bf912263bea14283bcf15843b9f16c53b54179a',
    '3af017ce3a76177139ea16a4395615a738bf14a738291379373511ea362d10a1',
    '3c00061b3c00066a3bfe081c3bfa0a4c3bed0d163bd50fb33ba9114d3b63127c',
    '3b01132f3a85134439f412d23957120d38b511223817103c37030ed335f00d6d',
    '3c00007a3c0000893bfe011d3bfb027c3bf004fa3bda08813bb10acd3b6f0c97',
    '3b100d7b3a930df139fe0def39590d8a38af0ce938080c3136d50af035b909a3',
    '3c0000003c0000013bff00153bfb00593bf200fd3bdd01df3bb7031c3b79047c',
    '3b1d05d43aa006d53a08075a395d075e38aa06f737f4064836ac05763586049f',
)
_DFG_DEV = []


def dfg_table():
    """three's DFG LUT as float32 (16 rows by N.V, 16 columns by roughness, (F0 scale, F90 bias))"""
    h = np.frombuffer(bytes.fromhex(''.join(_DFG_HEX)), '>u2').astype(np.uint16).view(np.float16)
    return h.astype(np.float32).reshape(16, 16, 2)


def _dfg_device():
    if not _DFG_DEV:
        _DFG_DEV.append(wp.array(dfg_table().reshape(-1, 2), dtype=wp.vec2))
    return _DFG_DEV[0]


# three r184's AgXToneMapping (src/nodes/display/ToneMappingFunctions.js), the constants as research/colour_work/
# scripts/agx_check.py transcribed them: TSL's mat3(vec3, vec3, vec3) takes COLUMNS, so each written matrix is
# transposed
_AGX_INSET = np.array([[0.856627153315983, 0.137318972929847, 0.11189821299995],
                       [0.0951212405381588, 0.761241990602591, 0.0767994186031903],
                       [0.0482516061458583, 0.101439036467562, 0.811302368396859]]).T
_AGX_OUTSET = np.array([[1.1271005818144368, -0.1413297634984383, -0.14132976349843826],
                        [-0.11060664309660323, 1.157823702216272, -0.11060664309660294],
                        [-0.016493938717834573, -0.016493938717834257, 1.2519364065950405]]).T
_SRGB_TO_REC2020 = np.array([[0.6274, 0.0691, 0.0164], [0.3293, 0.9195, 0.0880], [0.0433, 0.0113, 0.8956]]).T
_REC2020_TO_SRGB = np.array([[1.6605, -0.1246, -0.0182], [-0.5876, 1.1329, -0.1006], [-0.0728, -0.0083, 1.1187]]).T
_AGX_EV = (-12.47393, 4.026069)


def agx(c, exposure=1.0):
    """three r184's AgX: scene-linear sRGB (..., 3) -> display-linear sRGB in [0, 1] (the sRGB OETF follows)"""
    c = np.asarray(c, np.float64) * exposure
    c = c @ _SRGB_TO_REC2020.T
    c = c @ _AGX_INSET.T
    c = np.log2(np.maximum(c, 1e-10))
    c = np.clip((c - _AGX_EV[0]) / (_AGX_EV[1] - _AGX_EV[0]), 0.0, 1.0)
    x2 = c * c
    x4 = x2 * x2
    c = 15.5 * x4 * x2 - 40.14 * x4 * c + 31.96 * x4 - 6.868 * x2 * c + 0.4298 * x2 + 0.1191 * c - 0.00232
    c = c @ _AGX_OUTSET.T
    c = np.maximum(c, 0.0) ** 2.2
    c = c @ _REC2020_TO_SRGB.T
    return np.clip(c, 0.0, 1.0)


def display(lin, tone='agx', exposure=1.0):
    """scene-linear radiance -> display sRGB in [0, 1]: 'agx' (three r184: toneMapping = AgXToneMapping, then the
    sRGB output), 'legacy' (the old curve 1.25 x / (1 + x), then x^(1 / 2.2)), 'linear' (clamped, sRGB)"""
    lin = np.asarray(lin, np.float64) * exposure
    if tone == 'agx':
        return srgb_oetf(agx(lin))
    if tone == 'legacy':
        return np.clip(lin / (1.0 + lin) * 1.25, 0.0, 1.0) ** (1.0 / 2.2)
    if tone == 'linear':
        return srgb_oetf(lin)
    raise ValueError(f'lookdev: tone {tone!r} (agx, legacy or linear)')


TONES = ('agx', 'legacy', 'linear')


def _agx_mats():
    """AgX's matrices as agx() applies them (c <- M c), for k_display: sRGB -> Rec.2020 and the inset in one, the
    outset, Rec.2020 -> sRGB"""
    return [wp.mat33(*np.asarray(m, np.float32).ravel()) for m in
            (_AGX_INSET @ _SRGB_TO_REC2020, _AGX_OUTSET, _REC2020_TO_SRGB)]


@wp.func
def oetf1(x: float):
    """the exact sRGB OETF of one channel, clamped to [0, 1] first (srgb_oetf)"""
    y = wp.clamp(x, 0.0, 1.0)
    if y <= 0.0031308:
        return 12.92 * y
    return 1.055 * wp.pow(y, 1.0 / 2.4) - 0.055


@wp.func
def agx1(v: float, ev0: float, ev1: float):
    """AgX's log2 encoding and sigmoid polynomial of one channel (agx)"""
    x = wp.clamp((wp.log2(wp.max(v, 1.0e-10)) - ev0) / (ev1 - ev0), 0.0, 1.0)
    x2 = x * x
    x4 = x2 * x2
    return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232


@wp.func
def pow22(v: float):
    return wp.pow(wp.max(v, 0.0), 2.2)


@wp.kernel
def k_display(rgb: wp.array(dtype=wp.vec3), cov: wp.array(dtype=float), tone: int, exposure: float,
              m_in: wp.mat33, m_out: wp.mat33, m_rec: wp.mat33, ev0: float, ev1: float, bg: wp.vec3,
              out: wp.array(dtype=wp.vec3)):
    """display() per pixel on the device: the mean radiance of the samples that hit (rgb is premultiplied by cov) times
    the exposure, tone mapped (TONES: 0 agx, 1 legacy, 2 linear), laid over the background (display) by the coverage"""
    tid = wp.tid()
    c = cov[tid]
    lin = rgb[tid] * (exposure / wp.max(c, 1.0e-12))
    d = wp.vec3(0.0)
    if tone == 0:
        a = m_in @ lin
        b = m_out @ wp.vec3(agx1(a[0], ev0, ev1), agx1(a[1], ev0, ev1), agx1(a[2], ev0, ev1))
        e = m_rec @ wp.vec3(pow22(b[0]), pow22(b[1]), pow22(b[2]))
        d = wp.vec3(oetf1(e[0]), oetf1(e[1]), oetf1(e[2]))
    elif tone == 1:
        q = 1.0 / 2.2
        d = wp.vec3(wp.pow(wp.clamp(lin[0] / (1.0 + lin[0]) * 1.25, 0.0, 1.0), q),
                    wp.pow(wp.clamp(lin[1] / (1.0 + lin[1]) * 1.25, 0.0, 1.0), q),
                    wp.pow(wp.clamp(lin[2] / (1.0 + lin[2]) * 1.25, 0.0, 1.0), q))
    else:
        d = wp.vec3(oetf1(lin[0]), oetf1(lin[1]), oetf1(lin[2]))
    o = d * c + bg * (1.0 - c)
    out[tid] = wp.vec3(wp.clamp(o[0], 0.0, 1.0), wp.clamp(o[1], 0.0, 1.0), wp.clamp(o[2], 0.0, 1.0))


def _shoot(args, V, F, views, size, ss, label, center, span, light_mix, out_png, tone='agx', exposure=1.0, key=KEY,
           bg=BG, lod_bias=0.0, aov=None):
    from .render import basis
    used = np.unique(F)
    P = V[used]
    key3 = _rgb(key)
    bg3 = np.asarray(bg, np.float64) / 255.0
    if tone not in TONES:
        raise ValueError(f'lookdev: tone {tone!r} (agx, legacy or linear)')
    tone_i, agx_m = TONES.index(tone), _agx_mats()
    tiles = []
    for vname in views:
        right, upv, cam = basis(vname)
        X, Y = P @ right, P @ upv
        if center is not None:
            ctr = np.asarray(center, np.float64)
            cx, cy = float(ctr @ right), float(ctr @ upv)
            sp = float(span)
        else:
            sp = max(X.max() - X.min(), Y.max() - Y.min()) * 1.06
            cx, cy = (X.max() + X.min()) / 2, (Y.max() + Y.min()) / 2
        pix = sp / size
        far = float((P @ cam).max()) + 1.0
        origin0 = right * (cx - sp / 2) + upv * (cy + sp / 2) + cam * far
        light = cam * light_mix[0] + upv * light_mix[1] + right * light_mix[2]
        light /= np.linalg.norm(light)
        n = size * size
        out, cov, disp = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=float), wp.zeros(n, dtype=wp.vec3)
        spec, envs = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec3)
        wp.launch(k_look, dim=n, inputs=args + [wp.vec3(*origin0), wp.vec3(*(right * pix)), wp.vec3(*(-upv * pix)),
                                                wp.vec3(*(-cam)), size, ss, wp.vec3(*light), wp.vec3(*key3),
                                                float(lod_bias), out, cov, spec, envs])
        # tone map the mean radiance of the samples that hit (the engine resolves, then tone maps), then lay it over
        # the background by the coverage: display() on the device
        wp.launch(k_display, dim=n, inputs=[out, cov, tone_i, float(exposure)] + agx_m +
                  [float(_AGX_EV[0]), float(_AGX_EV[1]), wp.vec3(*bg3), disp])
        img = (disp.numpy().reshape(size, size, 3) * 255.0 + 0.5).astype(np.uint8)
        if aov is not None:
            aov[vname] = dict(rgb=out.numpy().reshape(size, size, 3), cov=cov.numpy().reshape(size, size),
                              spec=spec.numpy().reshape(size, size, 3), env_spec=envs.numpy().reshape(size, size, 3),
                              display=img, frame=(cx, cy, sp))
        im = Image.fromarray(img)
        ImageDraw.Draw(im).text((6, 6), f'{label} {vname}  frame {sp:.3f} m', fill=(240, 240, 240))
        tiles.append(im)
    sheet = Image.new('RGB', (size * len(tiles), size))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * size, 0))
    if out_png is None:
        return np.asarray(sheet)            # a frame for a video pipe (no files per frame)
    sheet.save(out_png)
    return out_png
