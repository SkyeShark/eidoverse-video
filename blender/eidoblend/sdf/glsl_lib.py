"""The GLSL that every SDF program is built from: the engine's primitive library, kept as the engine wrote it, and
the Blender edition's own prelude (the uniform block, the surface record, calcNormal / softShadow / sampleEnvMap).

SDF_PRIMITIVES is sdf_raymarch_loader.js's SDF_PRIMITIVES_GLSL (the library the GLSL EXAMPLES were written against
and that SDF_TSL ports) with one change: _hash's arithmetic is declared `precise`. Without it the GPU compiler, after
inlining vnoise's eight corners, folds each corner's +1 offset into the hash's additive constant differently, so one
lattice point hashes to different values from the cells around it and the noise tears along cell faces (measured:
1.5 % of face crossings jump, by up to 0.99; the engine's own raymarch shows the seams). `precise` holds the
compiler to the arithmetic as written: the same hash, now one value per lattice point. An example's `extra`, `map`,
`shade`, `surface` and `sample` are GLSL source in the same dialect, so the engine's GLSL originals (mrHege,
redShoggoth, the recipes) run as they were written.

Coordinates inside every GLSL function are the SDF's own local frame, three.js style: y up. The Blender object
built from it is converted to Blender's z-up axes when the mesh is written, so the GLSL never changes.
"""

SDF_PRIMITIVES = r"""
// --- distances ---
float sdSphere(vec3 p, float r) { return length(p) - r; }
float sdSphere(vec3 p, vec3 c, float r) { return length(p - c) - r; }

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sdRoundBox(vec3 p, vec3 b, float r) { return sdBox(p, b) - r; }

float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}
// Tapered capsule: radius r1 at A, r2 at B
float sdCap2(vec3 p, vec3 a, vec3 b, float r1, float r2) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - mix(r1, r2, h);
}

float sdEllipsoid(vec3 p, vec3 r) {
    vec3 d = p / r;
    float k0 = length(d);
    return (k0 - 1.0) * min(r.x, min(r.y, r.z));
}
float sdEllipsoid(vec3 p, vec3 c, vec3 r) { return sdEllipsoid(p - c, r); }

float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

float sdCone(vec3 p, vec2 c, float h) {
    vec2 q = h * vec2(c.x / c.y, -1.0);
    vec2 w = vec2(length(p.xz), p.y);
    vec2 a = w - q * clamp(dot(w, q) / dot(q, q), 0.0, 1.0);
    vec2 b = w - q * vec2(clamp(w.x / q.x, 0.0, 1.0), 1.0);
    float k = sign(q.y);
    float d = min(dot(a, a), dot(b, b));
    float s = max(k * (w.x * q.y - w.y * q.x), k * (w.y - q.y));
    return sqrt(d) * sign(s);
}

float sdRoundCone(vec3 p, vec3 a, vec3 b, float r1, float r2) {
    return sdCap2(p, a, b, r1, r2);
}

// Triangular prism, apex +Y, extruded along Z. Negate p.y for inverted.
float sdTriPrism(vec3 p, float hx, float hz) {
    vec3 q = abs(p);
    return max(q.z - hz, max(q.x * 0.866025 + p.y * 0.5, -p.y) - hx * 0.5);
}

// --- ops ---
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}
float smax(float a, float b, float k) { return -smin(-a, -b, k); }

vec2 opU(vec2 a, vec2 b) { return a.x < b.x ? a : b; }
vec2 opSmoothU(vec2 a, vec2 b, float k) {
    float h = clamp(0.5 + 0.5 * (b.x - a.x) / k, 0.0, 1.0);
    float d = mix(b.x, a.x, h) - k * h * (1.0 - h);
    return vec2(d, a.x < b.x ? a.y : b.y);
}
float opSub(float a, float b) { return max(-a, b); }
float opSmoothSub(float a, float b, float k) { return smax(-a, b, k); }
float opInt(float a, float b) { return max(a, b); }

// --- transforms (use in map() to rotate/mirror local coords) ---
vec3 opRotateY(vec3 p, float a) {
    float c = cos(a), s = sin(a);
    return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}
vec3 opRotateX(vec3 p, float a) {
    float c = cos(a), s = sin(a);
    return vec3(p.x, c * p.y - s * p.z, s * p.y + c * p.z);
}
vec3 opRotateZ(vec3 p, float a) {
    float c = cos(a), s = sin(a);
    return vec3(c * p.x - s * p.y, s * p.x + c * p.y, p.z);
}
vec3 opMirrorX(vec3 p) { return vec3(abs(p.x), p.y, p.z); }
vec3 opMirrorZ(vec3 p) { return vec3(p.x, p.y, abs(p.z)); }

// --- noise / fbm ---
float _hash(vec3 p) {
    precise vec3 q = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
    q *= 17.0;
    precise float h = q.x * q.y * q.z * (q.x + q.y + q.z);
    return fract(h);
}
float vnoise(vec3 x) {
    vec3 i = floor(x), f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(_hash(i + vec3(0,0,0)), _hash(i + vec3(1,0,0)), f.x),
                   mix(_hash(i + vec3(0,1,0)), _hash(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(_hash(i + vec3(0,0,1)), _hash(i + vec3(1,0,1)), f.x),
                   mix(_hash(i + vec3(0,1,1)), _hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * vnoise(p); p *= 2.03; a *= 0.5; }
    return v;
}
// 6-octave for high-quality surface detail
float fbm6(vec3 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 6; i++) { v += a * vnoise(p); p *= 2.07; a *= 0.5; }
    return v;
}
"""

