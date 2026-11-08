"""GLSL compute through Blender's `gpu` module: the fx family's GPU bake path.

The WebGPU engine's solvers are compute kernels over rgba16float 3D textures, read through linear-filtered
samplers and written with one textureStore per kernel. Blender 5.2 runs the same shape: a compute shader
reads `sampler3D`s (hardware trilinear when the texture's filter_mode is on) and writes `image3D`s. There are
no storage buffers from Python (no GPUStorageBuf), so per-point data (an emitter's vertices) travels in a 2D
float texture read with texelFetch.

Blender inserts a texture-fetch + image-access barrier after every gpu.compute.dispatch, so kernels chain
in submission order like the engine's computeAsync calls.

    ctx = ComputeContext()                  # gpu.init() in background mode
    tex = ctx.texture3d((nx, ny, nz))       # RGBA16F, linear filter, clamp to edge
    k = ctx.kernel(src, samplers=['velA'], images=['velOut'], push=[('FLOAT', 'uDt')], local=(8, 8, 4))
    k.run(groups, samplers={'velA': tex}, images={'velOut': tex2}, uDt=1/120)
    arr = ctx.read(tex)                     # numpy (nz, ny, nx, 4) float32
"""

from __future__ import annotations

import math

import numpy as np

GLSL_SNOISE = r"""
vec4 eido_permute4(vec4 x) { return mod(x * x * 34.0 + x, 289.0); }
/* three.js TSL curlNoise.js `snoise`: Ashima simplex, returning 0.5 + 12*dot(...) */
float eido_snoise(vec3 v) {
  const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.x;
  vec3 x2 = x0 - i2 + C.y;
  vec3 x3 = x0 - D.yyy;
  i = mod(i, 289.0);
  vec4 p = eido_permute4(eido_permute4(eido_permute4(i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  vec3 ns = 0.142857142857 * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = floor(j - 7.0 * x_) * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + (floor(b0) * 2.0 + 1.0).xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + (floor(b1) * 2.0 + 1.0).xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = inversesqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  return 0.5 + 12.0 * dot(m * m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}
/* TSL snoiseVec3, upstream quirk kept: components 1 and 3 scale the INPUT by 2 and subtract 1 */
vec3 eido_snoise_vec3(vec3 x) {
  return vec3(eido_snoise(x * 2.0 - 1.0),
              eido_snoise(vec3(x.y - 19.1, x.z + 33.4, x.x + 47.2)) * 2.0 - 1.0,
              eido_snoise(vec3(x.z + 74.2, x.x - 124.5, x.y + 99.4) * 2.0 - 1.0));
}
"""

GLSL_MX_NOISE = r"""
uint eido_rotl32(uint x, int k) { return (x << uint(k)) | (x >> uint(32 - k)); }
uint eido_bjfinal(uint a, uint b, uint c) {
  c ^= b; c -= eido_rotl32(b, 14);
  a ^= c; a -= eido_rotl32(c, 11);
  b ^= a; b -= eido_rotl32(a, 25);
  c ^= b; c -= eido_rotl32(b, 16);
  a ^= c; a -= eido_rotl32(c, 4);
  b ^= a; b -= eido_rotl32(a, 14);
  c ^= b; c -= eido_rotl32(b, 24);
  return c;
}
uint eido_mx_hash(int x, int y, int z) {
  uint s = 0xdeadbeefu + (3u << 2u) + 13u;
  return eido_bjfinal(s + uint(x), s + uint(y), s + uint(z));
}
float eido_mx_fade(float t) { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }
float eido_mx_grad(uint hash, float x, float y, float z) {
  uint h = hash & 15u;
  float u = h < 8u ? x : y;
  float v = h < 4u ? y : ((h == 12u || h == 14u) ? x : z);
  return ((h & 1u) != 0u ? -u : u) + ((h & 2u) != 0u ? -v : v);
}
/* three's MaterialX mx_noise_float(p) = mx_perlin_noise_float(p) (amplitude 1, pivot 0) */
float eido_mx_noise(vec3 p) {
  vec3 fl = floor(p);
  ivec3 I = ivec3(fl);
  vec3 f = p - fl;
  float u = eido_mx_fade(f.x), v = eido_mx_fade(f.y), w = eido_mx_fade(f.z);
  float v0 = eido_mx_grad(eido_mx_hash(I.x, I.y, I.z), f.x, f.y, f.z);
  float v1 = eido_mx_grad(eido_mx_hash(I.x + 1, I.y, I.z), f.x - 1.0, f.y, f.z);
  float v2 = eido_mx_grad(eido_mx_hash(I.x, I.y + 1, I.z), f.x, f.y - 1.0, f.z);
  float v3 = eido_mx_grad(eido_mx_hash(I.x + 1, I.y + 1, I.z), f.x - 1.0, f.y - 1.0, f.z);
  float v4 = eido_mx_grad(eido_mx_hash(I.x, I.y, I.z + 1), f.x, f.y, f.z - 1.0);
  float v5 = eido_mx_grad(eido_mx_hash(I.x + 1, I.y, I.z + 1), f.x - 1.0, f.y, f.z - 1.0);
  float v6 = eido_mx_grad(eido_mx_hash(I.x, I.y + 1, I.z + 1), f.x, f.y - 1.0, f.z - 1.0);
  float v7 = eido_mx_grad(eido_mx_hash(I.x + 1, I.y + 1, I.z + 1), f.x - 1.0, f.y - 1.0, f.z - 1.0);
  float s1 = 1.0 - u, t1 = 1.0 - v, r1 = 1.0 - w;
  float r = r1 * (t1 * (v0 * s1 + v1 * u) + v * (v2 * s1 + v3 * u))
          + w * (t1 * (v4 * s1 + v5 * u) + v * (v6 * s1 + v7 * u));
  return 0.9820 * r;
}
"""


