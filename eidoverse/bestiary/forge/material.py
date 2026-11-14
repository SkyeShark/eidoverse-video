"""The MATERIAL PASS plumbing (Warp, GPU): per texel of a texture set, the low under each sub-sample (point, the
engine's tangent frame, the anatomical attributes), the bake's drivers at the texel, and a texture-tier height composed
into the baked normal through the low's own UV derivatives (no Sobel in texture space: islands have different texel
densities and gutters, and the derivative method has neither problem).

Species recipes (species/*_skin.py) are kernels built on these funcs; they run in seconds from the saved drivers, so
the look iterates without re-baking the SDF.
"""
import numpy as np
import warp as wp

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile


@wp.func
def engine_tbn(n0: wp.vec3, n1: wp.vec3, n2: wp.vec3, t0: wp.vec4, t1: wp.vec4, t2: wp.vec4, b0: float, b1: float,
               b2: float):
    """THE ENGINE'S TANGENT FRAME at barycentrics (b0, b1, b2) of a triangle whose corners carry the glb's NORMAL n and
    TANGENT t (xyz, w the handedness): three r184's TSL normal-map path in the copy the renderer loads
    (node_modules/.deno/three@0.184.0/node_modules/three/build/three.webgpu.js). N: each corner's normal normalised
    (transformNormalToView), lerped, normalised (normalViewGeometry). B: cross(N, T) * w of the vertex stage's
    normalised N and T (getBitangent: the varying v_bitangentView), lerped, normalised (bitangentView). T: THIS
    NORMALISES EACH CORNER'S TANGENT BEFORE THE LERP, where three r184 lerps the UNNORMALISED view-space tangent
    (tangentView: modelViewMatrix * TANGENT.xyz into the varying v_tangentView, normalised only per fragment). The two
    are identical (to float rounding) for the unit TANGENTs the forge always writes (bake.low_frames normalises them in
    float64; glTF asks a unit TANGENT), under a model-view that scales every direction alike. A non-unit TANGENT would
    differ: three weights each corner's tangent by its length in the lerp, this does not (on a skinned mesh three
    normalises it per vertex first, skinning's transformDirection, and the two agree again). Returns the TBNViewMatrix
    as a mat33, columns T, B, N: the shader decodes normalize(M @ (tex * 2 - 1)) (NormalMapNode, no normalScale), the
    bake encodes the inverse (tbn_encode). The ONE copy of this math: bake.k_bake, low_at (every material pass),
    lookdev.k_look and the mech limb's own bake call it, so the frame a map is written in cannot drift from the one it
    is read in"""
    m0 = wp.normalize(n0)
    m1 = wp.normalize(n1)
    m2 = wp.normalize(n2)
    a0 = wp.normalize(wp.vec3(t0[0], t0[1], t0[2]))
    a1 = wp.normalize(wp.vec3(t1[0], t1[1], t1[2]))
    a2 = wp.normalize(wp.vec3(t2[0], t2[1], t2[2]))
    n = wp.normalize(m0 * b0 + m1 * b1 + m2 * b2)
    t = wp.normalize(a0 * b0 + a1 * b1 + a2 * b2)
    b = wp.normalize(wp.cross(m0, a0) * t0[3] * b0 + wp.cross(m1, a1) * t1[3] * b1 + wp.cross(m2, a2) * t2[3] * b2)
    return wp.mat33(t[0], b[0], n[0], t[1], b[1], n[1], t[2], b[2], n[2])


@wp.func
def tbn_encode(fr: wp.mat33, n: wp.vec3):
    """a world normal in the frame engine_tbn returns: the matched inverse of the shader's normalize(M @ tn) (the
    interpolated frame is not orthonormal), normalised; +z where the frame is degenerate"""
    if wp.abs(wp.determinant(fr)) < 1.0e-9:
        return wp.vec3(0.0, 0.0, 1.0)
    return wp.normalize(wp.inverse(fr) @ n)


@wp.struct
class Low:
    ok: int
    p: wp.vec3
    n: wp.vec3
    t: wp.vec3
    b: wp.vec3
    attr: wp.vec4
    face: int


@wp.func
def low_at(uv_mesh: wp.uint64, x: float, y: float, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
           ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4)):
    """the low under texel-space point (x, y) (texel units, y = v * size): the interpolated point, its normal, tangent
    and bitangent (engine_tbn: the shader's own frame) and attributes"""
    out = Low()
    out.ok = 0
    s = wp.mesh_query_ray(uv_mesh, wp.vec3(x, y, 1.0), wp.vec3(0.0, 0.0, -1.0), 2.0)
    if s.result:
        c0 = 3 * s.face
        u = s.u
        v = s.v
        w = 1.0 - u - v
        out.ok = 1
        out.face = s.face
        out.p = lpos[c0] * u + lpos[c0 + 1] * v + lpos[c0 + 2] * w
        fr = engine_tbn(lnrm[c0], lnrm[c0 + 1], lnrm[c0 + 2], ltan[c0], ltan[c0 + 1], ltan[c0 + 2], u, v, w)
        out.t = wp.vec3(fr[0, 0], fr[1, 0], fr[2, 0])
        out.b = wp.vec3(fr[0, 1], fr[1, 1], fr[2, 1])
        out.n = wp.vec3(fr[0, 2], fr[1, 2], fr[2, 2])
        out.attr = lattr[c0] * u + lattr[c0 + 1] * v + lattr[c0 + 2] * w
    return out