# The surface record a Blender `surface(p, n, mat)` returns: what the engine's shade() computed BEFORE its hand
# lighting (albedo, roughness, metal), plus the Principled inputs that stand in for its view-dependent terms
# (fresnel rims -> sheen / coat, wrap "SSS" -> subsurface). EEVEE lights it with the scene's own lights.
SURFACE_RECORD = r"""
struct SdfSurface {
    vec3 albedo;      // linear base colour
    float roughness;
    float metallic;
    vec3 emission;    // linear radiance (Principled Emission Color at strength 1)
    float sheen;      // Principled Sheen Weight (velvet / rim terms)
    vec3 sheenTint;
    float subsurface; // Principled Subsurface Weight
    float coat;       // Principled Coat Weight
    float specular;   // Principled Specular IOR Level (0.5 = the IOR's own F0)
    float transmission;
};
SdfSurface sdfSurface(vec3 albedo, float roughness) {
    SdfSurface s;
    s.albedo = albedo; s.roughness = roughness; s.metallic = 0.0;
    s.emission = vec3(0.0); s.sheen = 0.0; s.sheenTint = vec3(1.0);
    s.subsurface = 0.0; s.coat = 0.0; s.specular = 0.5; s.transmission = 0.0;
    return s;
}
"""

# The surface a GLSL map gets when it brings none: the Principled defaults.
DEFAULT_SURFACE = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) { return sdfSurface(vec3(0.8), 0.5); }
"""

# The surface a spec in the engine's own contract (map + shade, no surface) gets: shade() evaluated where the bake
# stands the viewer, straight along the normal, so its rim and fresnel terms read head-on. Its hand lighting stays in
# the colour. As albedo (the default) the scene's lights shade it again; as emission (SDF_SHADE_AS_EMISSION 1) it is
# the engine's exact unlit look: it still casts shadows and shows in reflections, but takes no light.
SHADE_SURFACE = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    vec3 c = max(shade(p, n, mat), vec3(0.0));
#if SDF_SHADE_AS_EMISSION
    SdfSurface s = sdfSurface(vec3(0.0), 1.0);
    s.emission = c;
    s.specular = 0.0;
#else
    SdfSurface s = sdfSurface(min(c, vec3(1.0)), 0.6);
#endif
    return s;
}
"""

