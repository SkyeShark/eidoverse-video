"""The human skin's LOOK-DEV TWIN (HUMAN_PLAN §5.1's parity rule, H3): the forge's preview of the skin, shading exactly as
the engine's TSL node does (work/bestiary/engine_test/human_skin.js: SkinLightingModel and skinMaterial), so a pigment
map, a zone or a LUT judged here reads the same in the engine. Kept apart from forge/lookdev.py (the other bases' look-
dev stays as it is); it calls lookdev's own device functions for three r184's GGX, DFG, environment and AgX display.

Per pixel (ss x ss parallel rays, orthographic, lookdev's frame): the clay's channels interpolated at the hit (the
engine's varyings), CLAMPED to [0, 1] (the engine's MSAA fix), then:
  * pigments f_mel = melanin0 x 2^((R - 0.5) 12), f_blood = blood0 x 2^((G - 0.5) 12); the albedo LUT at (sqrt(f_mel /
    MEL_MAX), sqrt(f_blood / BLOOD_MAX)): bilinear between texel centres, clamped, its float16 values (the GPU's);
  * roughness: the zone's lowered by the wet film, (r^4 + var)^(1/4) with var the faded micro relief's (pores x
    MICRO_VAR, the relief itself faded at this footprint) plus the specular AA of the normal's change over the pixel;
    then three's getRoughness: max(r, 0.0525) + the geometry roughness, at most 1;
  * the KEY: the pre-integrated diffuse LUT at (N.L / 2 + 1/2, curvature x the tissue scale) per channel, x albedo / pi;
    the dual-lobe GGX (r x 0.75, r x 1.30, mixed 0.85) at F0 0.0278; the transmission E^2 exp(-k t) x (the back lobe
    / pi + the forward lobe x TRANS_FWD), all at the key's irradiance; NO SHADOW (the parity view lights unshadowed:
    the engine's shadow map and its penumbra have no twin here);
  * the ENVIRONMENT: lookdev's analytic sky / ground (ENV), three's split-sum specular and multiscatter diffuse with
    the AO (lookdev.shade's environment half, with the skin's albedo and F0).
    render_skin(V, F, N, pig, surf, aux, U, lut, out_png, view='front', size, ss, center, span, light, key, env)

THE TEXTURED TWIN (the H3 integrator, 10-30: render_skin_tex): the glb's textured skin (h3/integrate/i02_glb.py), read
as the engine reads it: the split meshes' NORMAL and TANGENT through material.engine_tbn (three r184's per-fragment
frame), the five maps per set (N, the macro normal, the RGB packs PIGMENT / SURFACE / AUX: human_skin.js's textured
path) with the engine's own mip chain (eidoverse/render_scene.mjs _buildCpuMips: a 2 x 2 box per channel on the 8-bit
codes, truncating), sampled trilinear and anisotropically (up to 16 trilinear taps along the pixel footprint's long
axis, the footprint from the ray differentials), the composed normal decoded with its filtered length (Toksvig, the
shader's), each channel's pre-integrated diffuse at its own normal between the macro and the detail normal
(human_skin.js DIFF_NORMAL), the runtime relief's faded variance (AUX.B), the transmission and environment as above.
(H3b, the integrator 10-31, after the merge of the H3b material builder's shader: each channel's blend fades to the
detail normal where the two normals disagree (AGREE), the multi-bounce AO per channel on the indirect diffuse
(AO_BOUNCE), the wet tissue's AO floor (WET_AO_FLOOR) and the micro-shadow on direct light (MICRO_SHADOW). The runtime
variation, the eye's parts and the scattered shadow have no twin: the parity view renders without them.)
    render_skin_tex(sets, U, lut, out_png, view='front', size, ss, center, span, light, key, env)
"""
import numpy as np
import warp as wp
from PIL import Image

from .. import lookdev as LD
from .. import material as MT

wp.set_module_options({'enable_backward': False})

# the TSL node's constants (engine_test/human_skin.js K), one copy each side
MEL_MAX, BLOOD_MAX, CURV_MAX, LOG_RANGE = 1.0, 0.20, 1.0, 12.0
THICK_MAX, TISSUE_MAX, TISSUE_REF = 50.0, 4.0, 1.4
IOR = 1.4
LOBE0, LOBE1, LOBE_MIX = 0.75, 1.30, 0.85
TRANS_FWD = 1.2
MICRO_VAR = 0.035
SAA_SIGMA2, SAA_KAPPA = 0.15915494, 0.18


@wp.func
def lut2(tab: wp.array(dtype=wp.vec3), w: int, h: int, x: float, y: float):
    """the GPU's bilinear lookup: texel centres at (i + 0.5) / n, clamped to the edge"""
    fx = wp.clamp(x * float(w) - 0.5, 0.0, float(w - 1))
    fy = wp.clamp(y * float(h) - 0.5, 0.0, float(h - 1))
    x0 = int(wp.floor(fx))
    y0 = int(wp.floor(fy))
    x1 = wp.min(x0 + 1, w - 1)
    y1 = wp.min(y0 + 1, h - 1)
    ax = fx - float(x0)
    ay = fy - float(y0)
    a = tab[y0 * w + x0] * (1.0 - ax) + tab[y0 * w + x1] * ax
    b = tab[y1 * w + x0] * (1.0 - ax) + tab[y1 * w + x1] * ax
    return a * (1.0 - ay) + b * ay