class Kernel:
    def __init__(self, ctx, shader, local, push):
        self.ctx = ctx
        self.shader = shader
        self.local = local
        self.push = dict((n, t) for t, n in push)

    def run(self, groups, samplers=None, images=None, **uniforms):
        import gpu
        sh = self.shader
        for name, tex in (samplers or {}).items():
            sh.uniform_sampler(name, tex)
        for name, tex in (images or {}).items():
            sh.image(name, tex)
        for name, val in uniforms.items():
            t = self.push[name]
            if t == 'INT':
                sh.uniform_int(name, int(val))
            elif t == 'MAT4':
                sh.uniform_float(name, [float(x) for x in np.asarray(val, dtype=np.float64).T.ravel()])
            elif t == 'FLOAT':
                sh.uniform_float(name, float(val))
            else:
                sh.uniform_float(name, [float(x) for x in val])
        gpu.compute.dispatch(sh, *groups)

    def groups_for(self, size):
        return tuple(int(math.ceil(s / l)) for s, l in zip(size, self.local))


class ComputeContext:
    """Owns the GPU context in background mode and builds textures and kernels."""

    def __init__(self):
        import bpy
        import gpu
        if bpy.app.background:
            try:
                gpu.init()
            except Exception:
                pass                             # already initialised in this process
        self.gpu = gpu

    def texture3d(self, size, fmt='RGBA16F', filt=True, extend='EXTEND'):
        gpu = self.gpu
        tex = gpu.types.GPUTexture(tuple(int(s) for s in size), format=fmt)
        tex.clear(format='FLOAT', value=(0.0, 0.0, 0.0, 0.0))
        tex.filter_mode(bool(filt))
        tex.extend_mode(extend)
        return tex

    def texture2d_from(self, arr, fmt='RGBA32F'):
        """Upload an (H, W, 4) float array (row 0 = texel row 0)."""
        gpu = self.gpu
        a = np.ascontiguousarray(np.asarray(arr, dtype=np.float32))
        h, w = a.shape[:2]
        buf = gpu.types.Buffer('FLOAT', a.size, a.ravel())
        tex = gpu.types.GPUTexture((w, h), format=fmt, data=buf)
        tex.filter_mode(False)
        return tex

    def read(self, tex):
        """Texture contents as numpy float32, shape (depth, height, width, 4) for 3D textures."""
        buf = tex.read()
        return np.array(buf, dtype=np.float32, copy=True)

    def kernel(self, source, samplers=(), images=(), push=(), local=(8, 8, 4), image_type='FLOAT_3D',
               image_format='RGBA16F', sampler_types=None, defines=None, preamble=''):
        gpu = self.gpu
        info = gpu.types.GPUShaderCreateInfo()
        info.local_group_size(*local)
        slot = 0
        for name in samplers:
            st = (sampler_types or {}).get(name, 'FLOAT_3D')
            info.sampler(slot, st, name)
            slot += 1
        for i, name in enumerate(images):
            info.image(i, image_format, image_type, name, qualifiers={'WRITE'})
        for t, n in push:
            info.push_constant(t, n)
        for k, v in (defines or {}).items():
            info.define(k, str(v))
        info.compute_source(preamble + '\n' + source)
        shader = gpu.shader.create_from_info(info)
        return Kernel(self, shader, local, push)