# What the volume kernels return. SdfSample is the engine's createSdfVolume contract: sample(p) -> {color, alpha,
# step}: alpha is the per-sample opacity for a stride of `step` and color the radiance it adds, accumulated front to
# back. SdfMedium is the Blender-native one: densities and colours per metre.
VOLUME_RECORDS = r"""
struct SdfSample { vec3 color; float alpha; float step; };
SdfSample sdfSample(vec3 color, float alpha, float step) { SdfSample s; s.color = color; s.alpha = alpha; s.step = step; return s; }
struct SdfMedium {
    float density;    // extinction per metre (Principled Volume Density)
    vec3 albedo;      // scattering colour (Principled Volume Color)
    vec3 emission;    // emitted radiance per metre (Emission Color at strength 1)
    float temperature;  // kelvin for blackbody, 0 = none
};
SdfMedium sdfMedium(float density, vec3 albedo, vec3 emission) {
    SdfMedium m; m.density = density; m.albedo = albedo; m.emission = emission; m.temperature = 0.0; return m;
}
"""

# calcNormal / softShadow exactly as the engine's fragment shader defined them (calcNormal's step `h` is the
# engine's 0.0004 in the reference raymarch; the bake kernels pass their own through sdfNormalH).
NORMAL_AND_SHADOW = r"""
vec3 calcNormal(vec3 p) {
    const vec2 k = vec2(1.0, -1.0);
    float h = sdfNormalH;
    return normalize(
        k.xyy * map(p + k.xyy * h).x +
        k.yyx * map(p + k.yyx * h).x +
        k.yxy * map(p + k.yxy * h).x +
        k.xxx * map(p + k.xxx * h).x
    );
}

float softShadow(vec3 ro, vec3 rd, float mint, float maxt, float k) {
    float res = 1.0;
    float t = mint;
    for (int i = 0; i < 48; i++) {
        float h = map(ro + rd * t).x;
        if (h < 0.0005) return 0.0;
        res = min(res, k * h / t);
        t += h;
        if (t >= maxt) break;
    }
    return clamp(res, 0.0, 1.0);
}
"""

# The engine's HDRI helpers. sampleEnvMap reads an equirect bound as sdfEnvMap (the scene world's image when the
# reference raymarch is given one) and returns the engine's mid grey when none is bound.
ENV_HELPERS = r"""
vec3 sampleEnvMap(vec3 worldDir) {
    if (uEnvMapStrength <= 0.0) return vec3(0.5);
    vec3 d = normalize(worldDir);
    vec2 uv = vec2(
        atan(d.z, d.x) * 0.15915494 + 0.5,
        asin(clamp(d.y, -1.0, 1.0)) * 0.31830989 + 0.5
    );
    return texture(sdfEnvMap, uv).rgb * uEnvMapStrength;
}
vec3 sdfReflectWorld(vec3 pLocal, vec3 nLocal) {
    vec3 pWorld = (uModelMatrix * vec4(pLocal, 1.0)).xyz;
    vec3 nWorld = normalize(mat3(uModelMatrix) * nLocal);
    vec3 viewWorld = normalize(cameraPositionWorld - pWorld);
    return reflect(-viewWorld, nWorld);
}
"""

# Kernel bodies. Each reads its points from sdfPoints (RGBA32F, one point per texel) and writes up to six targets.
# sdfClip intersects the field with the padded bounds box so a surface leaving the bounds closes there (the engine's
# march never drew outside its box either).
KERNEL_COMMON = r"""
float sdfClipBox(vec3 p) {
    vec3 c = 0.5 * (sdfClipMin + sdfClipMax);
    vec3 b = 0.5 * (sdfClipMax - sdfClipMin);
    vec3 q = abs(p - c) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
vec2 sdfMapClipped(vec3 p) {
    vec2 r = map(p);
    if (sdfUseClip > 0.5) r.x = max(r.x, sdfClipBox(p));
    return r;
}
vec3 sdfGrad(vec3 p, float h) {
    const vec2 k = vec2(1.0, -1.0);
    vec3 g = k.xyy * sdfMapClipped(p + k.xyy * h).x + k.yyx * sdfMapClipped(p + k.yyx * h).x
           + k.yxy * sdfMapClipped(p + k.yxy * h).x + k.xxx * sdfMapClipped(p + k.xxx * h).x;
    return g / (4.0 * h);
}
vec4 sdfFetchPoint() { return texelFetch(sdfPoints, ivec2(gl_FragCoord.xy), 0); }
"""