@wp.func
def clamp4(v: wp.vec4):
    return wp.vec4(wp.clamp(v[0], 0.0, 1.0), wp.clamp(v[1], 0.0, 1.0), wp.clamp(v[2], 0.0, 1.0),
                   wp.clamp(v[3], 0.0, 1.0))


@wp.kernel
def k_skin(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), tri: wp.array(dtype=wp.int32),
           vn: wp.array(dtype=wp.vec3), pig: wp.array(dtype=wp.vec4), surf: wp.array(dtype=wp.vec4),
           aux: wp.array(dtype=wp.vec4), alb_t: wp.array(dtype=wp.vec3), tr_t: wp.array(dtype=wp.vec3),
           pre_t: wp.array(dtype=wp.vec3), dfg: wp.array(dtype=wp.vec2), env_rad: wp.array(dtype=wp.vec3),
           env_irr: wp.array(dtype=wp.vec3), n_mu: int, n_r: int, mel0: float, blood0: float, wet_u: float,
           pores_u: float, origin0: wp.vec3, du: wp.vec3, dv: wp.vec3, dirv: wp.vec3, size: int, ss: int,
           light: wp.vec3, key: wp.vec3, out: wp.array(dtype=wp.vec3), out_cov: wp.array(dtype=float)):
    tid = wp.tid()
    px = tid % size
    py = tid // size
    V = -dirv
    ex = wp.normalize(du)
    ey = -wp.normalize(dv)
    inv = 1.0 / float(ss)
    acc = wp.vec3(0.0)
    hits = float(0.0)
    one = wp.vec3(1.0, 1.0, 1.0)
    f0s = ((IOR - 1.0) / (IOR + 1.0)) * ((IOR - 1.0) / (IOR + 1.0))
    f0 = one * f0s
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
            # ray differentials (lookdev.k_look's): the normal's change over one pixel -> three's geometry roughness
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
            ax_ = (g11 * wp.dot(e0, dpx) - g01 * wp.dot(e1, dpx)) * idet
            bx_ = (g00 * wp.dot(e1, dpx) - g01 * wp.dot(e0, dpx)) * idet
            ay_ = (g11 * wp.dot(e0, dpy) - g01 * wp.dot(e1, dpy)) * idet
            by_ = (g00 * wp.dot(e1, dpy) - g01 * wp.dot(e0, dpy)) * idet
            m0 = vn[i0] - vn[i2]
            m1 = vn[i1] - vn[i2]
            dnx = m0 * ax_ + m1 * bx_
            dny = m0 * ay_ + m1 * by_
            dnx = (dnx - n * wp.dot(n, dnx)) / li
            dny = (dny - n * wp.dot(n, dny)) / li
            geo_r = wp.max(wp.max(wp.max(wp.abs(wp.dot(dnx, ex)), wp.abs(wp.dot(dny, ex))),
                                  wp.max(wp.abs(wp.dot(dnx, ey)), wp.abs(wp.dot(dny, ey)))),
                           wp.max(wp.abs(wp.dot(dnx, V)), wp.abs(wp.dot(dny, V))))
            if wp.dot(n, dirv) > 0.0:
                n = -n
            pg = clamp4(pig[i0] * w0 + pig[i1] * w1 + pig[i2] * w2)
            sf = clamp4(surf[i0] * w0 + surf[i1] * w1 + surf[i2] * w2)
            ax4 = clamp4(aux[i0] * w0 + aux[i1] * w1 + aux[i2] * w2)
            # pigments -> the albedo LUT
            fm = mel0 * wp.pow(2.0, (pg[0] - 0.5) * LOG_RANGE)
            fb = blood0 * wp.pow(2.0, (pg[1] - 0.5) * LOG_RANGE)
            um = wp.sqrt(wp.clamp(fm / MEL_MAX, 0.0, 1.0))
            vb = wp.sqrt(wp.clamp(fb / BLOOD_MAX, 0.0, 1.0))
            alb = lut2(alb_t, 64, 64, um, vb)
            # roughness: the zone's, wet, the micro relief's variance (faded relief at this footprint), spec AA
            wet = wp.max(wet_u, sf[3] * 0.6)
            rz = sf[2] * (1.0 - wet) + 0.12 * wet
            var = pg[3] * pores_u * MICRO_VAR
            var = var + wp.min((wp.dot(dnx, dnx) + wp.dot(dny, dny)) * 2.0 * SAA_SIGMA2, SAA_KAPPA)
            rm = wp.clamp(wp.pow(rz * rz * rz * rz + var, 0.25), 0.05, 1.0)
            r = wp.min(wp.max(rm, 0.0525) + geo_r, 1.0)
            # the key: pre-integrated diffuse (one normal: no micro relief at this footprint), dual-lobe GGX
            tissue = ax4[1] * TISSUE_MAX
            curv = wp.clamp(sf[0] * wp.clamp(tissue / TISSUE_REF, 0.4, 1.4), 0.0, 1.0)
            ndl_h = wp.dot(n, light) * 0.5 + 0.5
            D = lut2(pre_t, 64, 64, ndl_h, curv)
            diff_d = wp.cw_mul(wp.cw_mul(key, D), alb) * LD.INV_PI
            ndl = wp.clamp(wp.dot(n, light), 0.0, 1.0)
            r0 = wp.clamp(r * LOBE0, 0.045, 1.0)
            r1 = wp.clamp(r * LOBE1, 0.045, 1.0)
            spec = LD.brdf_ggx(n, V, light, f0, 1.0, r0) * LOBE_MIX + LD.brdf_ggx(n, V, light, f0, 1.0, r1) * \
                (1.0 - LOBE_MIX)
            spec_d = wp.cw_mul(key * ndl, spec)
            # the transmission (unshadowed: the parity view)
            E = lut2(tr_t, 64, 2, um, 0.25)
            kk = lut2(tr_t, 64, 2, vb, 0.75)
            thick = sf[1] * THICK_MAX
            T = wp.cw_mul(wp.cw_mul(E, E), wp.vec3(wp.exp(-kk[0] * thick), wp.exp(-kk[1] * thick),
                                                     wp.exp(-kk[2] * thick)))
            bk = wp.clamp(-wp.dot(n, light) * 0.5 + 0.5, 0.0, 1.0)
            bk = bk * bk
            fw = wp.clamp(wp.dot(V, -wp.normalize(light + n * 0.2)), 0.0, 1.0)
            fw = fw * fw * fw * fw
            trans = wp.cw_mul(key, T) * (bk * LD.INV_PI + fw * TRANS_FWD)
            # the environment (lookdev.shade's, dielectric: metalness 0, F90 1)
            ao = ax4[0]
            ndv = wp.clamp(wp.dot(n, V), 0.0, 1.0)
            fab = LD.dfg_at(dfg, r, ndv)
            ems = 1.0 - fab[0] - fab[1]
            fss = f0 * fab[0] + one * fab[1]
            fav = f0 + (one - f0) * 0.047619
            mul = wp.cw_div(wp.cw_mul(fss, fav), one - fav * ems) * ems
            e_irr = LD.env_irr_at(env_irr, n_mu, n[1])
            R = n * (2.0 * wp.dot(V, n)) - V
            r4 = r * r * r * r
            R = wp.normalize(R * (1.0 - r4) + n * r4)
            rad = LD.env_rad_at(env_rad, n_mu, n_r, R[1], r)
            diff_e = wp.cw_mul(wp.cw_mul(alb, one - fss - mul), e_irr) * ao
            spec_e = (wp.cw_mul(rad, fss) + wp.cw_mul(mul, e_irr)) * LD.spec_occlusion(ndv, ao, r)
            acc = acc + diff_d + spec_d + trans + diff_e + spec_e
    w = 1.0 / float(ss * ss)
    out[tid] = acc * w
    out_cov[tid] = hits * w


