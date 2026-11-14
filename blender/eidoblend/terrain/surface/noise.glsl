/* Blender's shader noise, ported for the surface bake (SURFACING_DESIGN.md 2.1, 2.3): the Noise Texture's fBM (3D
   and 4D, normalised: its Fac) and the Voronoi texture's F1 cell colour (2D and 3D), with Blender's own hashes (Bob
   Jenkins' lookup3, Cycles' util/hash.h) and Perlin noise (Cycles' svm/noise.h, Apache-2.0; Blender's GLSL is the
   same arithmetic, GPL-2.0-or-later). A term the bake evaluates with these equals the material's Noise and Voronoi
   nodes at the same coordinates. Pasted into a kernel where it says so; twin: surface/noise.py. */

uint bn_rot(uint x, uint k) { return (x << k) | (x >> (32u - k)); }

void bn_mix(inout uint a, inout uint b, inout uint c) {
  a -= c; a ^= bn_rot(c, 4u);  c += b;
  b -= a; b ^= bn_rot(a, 6u);  a += c;
  c -= b; c ^= bn_rot(b, 8u);  b += a;
  a -= c; a ^= bn_rot(c, 16u); c += b;
  b -= a; b ^= bn_rot(a, 19u); a += c;
  c -= b; c ^= bn_rot(b, 4u);  b += a;
}

void bn_final(inout uint a, inout uint b, inout uint c) {
  c ^= b; c -= bn_rot(b, 14u);
  a ^= c; a -= bn_rot(c, 11u);
  b ^= a; b -= bn_rot(a, 25u);
  c ^= b; c -= bn_rot(b, 16u);
  a ^= c; a -= bn_rot(c, 4u);
  b ^= a; b -= bn_rot(a, 14u);
  c ^= b; c -= bn_rot(b, 24u);
}

uint bn_hash2(uint kx, uint ky) {
  uint a = 0xdeadbeefu + (2u << 2u) + 13u;
  uint b = a, c = a;
  b += ky;
  a += kx;
  bn_final(a, b, c);
  return c;
}

uint bn_hash3(uint kx, uint ky, uint kz) {
  uint a = 0xdeadbeefu + (3u << 2u) + 13u;
  uint b = a, c = a;
  c += kz;
  b += ky;
  a += kx;
  bn_final(a, b, c);
  return c;
}

uint bn_hash4(uint kx, uint ky, uint kz, uint kw) {
  uint a = 0xdeadbeefu + (4u << 2u) + 13u;
  uint b = a, c = a;
  a += kx;
  b += ky;
  c += kz;
  bn_mix(a, b, c);
  a += kw;
  bn_final(a, b, c);
  return c;
}

float bn_u2f(uint h) { return float(h) / float(0xFFFFFFFFu); }
/* the Voronoi texture's hashes of integer cell indices (Blender 4.1+: the PCG hashes of "Hash Functions for GPU
   Rendering", JCGT 2020, in signed integers: hash_int2_to_float2(k) = pcg2d(k) without the paper's last xor-shift,
   hash_int2_to_float3(k) = pcg3d(k, 0), hash_int3_to_float3(k) = pcg3d(k); checked against Blender's renders) */
ivec2 bn_pcg2d_i(ivec2 v) {
  v = v * 1664525 + 1013904223;
  v.x += v.y * 1664525;
  v.y += v.x * 1664525;
  v ^= v >> 16;
  v.x += v.y * 1664525;
  v.y += v.x * 1664525;
  return v & ivec2(0x7FFFFFFF);
}
ivec3 bn_pcg3d_i(ivec3 v) {
  v = v * 1664525 + 1013904223;
  v.x += v.y * v.z;
  v.y += v.z * v.x;
  v.z += v.x * v.y;
  v ^= v >> 16;
  v.x += v.y * v.z;
  v.y += v.z * v.x;
  v.z += v.x * v.y;
  return v & ivec3(0x7FFFFFFF);
}
vec2 bn_hash_i2_f2(ivec2 k) { return vec2(bn_pcg2d_i(k)) * (1.0 / float(0x7FFFFFFF)); }
vec3 bn_hash_i2_f3(ivec2 k) { return vec3(bn_pcg3d_i(ivec3(k, 0))) * (1.0 / float(0x7FFFFFFF)); }
vec3 bn_hash_i3_f3(ivec3 k) { return vec3(bn_pcg3d_i(k)) * (1.0 / float(0x7FFFFFFF)); }

float bn_fade(float t) { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }
float bn_negate_if(float v, uint c) { return c != 0u ? -v : v; }

float bn_grad3(uint hash, float x, float y, float z) {
  uint h = hash & 15u;
  float u = h < 8u ? x : y;
  float vt = (h == 12u || h == 14u) ? x : z;
  float v = h < 4u ? y : vt;
  return bn_negate_if(u, h & 1u) + bn_negate_if(v, h & 2u);
}