@wp.func
def to_world(lo: Low, tn: wp.vec3):
    """a tangent-space normal to world space exactly as the shader does: mat3(T, B, N) * n, normalised"""
    return wp.normalize(lo.t * tn[0] + lo.b * tn[1] + lo.n * tn[2])


@wp.func
def to_tangent(lo: Low, n: wp.vec3):
    """the matched inverse of to_world (the interpolated frame is not orthonormal)"""
    t = lo.t
    b = lo.b
    nn = lo.n
    m = wp.mat33(t[0], b[0], nn[0], t[1], b[1], nn[1], t[2], b[2], nn[2])
    if wp.abs(wp.determinant(m)) < 1.0e-9:
        return wp.vec3(0.0, 0.0, 1.0)
    return wp.normalize(wp.inverse(m) @ n)


@wp.func
def surface_grad(p0: wp.vec3, p1: wp.vec3, p2: wp.vec3, h0: float, h1: float, h2: float):
    """the gradient g in the plane of (p1 - p0, p2 - p0) with g . dp_i = dh_i (the height's surface gradient from two
    neighbouring samples)"""
    a = p1 - p0
    b = p2 - p0
    aa = wp.dot(a, a)
    ab = wp.dot(a, b)
    bb = wp.dot(b, b)
    det = aa * bb - ab * ab
    if det < 1.0e-30:
        return wp.vec3(0.0)
    d1 = h1 - h0
    d2 = h2 - h0
    ca = (d1 * bb - d2 * ab) / det
    cb = (d2 * aa - d1 * ab) / det
    return a * ca + b * cb


@wp.func
def srgb1(c: float):
    """one channel sRGB (0..1) -> linear: the EXACT sRGB EOTF (IEC 61966-2-1), as three decodes an SRGBColorSpace
    texture (x^2.2 put the darks ~40 % off at linear 0.01)"""
    if c <= 0.04045:
        return c / 12.92
    return wp.pow((c + 0.055) / 1.055, 2.4)


@wp.func
def srgb(c: wp.vec3):
    """sRGB (0..1) -> linear, exact (srgb1 per channel): a measured sRGB colour constant decoded"""
    return wp.vec3(srgb1(c[0]), srgb1(c[1]), srgb1(c[2]))


# THE HOUSE'S sRGB TRANSFER on the host, the one helper: every albedo the forge encodes for a texture goes through
# srgb_oetf, every sRGB value it decodes through srgb_eotf (three r184 decodes an SRGBColorSpace texture exactly)
def srgb_eotf(s):
    """sRGB (0..1) -> linear, exact (the GPU's decode of an sRGB texture)"""
    s = np.asarray(s, np.float64)
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def srgb_oetf(L):
    """linear -> sRGB (0..1), exact, clamped to [0, 1] first (an albedo encoded for a texture; three's
    outputColorSpace = SRGBColorSpace)"""
    L = np.clip(np.asarray(L, np.float64), 0.0, 1.0)
    return np.where(L <= 0.0031308, 12.92 * L, 1.055 * L ** (1.0 / 2.4) - 0.055)


@wp.func
def mix3(a: wp.vec3, b: wp.vec3, t: float):
    return a + (b - a) * t


@wp.func
def lum(c: wp.vec3):
    """Rec.709 luminance of a linear colour (the reference study's L)"""
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


@wp.func
def lsh(c: wp.vec3, k_l: float, k_s: float):
    """c with its luminance times k_l and its chroma (the departure from the grey of equal luminance) times k_s, its
    hue held: the reference study's rules move L and S, not hue (countershading, cavities richer)"""
    L = wp.max(lum(c), 1.0e-6)
    g = wp.vec3(L, L, L)
    return (g + (c - g) * k_s) * k_l


def corner_arrays(V, F, N, TAN, ATTR):
    """per-corner device arrays of the low (the layout low_at reads)"""
    corner = np.asarray(F, np.int32).ravel()
    return (wp.array(np.asarray(V, np.float32)[corner], dtype=wp.vec3),
            wp.array(np.asarray(N, np.float32)[corner], dtype=wp.vec3),
            wp.array(np.asarray(TAN, np.float32)[corner], dtype=wp.vec4),
            wp.array(np.asarray(ATTR, np.float32)[corner], dtype=wp.vec4))


def uv_bvh(F, UV, size):
    corner = np.asarray(F, np.int32).ravel()
    luv = np.asarray(UV, np.float64)[corner] * size
    return wp.Mesh(points=wp.array(np.column_stack([luv, np.zeros(len(luv))]).astype(np.float32), dtype=wp.vec3),
                   indices=wp.array(np.arange(len(luv), dtype=np.int32), dtype=wp.int32))


def driver_arrays(res):
    """the bake's drivers (image order, rows top-down) back to the kernels' order (row y = v * size), flat"""
    out = {}
    for k, a in res.items():
        a = np.ascontiguousarray(np.asarray(a)[::-1])
        if a.ndim == 3 and a.shape[2] == 4:
            out[k] = wp.array(a.reshape(-1, 4).astype(np.float32), dtype=wp.vec4)
        elif a.dtype.kind in 'iu':
            out[k] = wp.array(a.reshape(-1).astype(np.int32), dtype=wp.int32)
        else:
            out[k] = wp.array(a.reshape(-1).astype(np.float32), dtype=wp.float32)
    return out


def image(arr, size, kind='rgb'):
    """a kernel output (row y = v * size) to an image-order uint8 array"""
    a = np.asarray(arr).reshape(size, size, -1)[::-1]
    return np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8).squeeze()