def lut_device(T):
    """the packs (human_skin_lut.read_packs) as device vec3 arrays of their float16 values"""
    return [wp.array(np.ascontiguousarray(T[k][..., :3].reshape(-1, 3).astype(np.float32)), dtype=wp.vec3)
            for k in ('albedo', 'trans', 'preint')]


def render_skin(V, F, N, pig, surf, aux, U, T, out_png=None, view='front', size=1024, ss=2, center=None, span=None,
                light=None, key=3.2, env=None, tone='agx', exposure=1.0, bg=LD.BG):
    """V in the units the channels' thickness assumes (metres, as the glb), the skin's channels per vertex (vec4 each);
    U: dict(melanin, blood, wet, pores); T: the LUT packs; light: the direction toward the key (world), else lookdev's
    default mix for the view. Returns the display image (uint8) and the linear radiance + coverage"""
    from ..render import basis
    V = np.asarray(V, np.float32)
    F = np.asarray(F, np.int32)
    right, upv, cam = basis(view)
    P = V[np.unique(F)]
    if center is None:
        X, Y = P @ right, P @ upv
        sp = max(X.max() - X.min(), Y.max() - Y.min()) * 1.06
        cx, cy = (X.max() + X.min()) / 2, (Y.max() + Y.min()) / 2
    else:
        c = np.asarray(center, np.float64)
        cx, cy, sp = float(c @ right), float(c @ upv), float(span)
    pix = sp / size
    far = float((P @ cam).max()) + 1.0
    origin0 = right * (cx - sp / 2) + upv * (cy + sp / 2) + cam * far
    if light is None:
        light = cam * 0.45 + upv * 0.75 + right * 0.45
    light = np.asarray(light, np.float64)
    light /= np.linalg.norm(light)
    pts = wp.array(V, dtype=wp.vec3)
    mesh = wp.Mesh(points=pts, indices=wp.array(F.ravel(), dtype=wp.int32))
    alb_t, tr_t, pre_t = lut_device(T)
    env_dev = LD._env_device(env)
    n = size * size
    out, cov, disp = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=float), wp.zeros(n, dtype=wp.vec3)
    key3 = LD._rgb(key)
    wp.launch(k_skin, dim=n, inputs=[mesh.id, pts, wp.array(F.ravel(), dtype=wp.int32),
                                     wp.array(np.asarray(N, np.float32), dtype=wp.vec3),
                                     wp.array(np.asarray(pig, np.float32), dtype=wp.vec4),
                                     wp.array(np.asarray(surf, np.float32), dtype=wp.vec4),
                                     wp.array(np.asarray(aux, np.float32), dtype=wp.vec4), alb_t, tr_t, pre_t,
                                     LD._dfg_device()] + env_dev +
              [float(U['melanin']), float(U['blood']), float(U.get('wet', 0.0)), float(U.get('pores', 1.0)),
               wp.vec3(*origin0), wp.vec3(*(right * pix)), wp.vec3(*(-upv * pix)), wp.vec3(*(-cam)), size, ss,
               wp.vec3(*light), wp.vec3(*key3), out, cov])
    tone_i, agx_m = LD.TONES.index(tone), LD._agx_mats()
    bg3 = np.asarray(bg, np.float64) / 255.0
    wp.launch(LD.k_display, dim=n, inputs=[out, cov, tone_i, float(exposure)] + agx_m +
              [float(LD._AGX_EV[0]), float(LD._AGX_EV[1]), wp.vec3(*bg3), disp])
    img = (disp.numpy().reshape(size, size, 3) * 255.0 + 0.5).astype(np.uint8)
    if out_png:
        Image.fromarray(img).save(out_png)
    return img, out.numpy().reshape(size, size, 3), cov.numpy().reshape(size, size), dict(cx=cx, cy=cy, span=sp,
                                                                                          light=light.tolist())