float bn_grad4(uint hash, float x, float y, float z, float w) {
  uint h = hash & 31u;
  float u = h < 24u ? x : y;
  float v = h < 16u ? y : z;
  float s = h < 8u ? z : w;
  return bn_negate_if(u, h & 1u) + bn_negate_if(v, h & 2u) + bn_negate_if(s, h & 4u);
}

float bn_tri_mix(float v0, float v1, float v2, float v3, float v4, float v5, float v6, float v7,
                 float x, float y, float z) {
  float x1 = 1.0 - x;
  float y1 = 1.0 - y;
  float z1 = 1.0 - z;
  return z1 * (y1 * (v0 * x1 + v1 * x) + y * (v2 * x1 + v3 * x)) +
         z * (y1 * (v4 * x1 + v5 * x) + y * (v6 * x1 + v7 * x));
}

float bn_perlin3(vec3 p) {
  vec3 fl = floor(p);
  ivec3 I = ivec3(fl);
  vec3 f = p - fl;
  uint X = uint(I.x), Y = uint(I.y), Z = uint(I.z);
  float u = bn_fade(f.x), v = bn_fade(f.y), w = bn_fade(f.z);
  return bn_tri_mix(bn_grad3(bn_hash3(X, Y, Z), f.x, f.y, f.z),
                    bn_grad3(bn_hash3(X + 1u, Y, Z), f.x - 1.0, f.y, f.z),
                    bn_grad3(bn_hash3(X, Y + 1u, Z), f.x, f.y - 1.0, f.z),
                    bn_grad3(bn_hash3(X + 1u, Y + 1u, Z), f.x - 1.0, f.y - 1.0, f.z),
                    bn_grad3(bn_hash3(X, Y, Z + 1u), f.x, f.y, f.z - 1.0),
                    bn_grad3(bn_hash3(X + 1u, Y, Z + 1u), f.x - 1.0, f.y, f.z - 1.0),
                    bn_grad3(bn_hash3(X, Y + 1u, Z + 1u), f.x, f.y - 1.0, f.z - 1.0),
                    bn_grad3(bn_hash3(X + 1u, Y + 1u, Z + 1u), f.x - 1.0, f.y - 1.0, f.z - 1.0), u, v, w);
}

float bn_perlin4(vec4 p) {
  vec4 fl = floor(p);
  ivec4 I = ivec4(fl);
  vec4 f = p - fl;
  uint X = uint(I.x), Y = uint(I.y), Z = uint(I.z), W = uint(I.w);
  float u = bn_fade(f.x), v = bn_fade(f.y), t = bn_fade(f.z), s = bn_fade(f.w);
  float a = bn_tri_mix(bn_grad4(bn_hash4(X, Y, Z, W), f.x, f.y, f.z, f.w),
                       bn_grad4(bn_hash4(X + 1u, Y, Z, W), f.x - 1.0, f.y, f.z, f.w),
                       bn_grad4(bn_hash4(X, Y + 1u, Z, W), f.x, f.y - 1.0, f.z, f.w),
                       bn_grad4(bn_hash4(X + 1u, Y + 1u, Z, W), f.x - 1.0, f.y - 1.0, f.z, f.w),
                       bn_grad4(bn_hash4(X, Y, Z + 1u, W), f.x, f.y, f.z - 1.0, f.w),
                       bn_grad4(bn_hash4(X + 1u, Y, Z + 1u, W), f.x - 1.0, f.y, f.z - 1.0, f.w),
                       bn_grad4(bn_hash4(X, Y + 1u, Z + 1u, W), f.x, f.y - 1.0, f.z - 1.0, f.w),
                       bn_grad4(bn_hash4(X + 1u, Y + 1u, Z + 1u, W), f.x - 1.0, f.y - 1.0, f.z - 1.0, f.w), u, v, t);
  float b = bn_tri_mix(bn_grad4(bn_hash4(X, Y, Z, W + 1u), f.x, f.y, f.z, f.w - 1.0),
                       bn_grad4(bn_hash4(X + 1u, Y, Z, W + 1u), f.x - 1.0, f.y, f.z, f.w - 1.0),
                       bn_grad4(bn_hash4(X, Y + 1u, Z, W + 1u), f.x, f.y - 1.0, f.z, f.w - 1.0),
                       bn_grad4(bn_hash4(X + 1u, Y + 1u, Z, W + 1u), f.x - 1.0, f.y - 1.0, f.z, f.w - 1.0),
                       bn_grad4(bn_hash4(X, Y, Z + 1u, W + 1u), f.x, f.y, f.z - 1.0, f.w - 1.0),
                       bn_grad4(bn_hash4(X + 1u, Y, Z + 1u, W + 1u), f.x - 1.0, f.y, f.z - 1.0, f.w - 1.0),
                       bn_grad4(bn_hash4(X, Y + 1u, Z + 1u, W + 1u), f.x, f.y - 1.0, f.z - 1.0, f.w - 1.0),
                       bn_grad4(bn_hash4(X + 1u, Y + 1u, Z + 1u, W + 1u), f.x - 1.0, f.y - 1.0, f.z - 1.0,
                                f.w - 1.0), u, v, t);
  return mix(a, b, s);
}