# `cameraPosition` in an example's GLSL is the viewer, in the SDF's local frame (the originals mixed it with local p,
# which only agreed for an unrotated object at the origin; the TSL port made it ctx.ro, the local camera). Each
# kernel sets it per invocation: the reference raymarch from the Blender camera; the surface bake from straight
# along the normal, so view-dependent terms (rims, fresnel tints) read as seen head-on and stay out of the textures.
VIEW_PRELUDE = r"""
vec3 sdfViewPos;
#define cameraPosition sdfViewPos
#define uEnvMap sdfEnvMap
"""

KERNEL_DIST = r"""
void main() {
    sdfViewPos = sdfCameraUniform;
    vec4 q = sdfFetchPoint();
    vec2 r = sdfMapClipped(q.xyz);
    out0 = vec4(r.x, r.y, 0.0, 1.0);
}
"""

KERNEL_GRAD = r"""
void main() {
    sdfViewPos = sdfCameraUniform;
    vec4 q = sdfFetchPoint();
    vec2 r = sdfMapClipped(q.xyz);
    vec3 g = sdfGrad(q.xyz, sdfGradH);
    out0 = vec4(r.x, r.y, 0.0, 1.0);
    out1 = vec4(g, length(g));
}
"""

# surface: optional Newton projection onto the level set, the normal at the storage resolution, the material id,
# then the example's surface().
KERNEL_SURFACE = r"""
void main() {
    sdfViewPos = sdfCameraUniform;
    vec4 q = sdfFetchPoint();
    vec3 p = q.xyz;
    for (int i = 0; i < 4; i++) {
        if (float(i) >= sdfProject) break;
        float d = sdfMapClipped(p).x - sdfIso;
        vec3 g = sdfGrad(p, sdfGradH);
        p -= d * g / max(dot(g, g), 1e-12);
    }
    vec2 r = sdfMapClipped(p);
    vec3 n = normalize(sdfGrad(p, sdfNormalH) + vec3(0.0, 1e-20, 0.0));
    sdfViewPos = p + n * 1000.0;
    SdfSurface s = surface(p, n, r.y);
    out0 = vec4(s.albedo, s.roughness);
    out1 = vec4(s.emission, s.metallic);
    out2 = vec4(s.sheenTint, s.sheen);
    out3 = vec4(s.subsurface, s.coat, s.specular, s.transmission);
    out4 = vec4(p, r.x);
    out5 = vec4(n, r.y);
}
"""

KERNEL_SAMPLE = r"""
void main() {
    sdfViewPos = sdfCameraUniform;
    vec4 q = sdfFetchPoint();
    SdfSample s = sample(q.xyz);
    out0 = vec4(s.color, s.alpha);
    out1 = vec4(s.step, 0.0, 0.0, 1.0);
}
"""

KERNEL_MEDIUM = r"""
void main() {
    sdfViewPos = sdfCameraUniform;
    vec4 q = sdfFetchPoint();
    SdfMedium m = medium(q.xyz);
    out0 = vec4(m.emission, m.density);
    out1 = vec4(m.albedo, m.temperature);
}
"""