# ------------------------------------------------------------------------------------ the textured twin (H3, 10-30)
TOKSVIG_DEAD = 0.0035                   # human_skin.js K.TOKSVIG_DEAD
DIFF_NORMAL = (0.10, 0.20, 0.33)        # human_skin.js K.DIFF_NORMAL (the kernel reads the three scalars below; H3's
#                                         (0.55, 0.80, 0.92) until the H3b merge, 10-31: the forge's derived blend)
DN_R, DN_G, DN_B = DIFF_NORMAL
ANISO = 16                              # human_skin.js K.ANISOTROPY
# (the H3b integrator, 10-31) the terms the H3b material builder added to the engine's textured path, one copy each side
# (engine_test/human_skin.js, merged 10-31), so the parity view compares the shader that ships:
AGREE_LO, AGREE_HI = 0.25, 0.75         # SkinLightingModel's guard: each channel's normal blend fades to the detail normal
#                                         where the macro and detail normals disagree (smoothstep of nG . nD)
AO_BOUNCE = 1.0                         # K.AO_BOUNCE: Jimenez et al. 2016's multi-bounce AO per channel on the indirect
#                                         diffuse (1 on, 0 three's plain AO multiply)
WET_AO_FLOOR = 0.40                     # K.WET_AO_FLOOR: the skin's aoNode = max(AO, wet x this)
MICRO_SHADOW = 1.0                      # K.MICRO_SHADOW: saturate(|Nmacro.L| + 2 a^2 - 1) on the direct diffuse and
#                                         specular, a = smoothstep(MICRO_SHADOW_AO, the AO read MICRO_SHADOW_BIAS mips
#                                         coarser, the wet floor in)
MICRO_SHADOW_AO_LO, MICRO_SHADOW_AO_HI = 0.10, 0.60
MICRO_SHADOW_BIAS, MICRO_SHADOW_LOD_MIN = 1.0, 2.5   # its AO read at max(the pixel's isotropic level + BIAS, LOD_MIN)


@wp.func
def ao_bounce(rho: float, x: float):
    """Jimenez et al. 2016's multi-bounce AO for one channel of albedo rho (human_skin.js ambientOcclusion)"""
    a = rho * 2.0404 - 0.3324
    b = rho * -4.7951 + 0.6417
    c = rho * 2.7552 + 0.6903
    return wp.max(((a * x + b) * x + c) * x, x)
MAP_KEYS = ('N', 'Nmacro', 'PIGMENT', 'SURFACE', 'AUX')


def cpu_mips(img):
    """the engine's mip chain of a glb texture (eidoverse/render_scene.mjs _buildCpuMips): a 2 x 2 box per channel on
    the 8-bit codes, (a + b + c + d) >> 2, edge texels clamped, down to 1 x 1"""
    levels = [np.ascontiguousarray(img, np.uint8)]
    a = img.astype(np.int32)
    while a.shape[0] > 1 or a.shape[1] > 1:
        h, w = a.shape[:2]
        dh, dw = max(1, h >> 1), max(1, w >> 1)
        y0 = np.minimum(np.arange(dh) * 2, h - 1)
        y1 = np.minimum(np.arange(dh) * 2 + 1, h - 1)
        x0 = np.minimum(np.arange(dw) * 2, w - 1)
        x1 = np.minimum(np.arange(dw) * 2 + 1, w - 1)
        a = (a[y0][:, x0] + a[y0][:, x1] + a[y1][:, x0] + a[y1][:, x1]) >> 2
        levels.append(np.ascontiguousarray(a.astype(np.uint8)))
    return levels


@wp.func
def tx_texel(tex: wp.array(dtype=wp.uint8), off: int, w: int, x: int, y: int):
    k = off + 3 * (y * w + x)
    return wp.vec3(float(tex[k]), float(tex[k + 1]), float(tex[k + 2])) * (1.0 / 255.0)