/* C's fmod: a - b trunc(a / b) */
float bn_fmod(float a, float b) { return a - b * trunc(a / b); }

/* the safe signed noise: repeats every 100000 on each axis (Blender's guard against float precision) */
float bn_snoise3(vec3 p) {
  vec3 pc = 0.5 * vec3(greaterThanEqual(abs(p), vec3(1000000.0)));
  vec3 q = vec3(bn_fmod(p.x, 100000.0), bn_fmod(p.y, 100000.0), bn_fmod(p.z, 100000.0)) + pc;
  return 0.9820 * bn_perlin3(q);
}

float bn_snoise4(vec4 p) {
  vec4 pc = 0.5 * vec4(greaterThanEqual(abs(p), vec4(1000000.0)));
  vec4 q = vec4(bn_fmod(p.x, 100000.0), bn_fmod(p.y, 100000.0), bn_fmod(p.z, 100000.0), bn_fmod(p.w, 100000.0)) + pc;
  return 0.8344 * bn_perlin4(q);
}

/* the Noise Texture's fBM, normalised (its Fac), lacunarity 2 */
float bn_fbm3(vec3 p, float detail, float roughness) {
  detail = clamp(detail, 0.0, 15.0);
  roughness = max(roughness, 0.0);
  float fscale = 1.0, amp = 1.0, maxamp = 0.0, sum = 0.0;
  for (int i = 0; i <= int(detail); i++) {
    float t = bn_snoise3(fscale * p);
    sum += t * amp;
    maxamp += amp;
    amp *= roughness;
    fscale *= 2.0;
  }
  float rmd = detail - floor(detail);
  if (rmd != 0.0) {
    float t = bn_snoise3(fscale * p);
    float sum2 = sum + t * amp;
    return mix(0.5 * sum / maxamp + 0.5, 0.5 * sum2 / (maxamp + amp) + 0.5, rmd);
  }
  return 0.5 * sum / maxamp + 0.5;
}

float bn_fbm4(vec4 p, float detail, float roughness) {
  detail = clamp(detail, 0.0, 15.0);
  roughness = max(roughness, 0.0);
  float fscale = 1.0, amp = 1.0, maxamp = 0.0, sum = 0.0;
  for (int i = 0; i <= int(detail); i++) {
    float t = bn_snoise4(fscale * p);
    sum += t * amp;
    maxamp += amp;
    amp *= roughness;
    fscale *= 2.0;
  }
  float rmd = detail - floor(detail);
  if (rmd != 0.0) {
    float t = bn_snoise4(fscale * p);
    float sum2 = sum + t * amp;
    return mix(0.5 * sum / maxamp + 0.5, 0.5 * sum2 / (maxamp + amp) + 0.5, rmd);
  }
  return 0.5 * sum / maxamp + 0.5;
}

/* the Noise Texture node's Fac: 3D (Vector x Scale) and 4D ((Vector, W) x Scale), fBM, no distortion */
float bn_noise_node3(vec3 co, float scale, float detail, float roughness) {
  return bn_fbm3(co * scale, detail, roughness);
}

float bn_noise_node4(vec3 co, float w, float scale, float detail, float roughness) {
  return bn_fbm4(vec4(co * scale, w * scale), detail, roughness);
}

/* the Voronoi texture node's F1 Color (Euclidean, detail 0) */
vec3 bn_voronoi_f1_colour2(vec2 co, float scale, float randomness) {
  vec2 coord = co * scale;
  vec2 fl = floor(coord);
  ivec2 cell = ivec2(fl);
  vec2 local = coord - fl;
  float best = 3.4e38;
  ivec2 target = ivec2(0);
  randomness = clamp(randomness, 0.0, 1.0);
  for (int j = -1; j <= 1; j++) {
    for (int i = -1; i <= 1; i++) {
      ivec2 off = ivec2(i, j);
      vec2 pt = vec2(off) + bn_hash_i2_f2(cell + off) * randomness;
      float d = distance(pt, local);
      if (d < best) {
        best = d;
        target = off;
      }
    }
  }
  return bn_hash_i2_f3(cell + target);
}

vec3 bn_voronoi_f1_colour3(vec3 co, float scale, float randomness) {
  vec3 coord = co * scale;
  vec3 fl = floor(coord);
  ivec3 cell = ivec3(fl);
  vec3 local = coord - fl;
  float best = 3.4e38;
  ivec3 target = ivec3(0);
  randomness = clamp(randomness, 0.0, 1.0);
  for (int k = -1; k <= 1; k++) {
    for (int j = -1; j <= 1; j++) {
      for (int i = -1; i <= 1; i++) {
        ivec3 off = ivec3(i, j, k);
        vec3 pt = vec3(off) + bn_hash_i3_f3(cell + off) * randomness;
        float d = distance(pt, local);
        if (d < best) {
          best = d;
          target = off;
        }
      }
    }
  }
  return bn_hash_i3_f3(cell + target);
}