# createSdfVolume's march, from a Blender camera in the volume's local three frame: front-to-back premultiplied
# accumulation through the bounds box, the sample's own alpha and step, early out at 0.99, the optional post(sum),
# and the engine's discard below 0.01. The reference an EEVEE volume is judged against.
KERNEL_VOLUME_RAYMARCH = r"""
void main() {
    vec2 px = gl_FragCoord.xy + 0.5 * sdfJitter;
    vec2 ndc = px / sdfImageSize * 2.0 - 1.0;
    vec3 ro = sdfCameraUniform;
    sdfViewPos = ro;
    vec3 rd = normalize(sdfCamFwd + ndc.x * sdfCamTan.x * sdfCamRight + ndc.y * sdfCamTan.y * sdfCamUp);
    vec3 inv = 1.0 / rd;
    vec3 t0v = (sdfClipMin - ro) * inv, t1v = (sdfClipMax - ro) * inv;
    vec3 tn = min(t0v, t1v), tx = max(t0v, t1v);
    float t0 = max(max(max(tn.x, tn.y), tn.z), 0.0);
    float t1 = min(min(tx.x, tx.y), tx.z);
    if (t1 <= t0) { out0 = vec4(0.0); return; }
    vec4 sum = vec4(0.0);
    float t = t0;
    for (int i = 0; i < 4096; i++) {
        if (float(i) >= sdfVolSteps) break;
        if (t > t1 || sum.w >= 0.99) break;
        vec3 p = ro + rd * t;
#ifdef SDF_VOLUME_MEDIUM
        SdfMedium m = medium(p);
        float dt = sdfMediumStep;
        float a = 1.0 - exp(-max(m.density, 0.0) * dt);
        // emission, plus the scattering colour under a flat ambient (no shadowing: the reference shows the medium's
        // shape and opacity; the scene's real light on it is EEVEE's)
        vec3 c = m.density > 1e-6 ? m.emission / m.density + m.albedo * sdfMediumAmbient : vec3(0.0);
        float stp = dt;
#else
        SdfSample smp = sample(p);
        float a = clamp(smp.alpha, 0.0, 1.0);
        vec3 c = smp.color;
        float stp = smp.step;
#endif
        float contrib = a * (1.0 - sum.w);
        sum = vec4(sum.xyz + c * contrib, sum.w + contrib);
        t += max(stp, 1e-4);
    }
    if (sum.w < 0.01) { out0 = vec4(0.0); return; }
#ifdef SDF_HAS_POST
    sum = post(sum);
#endif
    out0 = sum;
}
"""

# The engine's raymarch (createSdfObject's fragment shader) with the example's own shade(), from a Blender camera
# moved into the object's local three frame: the reference the EEVEE port is judged against. With sdfUseClip on (an
# example cut_by_bounds, whose surface runs past its box on purpose) it marches the field cut by the bounds box, the
# solid the mesh is; the engine's own march walked back out of the box there and drew the uncut surface in front.
KERNEL_RAYMARCH = r"""
void main() {
    vec2 px = gl_FragCoord.xy + 0.5 * sdfJitter;
    vec2 ndc = px / sdfImageSize * 2.0 - 1.0;
    vec3 roLocal = sdfCameraUniform;
    sdfViewPos = roLocal;
    vec3 rdLocal = normalize(sdfCamFwd + ndc.x * sdfCamTan.x * sdfCamRight + ndc.y * sdfCamTan.y * sdfCamUp);
    float t = 0.001;
    vec2 res = vec2(9999.0, 0.0);
    bool hit = false;
    // the engine's bounds-box entry: rays start where they enter the box (the proxy box's fragment)
    vec3 inv = 1.0 / rdLocal;
    vec3 t0v = (sdfClipMin - roLocal) * inv, t1v = (sdfClipMax - roLocal) * inv;
    vec3 tn = min(t0v, t1v), tx = max(t0v, t1v);
    float tEnter = max(max(tn.x, tn.y), tn.z), tExit = min(min(tx.x, tx.y), tx.z);
    if (tExit <= max(tEnter, 0.0)) { out0 = vec4(0.0); return; }
    t = max(tEnter, 0.001);
    for (int i = 0; i < 1024; i++) {
        if (float(i) >= uMaxSteps) break;
        vec3 p = roLocal + rdLocal * t;
        res = sdfMapClipped(p);
        if (abs(res.x) < uSurfEps * max(t, 1.0)) { hit = true; break; }
        t += res.x * uStepScale;
        if (t > uMaxDist || t > tExit) break;
    }
    if (!hit) { out0 = vec4(0.0); return; }
    vec3 hitLocal = roLocal + rdLocal * t;
    vec3 nLocal = sdfUseClip > 0.5 ? normalize(sdfGrad(hitLocal, sdfNormalH)) : calcNormal(hitLocal);
    vec3 col = shade(hitLocal, nLocal, res.y);
    out0 = vec4(col, 1.0);
}
"""