@wp.func
def tx_bil(tex: wp.array(dtype=wp.uint8), off: int, w: int, h: int, u: float, v: float):
    """bilinear (texel centres, clamp to edge) at the forge's uv: v up the image (row = (1 - v) h), as glTF's v' = 1 - v
    reads an image whose row 0 is the top"""
    fx = wp.clamp(u * float(w) - 0.5, 0.0, float(w - 1))
    fy = wp.clamp((1.0 - v) * float(h) - 0.5, 0.0, float(h - 1))
    x0 = int(wp.floor(fx))
    y0 = int(wp.floor(fy))
    x1 = wp.min(x0 + 1, w - 1)
    y1 = wp.min(y0 + 1, h - 1)
    ax = fx - float(x0)
    ay = fy - float(y0)
    a = tx_texel(tex, off, w, x0, y0) * (1.0 - ax) + tx_texel(tex, off, w, x1, y0) * ax
    b = tx_texel(tex, off, w, x0, y1) * (1.0 - ax) + tx_texel(tex, off, w, x1, y1) * ax
    return a * (1.0 - ay) + b * ay


@wp.func
def tx_tri(tex: wp.array(dtype=wp.uint8), loff: wp.array2d(dtype=wp.int32), lw: wp.array2d(dtype=wp.int32),
           lh: wp.array2d(dtype=wp.int32), nlev: wp.array(dtype=wp.int32), t: int, u: float, v: float, lod: float):
    l = wp.clamp(lod, 0.0, float(nlev[t] - 1))
    l0 = int(wp.floor(l))
    l1 = wp.min(l0 + 1, nlev[t] - 1)
    f = l - float(l0)
    a = tx_bil(tex, loff[t, l0], lw[t, l0], lh[t, l0], u, v)
    b = tx_bil(tex, loff[t, l1], lw[t, l1], lh[t, l1], u, v)
    return a * (1.0 - f) + b * f


@wp.func
def tx_aniso(tex: wp.array(dtype=wp.uint8), loff: wp.array2d(dtype=wp.int32), lw: wp.array2d(dtype=wp.int32),
             lh: wp.array2d(dtype=wp.int32), nlev: wp.array(dtype=wp.int32), t: int, u: float, v: float,
             dudx: float, dvdx: float, dudy: float, dvdy: float):
    """anisotropic trilinear: the pixel footprint's axes in level-0 texels; n = min(ceil(major / minor), ANISO) taps
    along the major axis at lod log2(major / n)"""
    W = float(lw[t, 0])
    H = float(lh[t, 0])
    lx = wp.sqrt(dudx * dudx * W * W + dvdx * dvdx * H * H)
    ly = wp.sqrt(dudy * dudy * W * W + dvdy * dvdy * H * H)
    major = wp.max(lx, ly)
    minor = wp.max(wp.min(lx, ly), 1.0e-6)
    n = wp.max(1, wp.min(int(wp.ceil(major / minor)), ANISO))
    lod = wp.log2(wp.max(major / float(n), 1.0e-6))
    du = dudx
    dv = dvdx
    if ly > lx:
        du = dudy
        dv = dvdy
    acc = wp.vec3(0.0)
    for k in range(n):
        s = (float(k) + 0.5) / float(n) - 0.5
        acc = acc + tx_tri(tex, loff, lw, lh, nlev, t, u + s * du, v + s * dv, lod)
    return acc / float(n)


@wp.func
def tx_level(tex: wp.array(dtype=wp.uint8), loff: wp.array2d(dtype=wp.int32), lw: wp.array2d(dtype=wp.int32),
             lh: wp.array2d(dtype=wp.int32), nlev: wp.array(dtype=wp.int32), t: int, u: float, v: float,
             dudx: float, dvdx: float, dudy: float, dvdy: float, bias: float, lod_min: float):
    """(the H3b integrator) one trilinear read at an explicit level, as the shader's texture(...).level(): the pixel's
    isotropic level (the footprint's longer axis in level-0 texels) + bias, never finer than lod_min"""
    W = float(lw[t, 0])
    H = float(lh[t, 0])
    lx = wp.sqrt(dudx * dudx * W * W + dvdx * dvdx * H * H)
    ly = wp.sqrt(dudy * dudy * W * W + dvdy * dvdy * H * H)
    lod = wp.max(wp.log2(wp.max(wp.max(lx, ly), 1.0e-6)) + bias, lod_min)
    return tx_tri(tex, loff, lw, lh, nlev, t, u, v, lod)


@wp.kernel
def k_skin_tex(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), tri: wp.array(dtype=wp.int32),
               vn: wp.array(dtype=wp.vec3), vt: wp.array(dtype=wp.vec4), vuv: wp.array(dtype=wp.vec2),
               tset: wp.array(dtype=wp.int32), tex: wp.array(dtype=wp.uint8), loff: wp.array2d(dtype=wp.int32),
               lw: wp.array2d(dtype=wp.int32), lh: wp.array2d(dtype=wp.int32), nlev: wp.array(dtype=wp.int32),
               alb_t: wp.array(dtype=wp.vec3), tr_t: wp.array(dtype=wp.vec3), pre_t: wp.array(dtype=wp.vec3),
               dfg: wp.array(dtype=wp.vec2), env_rad: wp.array(dtype=wp.vec3), env_irr: wp.array(dtype=wp.vec3),
               n_mu: int, n_r: int, mel0: float, blood0: float, wet_u: float, pores_u: float, origin0: wp.vec3,
               du: wp.vec3, dv: wp.vec3, dirv: wp.vec3, size: int, ss: int, light: wp.vec3, key: wp.vec3,
               out: wp.array(dtype=wp.vec3), out_cov: wp.array(dtype=float)):
    tid = wp.tid()
    px = tid % size
    py = tid // size
    V = -dirv
    ex = wp.normalize(du)
    ey = -wp.normalize(dv)
    inv = 1.0 / float(ss)
    acc = wp.vec3(0.0)
    hits = float(0.0)
    one = wp.vec3(1.0, 1.0, 1.0)
    f0s = ((IOR - 1.0) / (IOR + 1.0)) * ((IOR - 1.0) / (IOR + 1.0))
    f0 = one * f0s
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
            ngeo = ni / li
            # ray differentials (render_skin's): the barycentrics' change over one pixel
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
            ax_ = (g11 * wp.dot(e0, dpx) - g01 * wp.dot(e1, dpx)) * idet
            bx_ = (g00 * wp.dot(e1, dpx) - g01 * wp.dot(e0, dpx)) * idet
            ay_ = (g11 * wp.dot(e0, dpy) - g01 * wp.dot(e1, dpy)) * idet
            by_ = (g00 * wp.dot(e1, dpy) - g01 * wp.dot(e0, dpy)) * idet
            m0 = vn[i0] - vn[i2]
            m1 = vn[i1] - vn[i2]
            dnx = m0 * ax_ + m1 * bx_
            dny = m0 * ay_ + m1 * by_
            dnx = (dnx - ngeo * wp.dot(ngeo, dnx)) / li
            dny = (dny - ngeo * wp.dot(ngeo, dny)) / li
            geo_r = wp.max(wp.max(wp.max(wp.abs(wp.dot(dnx, ex)), wp.abs(wp.dot(dny, ex))),
                                  wp.max(wp.abs(wp.dot(dnx, ey)), wp.abs(wp.dot(dny, ey)))),
                           wp.max(wp.abs(wp.dot(dnx, V)), wp.abs(wp.dot(dny, V))))
            # the UV and its change over the pixel; the five maps, as the engine filters them
            uv = vuv[i0] * w0 + vuv[i1] * w1 + vuv[i2] * w2
            q0 = vuv[i0] - vuv[i2]
            q1 = vuv[i1] - vuv[i2]
            dudx = q0[0] * ax_ + q1[0] * bx_
            dvdx = q0[1] * ax_ + q1[1] * bx_
            dudy = q0[0] * ay_ + q1[0] * by_
            dvdy = q0[1] * ay_ + q1[1] * by_
            tb = tset[f] * 5
            cN = tx_aniso(tex, loff, lw, lh, nlev, tb, uv[0], uv[1], dudx, dvdx, dudy, dvdy)
            cM = tx_aniso(tex, loff, lw, lh, nlev, tb + 1, uv[0], uv[1], dudx, dvdx, dudy, dvdy)
            pg = tx_aniso(tex, loff, lw, lh, nlev, tb + 2, uv[0], uv[1], dudx, dvdx, dudy, dvdy)
            sf = tx_aniso(tex, loff, lw, lh, nlev, tb + 3, uv[0], uv[1], dudx, dvdx, dudy, dvdy)
            xa = tx_aniso(tex, loff, lw, lh, nlev, tb + 4, uv[0], uv[1], dudx, dvdx, dudy, dvdy)
            M3 = MT.engine_tbn(vn[i0], vn[i1], vn[i2], vt[i0], vt[i1], vt[i2], w0, w1, w2)
            tN = cN * 2.0 - one
            rl = wp.min(wp.length(tN) + TOKSVIG_DEAD, 1.0)
            nD = wp.normalize(M3 @ tN)
            nG = wp.normalize(M3 @ (cM * 2.0 - one))
            # pigments -> the albedo LUT
            fm = mel0 * wp.pow(2.0, (pg[0] - 0.5) * LOG_RANGE)
            fb = blood0 * wp.pow(2.0, (pg[1] - 0.5) * LOG_RANGE)
            um = wp.sqrt(wp.clamp(fm / MEL_MAX, 0.0, 1.0))
            vb = wp.sqrt(wp.clamp(fb / BLOOD_MAX, 0.0, 1.0))
            alb = lut2(alb_t, 64, 64, um, vb)
            # roughness: the zone's (the mip-0 variance folded in at pack time), wet, Toksvig at this mip, the runtime
            # relief's faded variance, the geometric spec AA
            wet = wp.max(wet_u, xa[1] * 0.6)
            rz = sf[2] * (1.0 - wet) + 0.12 * wet
            r2 = rl * rl
            var = wp.min((1.0 - r2) * 2.0 / wp.max(rl * 3.0 - r2 * rl, 1.0e-4), 0.5)
            var = var + xa[2] * pores_u * MICRO_VAR
            var = var + wp.min((wp.dot(dnx, dnx) + wp.dot(dny, dny)) * 2.0 * SAA_SIGMA2, SAA_KAPPA)
            rm = wp.clamp(wp.pow(rz * rz * rz * rz + var, 0.25), 0.05, 1.0)
            r = wp.min(wp.max(rm, 0.0525) + geo_r, 1.0)
            # the key: each channel's pre-integrated diffuse at its own normal, the dual-lobe GGX on the detail normal
            curv = wp.clamp(sf[0], 0.0, 1.0)
            # (H3b integrator) the engine's guard: mix(nD, mix(nG, nD, w), agree), normalised
            agr = wp.smoothstep(AGREE_LO, AGREE_HI, wp.dot(nG, nD))
            nr = wp.normalize(nD * (1.0 - agr) + (nG * (1.0 - DN_R) + nD * DN_R) * agr)
            ng_ = wp.normalize(nD * (1.0 - agr) + (nG * (1.0 - DN_G) + nD * DN_G) * agr)
            nb = wp.normalize(nD * (1.0 - agr) + (nG * (1.0 - DN_B) + nD * DN_B) * agr)
            Dr = lut2(pre_t, 64, 64, wp.dot(nr, light) * 0.5 + 0.5, curv)
            Dg = lut2(pre_t, 64, 64, wp.dot(ng_, light) * 0.5 + 0.5, curv)
            Db = lut2(pre_t, 64, 64, wp.dot(nb, light) * 0.5 + 0.5, curv)
            D = wp.vec3(Dr[0], Dg[1], Db[2])
            diff_d = wp.cw_mul(wp.cw_mul(key, D), alb) * LD.INV_PI
            ndl = wp.clamp(wp.dot(nD, light), 0.0, 1.0)
            r0 = wp.clamp(r * LOBE0, 0.045, 1.0)
            r1 = wp.clamp(r * LOBE1, 0.045, 1.0)
            spec = LD.brdf_ggx(nD, V, light, f0, 1.0, r0) * LOBE_MIX + LD.brdf_ggx(nD, V, light, f0, 1.0, r1) * \
                (1.0 - LOBE_MIX)
            spec_d = wp.cw_mul(key * ndl, spec)
            # (H3b integrator) the skin's aoNode (the wet tissue's floor in) and the micro-shadow on the direct light
            ao = wp.max(xa[0], xa[1] * WET_AO_FLOOR)
            if MICRO_SHADOW > 0.5:
                xb = tx_level(tex, loff, lw, lh, nlev, tb + 4, uv[0], uv[1], dudx, dvdx, dudy, dvdy, MICRO_SHADOW_BIAS,
                              MICRO_SHADOW_LOD_MIN)
                aom = wp.smoothstep(MICRO_SHADOW_AO_LO, MICRO_SHADOW_AO_HI, wp.max(xb[0], xa[1] * WET_AO_FLOOR))
                msh = wp.clamp(wp.abs(wp.dot(nG, light)) + 2.0 * aom * aom - 1.0, 0.0, 1.0)
                diff_d = diff_d * msh
                spec_d = spec_d * msh
            # the transmission (unshadowed: the parity view), on the macro normal
            E = lut2(tr_t, 64, 2, um, 0.25)
            kk = lut2(tr_t, 64, 2, vb, 0.75)
            thick = sf[1] * THICK_MAX
            T = wp.cw_mul(wp.cw_mul(E, E), wp.vec3(wp.exp(-kk[0] * thick), wp.exp(-kk[1] * thick),
                                                     wp.exp(-kk[2] * thick)))
            bk = wp.clamp(-wp.dot(nG, light) * 0.5 + 0.5, 0.0, 1.0)
            bk = bk * bk
            fw = wp.clamp(wp.dot(V, -wp.normalize(light + nG * 0.2)), 0.0, 1.0)
            fw = fw * fw * fw * fw
            trans = wp.cw_mul(key, T) * (bk * LD.INV_PI + fw * TRANS_FWD)
            # the environment on the detail normal, with the AO (the aoNode above)
            ndv = wp.clamp(wp.dot(nD, V), 0.0, 1.0)
            fab = LD.dfg_at(dfg, r, ndv)
            ems = 1.0 - fab[0] - fab[1]
            fss = f0 * fab[0] + one * fab[1]
            fav = f0 + (one - f0) * 0.047619
            mul = wp.cw_div(wp.cw_mul(fss, fav), one - fav * ems) * ems
            e_irr = LD.env_irr_at(env_irr, n_mu, nD[1])
            Rr = nD * (2.0 * wp.dot(V, nD)) - V
            r4 = r * r * r * r
            Rr = wp.normalize(Rr * (1.0 - r4) + nD * r4)
            rad = LD.env_rad_at(env_rad, n_mu, n_r, Rr[1], r)
            diff_e = wp.cw_mul(wp.cw_mul(alb, one - fss - mul), e_irr)
            if AO_BOUNCE > 0.5:
                # (H3b integrator) the engine's multi-bounce AO per channel (SkinLightingModel.ambientOcclusion)
                diff_e = wp.cw_mul(diff_e, wp.vec3(ao_bounce(alb[0], ao), ao_bounce(alb[1], ao), ao_bounce(alb[2], ao)))
            else:
                diff_e = diff_e * ao
            spec_e = (wp.cw_mul(rad, fss) + wp.cw_mul(mul, e_irr)) * LD.spec_occlusion(ndv, ao, r)
            acc = acc + diff_d + spec_d + trans + diff_e + spec_e
    w = 1.0 / float(ss * ss)
    out[tid] = acc * w
    out_cov[tid] = hits * w


def render_skin_tex(sets, U, T, out_png=None, view='front', size=1024, ss=2, center=None, span=None, light=None,
                    key=3.2, env=None, tone='agx', exposure=1.0, bg=LD.BG):
    """sets: [dict(V (m), F, N, TAN (x, y, z, w), UV (the forge's: v up), maps={N, Nmacro, PIGMENT, SURFACE, AUX:
    uint8 (h, w, 3)})], the glb's own arrays and decoded PNGs; U: dict(melanin, blood, wet, pores); T: the LUT packs.
    The frame, key and display as render_skin. Returns the display image (uint8), the linear radiance, the coverage"""
    from ..render import basis
    Vs, Fs, Ns, Ts, UVs, sid = [], [], [], [], [], []
    base = 0
    lev_off, lev_w, lev_h, n_lev, chunks = [], [], [], [], []
    off = 0
    for k, S in enumerate(sets):
        Vs.append(np.asarray(S['V'], np.float32))
        Fs.append(np.asarray(S['F'], np.int64) + base)
        Ns.append(np.asarray(S['N'], np.float32))
        Ts.append(np.asarray(S['TAN'], np.float32))
        UVs.append(np.asarray(S['UV'], np.float32))
        sid.append(np.full(len(S['F']), k, np.int32))
        base += len(S['V'])
        for key_ in MAP_KEYS:
            lv = cpu_mips(S['maps'][key_])
            lev_off.append([0] * 16)
            lev_w.append([1] * 16)
            lev_h.append([1] * 16)
            for li, a in enumerate(lv[:16]):
                lev_off[-1][li] = off
                lev_w[-1][li] = a.shape[1]
                lev_h[-1][li] = a.shape[0]
                chunks.append(a.reshape(-1))
                off += a.size
            n_lev.append(min(len(lv), 16))
    V = np.concatenate(Vs)
    F = np.concatenate(Fs).astype(np.int32)
    right, upv, cam = basis(view)
    P = V[np.unique(F)]
    if center is None:
        X, Y = P @ right, P @ upv
        sp = max(X.max() - X.min(), Y.max() - Y.min()) * 1.06
        cx, cy = (X.max() + X.min()) / 2, (Y.max() + Y.min()) / 2
    else:
        c = np.asarray(center, np.float64)
        cx, cy, sp = float(c @ right), float(c @ upv), float(span)
    pix = sp / size
    far = float((P @ cam).max()) + 1.0
    origin0 = right * (cx - sp / 2) + upv * (cy + sp / 2) + cam * far
    if light is None:
        light = cam * 0.45 + upv * 0.75 + right * 0.45
    light = np.asarray(light, np.float64)
    light /= np.linalg.norm(light)
    pts = wp.array(V, dtype=wp.vec3)
    mesh = wp.Mesh(points=pts, indices=wp.array(F.ravel(), dtype=wp.int32))
    alb_t, tr_t, pre_t = lut_device(T)
    env_dev = LD._env_device(env)
    n = size * size
    out, cov, disp = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=float), wp.zeros(n, dtype=wp.vec3)
    key3 = LD._rgb(key)
    wp.launch(k_skin_tex, dim=n, inputs=[mesh.id, pts, wp.array(F.ravel(), dtype=wp.int32),
                                         wp.array(np.concatenate(Ns), dtype=wp.vec3),
                                         wp.array(np.concatenate(Ts), dtype=wp.vec4),
                                         wp.array(np.concatenate(UVs), dtype=wp.vec2),
                                         wp.array(np.concatenate(sid), dtype=wp.int32),
                                         wp.array(np.concatenate(chunks), dtype=wp.uint8),
                                         wp.array(np.asarray(lev_off, np.int32), dtype=wp.int32),
                                         wp.array(np.asarray(lev_w, np.int32), dtype=wp.int32),
                                         wp.array(np.asarray(lev_h, np.int32), dtype=wp.int32),
                                         wp.array(np.asarray(n_lev, np.int32), dtype=wp.int32),
                                         alb_t, tr_t, pre_t, LD._dfg_device()] + env_dev +
              [float(U['melanin']), float(U['blood']), float(U.get('wet', 0.0)), float(U.get('pores', 1.0)),
               wp.vec3(*origin0), wp.vec3(*(right * pix)), wp.vec3(*(-upv * pix)), wp.vec3(*(-cam)), size, ss,
               wp.vec3(*light), wp.vec3(*key3), out, cov])
    tone_i, agx_m = LD.TONES.index(tone), LD._agx_mats()
    bg3 = np.asarray(bg, np.float64) / 255.0
    wp.launch(LD.k_display, dim=n, inputs=[out, cov, tone_i, float(exposure)] + agx_m +
              [float(LD._AGX_EV[0]), float(LD._AGX_EV[1]), wp.vec3(*bg3), disp])
    img = (disp.numpy().reshape(size, size, 3) * 255.0 + 0.5).astype(np.uint8)
    if out_png:
        Image.fromarray(img).save(out_png)
    return img, out.numpy().reshape(size, size, 3), cov.numpy().reshape(size, size), dict(cx=cx, cy=cy, span=sp,
                                                                                          light=light.tolist())
