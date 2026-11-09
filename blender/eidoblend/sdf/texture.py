"""make_sdf_texture: an SDF raymarched into an image (the Blender edition of makeSdfTexture and SDF_TEX_RECIPES),
and make_explosion_texture (makeExplosionTexture, from the engine's pre-TSL GLSL file).

createSdfObject places an SDF body in the scene; makeSdfTexture rendered an SDF with its own orbiting camera into a
texture, for screens, holograms, billboards and wallpaper: the same fractal on several monitors, under full PBR.
The engine's recipes are GLSL, and its WebGPU edition could no longer run them (a GLSL ShaderMaterial renders black
there). Blender's GPU module runs GLSL, so here they run again, verbatim: the palette, the default shade and sky,
the four distance estimators and the fragment main, rendered by a fragment pass into a bpy image.

    from eidoblend.sdf import make_sdf_texture
    bulb = make_sdf_texture(recipe='mandelbulb', width=512, height=256,
                            uniforms={'power': 8.0, 'iterations': 96, 'paletteHueShift': 0.0},
                            camera_orbit_radius=2.6, camera_orbit_speed=0.18, camera_pitch=0.4, camera_fov=1.6)
    bulb.update(2.0)                       # one frame at t = 2 s into bulb.image (a bpy Image, sRGB)
    bulb.bake(1, 240)                      # or the whole film: a PNG sequence the image plays, frame by frame
    screen.data.materials.append(bulb.material(emission_strength=0.9))   # map + emissiveMap, as the engine's usage

The texture is an 8-bit sRGB image of the shader's values, clamped, made to read back as the engine's did. The WebGL
engine tagged its 8-bit render target sRGB, so the GPU encoded each value on write and decoded it on read: its texels
held the shader's values as LINEAR light. That is the engine's look (encoding='linear', the default): bright skies
behind the fractals, and a washed, pale detonation whose own 1/2.2 gamma is applied twice, as the engine's smoke-test
frames show (workspace/sdf_tex_smoketest, sdf_explosion_smoketest). encoding='srgb' reads the values as display
colours instead, as the shaders were written (shadertoy-style recipes, the detonation's tone curve): darker skies,
deeper colour.

make_explosion_texture is the same contract around one self-contained shader: a mushroom-cloud detonation on a
15-second loop, with its own camera, fire ramp, sky and tone curve. The engine dropped it with the TSL migration
(dead on WebGPU); here it runs again from the GLSL backup, as written.
"""

from __future__ import annotations

import os

import numpy as np

from .gpu_eval import _ensure_gpu, _read_texture
from .spec import file_stem, resolve_cache_dir


def _check_encoding(encoding):
    if encoding not in ('srgb', 'linear'):
        raise ValueError(f"make_sdf_texture: encoding is 'srgb' or 'linear', not {encoding!r}")
    return encoding

SDF_TEX_PALETTE_GLSL = r"""
vec3 sdfTexPalette(float t, vec3 p, float mode) {
    if (mode < 0.5) {
        return 0.5 + 0.5 * cos(t * 0.30 + p * 3.5 + vec3(0.0, 2.1, 4.2));
    } else if (mode < 1.5) {
        vec3 a = vec3(0.10, 0.65, 0.85);
        vec3 b = vec3(0.95, 0.20, 0.60);
        float k = 0.5 + 0.5 * sin(t * 0.4 + p.x * 2.5 + p.z * 1.7);
        return mix(a, b, k);
    } else if (mode < 2.5) {
        vec3 amber = vec3(1.0, 0.62, 0.18);
        float k = 0.4 + 0.6 * sin(t * 0.35 + length(p) * 3.0);
        return amber * (0.55 + 0.45 * k);
    } else {
        vec3 g = vec3(0.20, 0.95, 0.55);
        float k = 0.5 + 0.5 * sin(t * 0.45 + p.y * 4.0);
        return g * (0.4 + 0.6 * k);
    }
}
"""

# Default shade: Lambert + fresnel + iteration-count AO + palette colour.
SDF_TEX_DEFAULT_SHADE = r"""
vec3 sdfTexShade(vec3 p, vec3 n, vec3 rd, int iter, int maxIter, float t, float paletteMode) {
    float ao = 1.0 - float(iter) / float(maxIter);
    vec3 lDir = normalize(vec3(0.6, 0.8, -0.3));
    float diff = max(dot(n, lDir), 0.0);
    float fres = pow(1.0 - max(0.0, dot(n, -rd)), 2.5);
    vec3 baseCol = sdfTexPalette(t, p, paletteMode);
    vec3 col = baseCol * (0.25 + 0.85 * diff) * (0.45 + 0.55 * ao);
    col += vec3(1.0, 0.75, 0.5) * fres * 0.7;
    col += vec3(1.0, 0.9, 0.7) * pow(1.0 - max(0.0, dot(-rd, n)), 8.0) * 0.4;
    return col;
}
"""

# Default sky: a soft nebula gradient + sparse stars, glowing near the SDF's silhouette.
SDF_TEX_DEFAULT_SKY = r"""
vec3 sdfTexSky(vec2 uv, float minDist, float t, float paletteMode) {
    vec3 a, b, glow;
    if (paletteMode < 0.5)        { a = vec3(0.05,0.02,0.08); b = vec3(0.20,0.04,0.16); glow = vec3(0.95,0.55,0.85); }
    else if (paletteMode < 1.5)   { a = vec3(0.02,0.04,0.10); b = vec3(0.04,0.10,0.22); glow = vec3(0.40,0.85,1.00); }
    else if (paletteMode < 2.5)   { a = vec3(0.06,0.04,0.02); b = vec3(0.18,0.10,0.04); glow = vec3(1.00,0.65,0.25); }
    else                          { a = vec3(0.02,0.06,0.03); b = vec3(0.04,0.16,0.08); glow = vec3(0.30,0.95,0.55); }
    vec3 sky = mix(a, b, 0.5 + 0.5 * uv.y);
    sky += glow * exp(-minDist * 7.0) * 0.6;
    vec2 starUV = uv * 18.0;
    float starHash = fract(sin(dot(floor(starUV), vec2(127.1, 311.7))) * 43758.5);
    float star = smoothstep(0.985, 1.0, starHash) * (0.7 + 0.3 * sin(t * 2.0 + starHash * 12.0));
    sky += vec3(1.0, 0.95, 0.85) * star;
    return sky;
}
"""

# The recipes' distance estimators, as the engine wrote them; default uniforms keep the engine's names (each
# becomes u<Name> in the shader, a float).
SDF_TEX_RECIPES = {
    'mandelbulb': {
        'default_uniforms': {'power': 8.0, 'iterations': 96, 'bailout': 6.0, 'paletteMode': 0.0, 'paletteHueShift': 0.0},
        'de': r"""
            float DE(vec3 pos) {
                vec3 z = pos;
                float dr = 1.0;
                float r = 0.0;
                // Mandelbulb inner-iteration count is fixed at 8 — uPower
                // is the fractal exponent, not the iteration count.
                for (int i = 0; i < 8; i++) {
                    r = length(z);
                    if (r > 2.0) break;
                    float theta = acos(clamp(z.z / r, -1.0, 1.0));
                    float phi   = atan(z.y, z.x);
                    dr = pow(r, uPower - 1.0) * uPower * dr + 1.0;
                    float zr = pow(r, uPower);
                    theta = theta * uPower;
                    phi   = phi * uPower;
                    z = zr * vec3(sin(theta) * cos(phi),
                                  sin(theta) * sin(phi),
                                  cos(theta));
                    z += pos;
                }
                return 0.5 * log(r) * r / dr;
            }
        """,
    },
    'sierpinski_tetra': {
        # Kaleidoscopic IFS folded tetrahedron — sharp crystalline geometry.
        'default_uniforms': {'power': 1.0, 'iterations': 80, 'bailout': 8.0, 'paletteMode': 1.0, 'paletteHueShift': 0.0,
                             'scale': 2.0, 'foldCount': 12.0},
        'de': r"""
            float DE(vec3 pos) {
                vec3 a1 = vec3( 1.0,  1.0,  1.0);
                vec3 a2 = vec3(-1.0, -1.0,  1.0);
                vec3 a3 = vec3( 1.0, -1.0, -1.0);
                vec3 a4 = vec3(-1.0,  1.0, -1.0);
                vec3 z = pos;
                float dist;
                for (int i = 0; i < 24; i++) {
                    if (float(i) >= uFoldCount) break;
                    vec3 c = a1; float minDist = length(z - a1);
                    dist = length(z - a2); if (dist < minDist) { c = a2; minDist = dist; }
                    dist = length(z - a3); if (dist < minDist) { c = a3; minDist = dist; }
                    dist = length(z - a4); if (dist < minDist) { c = a4; }
                    z = uScale * z - c * (uScale - 1.0);
                }
                return length(z) * pow(uScale, -float(uFoldCount));
            }
        """,
    },
    'menger_sponge': {
        # Iterated cube subtraction — recursive cross-cut grid.
        'default_uniforms': {'power': 1.0, 'iterations': 90, 'bailout': 8.0, 'paletteMode': 2.0, 'paletteHueShift': 0.0,
                             'foldCount': 5.0},
        'de': r"""
            float sdBox(vec3 p, vec3 b) {
                vec3 d = abs(p) - b;
                return min(max(d.x, max(d.y, d.z)), 0.0) + length(max(d, 0.0));
            }
            float DE(vec3 pos) {
                float d = sdBox(pos, vec3(1.0));
                float s = 1.0;
                for (int i = 0; i < 8; i++) {
                    if (float(i) >= uFoldCount) break;
                    vec3 a = mod(pos * s, 2.0) - 1.0;
                    s *= 3.0;
                    vec3 r = 1.0 - 3.0 * abs(a);
                    float c = (min(max(r.x, r.y), min(max(r.y, r.z), max(r.z, r.x)))) / s;
                    d = max(d, c);
                }
                return d;
            }
        """,
    },
    'gyroid': {
        # Triply periodic minimal surface — endless interlinked tunnels.
        'default_uniforms': {'power': 1.0, 'iterations': 80, 'bailout': 8.0, 'paletteMode': 3.0, 'paletteHueShift': 0.0,
                             'scale': 3.5, 'isoOffset': 0.0},
        'de': r"""
            float DE(vec3 pos) {
                vec3 p = pos * uScale;
                float g = dot(sin(p), cos(p.yzx)) - uIsoOffset;
                return g * 0.55 / uScale;
            }
        """,
    },
}

# The engine's fragment main (_buildSdfTexFragmentShader), unchanged but for its in/out: vUv is the pixel's centre
# over the image, and the colour goes to sdfTexColor instead of gl_FragColor.
_SDF_TEX_MAIN = r"""
vec3 calcNormal(vec3 p) {
    const float h = 0.0008;
    const vec2 k = vec2(1.0, -1.0);
    return normalize(
        k.xyy * DE(p + k.xyy * h) +
        k.yyx * DE(p + k.yyx * h) +
        k.yxy * DE(p + k.yxy * h) +
        k.xxx * DE(p + k.xxx * h)
    );
}
"""

_SDF_TEX_MAIN_BODY = r"""
void main() {
    vUv = (gl_FragCoord.xy + 0.5 * sdfTexJitter) / sdfTexSize;
    vec2 uv = vUv * 2.0 - 1.0;
    uv.x *= uAspect;
    float ang = uTime * uOrbitSpeed;
    float ca = cos(ang), sa = sin(ang);
    vec3 ro = uTarget + vec3(sa * uOrbitR, uPitch + 0.30 * sin(uTime * 0.12), ca * uOrbitR);
    vec3 ww = normalize(uTarget - ro);
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    vec3 rd = normalize(uv.x * uu + uv.y * vv + uFov * ww);
    float t = 0.5;
    float minDist = 1e9;
    int hitIter = 0;
    bool hit = false;
    const int MAX_ITER = 160;
    for (int i = 0; i < MAX_ITER; i++) {
        if (float(i) >= uIterations) break;
        vec3 p = ro + rd * t;
        float d = DE(p);
        minDist = min(minDist, d);
        if (d < 0.0008 * t) { hit = true; hitIter = i; break; }
        if (t > uBailout) break;
        t += d * 0.85;
    }
    vec3 col;
    if (hit) {
        vec3 p = ro + rd * t;
        vec3 n = calcNormal(p);
        col = sdfTexShade(p, n, rd, hitIter, MAX_ITER, uTime, uPaletteMode);
    } else {
        col = sdfTexSky(uv, minDist, uTime, uPaletteMode);
    }
    vec2 buv = vUv;
    float vig = smoothstep(0.0, 0.04, buv.x) * smoothstep(0.0, 0.04, buv.y)
              * smoothstep(0.0, 0.04, 1.0-buv.x) * smoothstep(0.0, 0.04, 1.0-buv.y);
    col *= 0.55 + 0.45 * vig;
    sdfTexColor = vec4(col, 1.0);
}
"""

_CAMEL_OPTS = {
    'cameraOrbitRadius': 'camera_orbit_radius', 'cameraOrbitSpeed': 'camera_orbit_speed',
    'cameraPitch': 'camera_pitch', 'cameraFov': 'camera_fov', 'cameraTarget': 'camera_target',
    'customDe': 'custom_de', 'customShade': 'custom_shade', 'updateEvery': 'update_every',
}


def _uname(k):
    """The engine's uniform naming: power -> uPower; a name already of the form uX stays."""
    if len(k) > 1 and k[0] == 'u' and k[1].isupper():
        return k
    return 'u' + k[0].upper() + k[1:]


class SdfTexture:
    """What make_sdf_texture returns. .image (also .texture, the engine's name) is the bpy Image; update(t) renders
    one frame into it; bake() renders a frame range into a PNG sequence the image plays; set_uniform(), material(),
    dispose(). .uniforms holds the shader's uniform values by their GLSL names."""

    def __init__(self, recipe='mandelbulb', width=512, height=256, aspect=None, uniforms=None,
                 camera_orbit_radius=2.6, camera_orbit_speed=0.18, camera_pitch=0.4, camera_fov=1.6,
                 camera_target=(0.0, 0.0, 0.0), custom_de=None, custom_shade=None, update_every=1, anisotropy=None,
                 name=None, cache_dir='//sdf_cache', samples=1, encoding='linear'):
        import bpy
        self.encoding = _check_encoding(encoding)
        base = SDF_TEX_RECIPES.get(recipe)
        if base is None and not custom_de:
            raise ValueError(f"make_sdf_texture: unknown recipe '{recipe}'. Built-ins: {', '.join(SDF_TEX_RECIPES)}. "
                             'Pass custom_de to use your own.')
        if base is None:
            base = {'default_uniforms': {'power': 1, 'iterations': 96, 'bailout': 6.0, 'paletteMode': 0.0}, 'de': ''}
        self.recipe = recipe
        self.width = int(width) or 512
        self.height = int(height) or 256
        self.aspect = float(aspect) if aspect is not None else self.width / self.height
        self.update_every = max(1, int(update_every or 1))
        self.anisotropy = anisotropy          # Blender filters images by its own settings: kept for the record
        self.samples = max(1, int(samples))
        self.name = name or f'sdf_tex_{recipe}'
        self.cache_dir = resolve_cache_dir(cache_dir)
        merged = dict(base['default_uniforms'])
        merged.update(uniforms or {})
        self.uniforms = {
            'uTime': 0.0, 'uAspect': self.aspect, 'uOrbitR': float(camera_orbit_radius),
            'uOrbitSpeed': float(camera_orbit_speed), 'uPitch': float(camera_pitch), 'uFov': float(camera_fov),
            'uTarget': tuple(float(x) for x in camera_target),
        }
        self._user = []
        for k, v in merged.items():
            self.uniforms[_uname(k)] = float(v)
            self._user.append(_uname(k))
        self.de = custom_de or base['de']
        self.custom_shade = custom_shade
        self._shader = None
        self._frames = 0
        self.image = bpy.data.images.new(self.name, self.width, self.height, alpha=False, float_buffer=False)
        self.image.colorspace_settings.name = 'sRGB'
        self.texture = self.image
        self.sequence = None
        # baked frames are named for the image, which Blender keeps unique: two screens of one recipe keep their own
        self.stem = file_stem(self.image.name)

    # ------------------------------------------------------------------------------------------------ source ---
    # the vector uniforms' swizzles over the uniform block (everything else is a float in .x)
    _SWIZZLE = {'uTarget': '.xyz', 'sdfTexSize': '.xy', 'sdfTexJitter': '.xy'}

    def _layout(self):
        names = ['uTime', 'uAspect', 'uOrbitR', 'uOrbitSpeed', 'uPitch', 'uFov', 'uTarget'] + self._user
        names += ['sdfTexSize', 'sdfTexJitter']
        return names

    def _uniform_macros(self):
        """Each uniform as a #define over one uniform block (the engine declared them one by one)."""
        return '\n'.join('#define %s (sdfTexU.v[%d]%s)' % (n, i, self._SWIZZLE.get(n, '.x'))
                         for i, n in enumerate(self._layout()))

    def source(self):
        """The full fragment source (the engine's shader, its uniforms as macros over one uniform block)."""
        shade = (('vec3 sdfTexShade(vec3 p, vec3 n, vec3 rd, int iter, int maxIter, float t, float paletteMode) { %s }'
                  % self.custom_shade) if self.custom_shade else SDF_TEX_DEFAULT_SHADE)
        return '\n'.join([self._uniform_macros(), 'vec2 vUv;', SDF_TEX_PALETTE_GLSL, self.de, _SDF_TEX_MAIN, shade,
                          SDF_TEX_DEFAULT_SKY, _SDF_TEX_MAIN_BODY])

    def _build(self):
        if self._shader is not None:
            return self._shader
        import gpu
        from gpu_extras.batch import batch_for_shader
        _ensure_gpu()
        n = len(self._layout())
        info = gpu.types.GPUShaderCreateInfo()
        info.typedef_source('struct SdfTexParams { vec4 v[%d]; };' % n)
        info.uniform_buf(0, 'SdfTexParams', 'sdfTexU')
        info.vertex_in(0, 'VEC2', 'pos')
        info.fragment_out(0, 'VEC4', 'sdfTexColor')
        info.vertex_source('void main() { gl_Position = vec4(pos, 0.0, 1.0); }')
        src = self.source()
        info.fragment_source(src)
        try:
            sh = gpu.shader.create_from_info(info)
        except Exception as e:
            numbered = '\n'.join('%4d  %s' % (i + 1, ln) for i, ln in enumerate(src.split('\n')))
            raise RuntimeError(f'[sdf.texture] {self.name}: the shader did not compile: {e}\n{numbered}') from e
        self._shader = (sh, batch_for_shader(sh, 'TRIS', {'pos': [(-1, -1), (3, -1), (-1, 3)]}))
        return self._shader

    def render(self, t):
        """Linear float (H, W, 4) of the shader at time t (row 0 at the bottom), averaged over `samples` jittered
        passes (1 = the engine's one sample per texel)."""
        import gpu
        sh, batch = self._build()
        self.uniforms['uTime'] = float(t)
        names = self._layout()
        tex = gpu.types.GPUTexture((self.width, self.height), format='RGBA32F')
        fb = gpu.types.GPUFrameBuffer(color_slots=(tex,))
        acc = np.zeros((self.height, self.width, 4), np.float64)
        rng = np.random.default_rng(11)
        for s in range(self.samples):
            jit = (0.0, 0.0) if s == 0 else tuple(float(x) for x in rng.uniform(-1, 1, 2))
            vals = dict(self.uniforms, sdfTexSize=(float(self.width), float(self.height)), sdfTexJitter=jit)
            block = np.zeros((len(names), 4), np.float32)
            for i, nme in enumerate(names):
                v = vals[nme]
                v = [v] if isinstance(v, (int, float)) else list(v)
                block[i, :len(v)] = v
            ubo = gpu.types.GPUUniformBuf(gpu.types.Buffer('FLOAT', block.size, block.ravel()))
            with fb.bind():
                sh.bind()
                sh.uniform_block('sdfTexU', ubo)
                batch.draw(sh)
            acc += _read_texture(tex).reshape(self.height, self.width, 4)
        return (acc / self.samples).astype(np.float32)

    # ---------------------------------------------------------------------------------------------- engine API ---
    def update(self, t, renderer=None):
        """Render the frame at t seconds into .image (the engine's update(t, renderer); every update_every-th call
        renders, the others keep the last frame)."""
        n = self._frames
        self._frames += 1
        if n % self.update_every != 0:
            return self
        img = self._texels(self.render(t))
        img[..., 3] = 1.0
        if self.image.source != 'GENERATED':
            self.image.source = 'GENERATED'
        self.image.pixels.foreach_set(img.ravel())
        self.image.update()
        # a generated image's pixels are not saved with the .blend unless packed: packed, a build saved now and
        # rendered later shows this frame, not a blank screen
        self.image.pack()
        return self

    def _texels(self, img):
        """The 8-bit sRGB image's values for a shader output (H, W, 4): sRGB-encoded, so that they read back as the
        shader's values in linear light (encoding='linear', the default: what the WebGL engine's sRGB render target
        did to them), or the shader's colours taken as display sRGB (encoding='srgb')."""
        a = np.clip(np.asarray(img, np.float32), 0.0, 1.0)
        if self.encoding == 'linear':
            c = a[..., :3]
            a[..., :3] = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)
        return a

    def set_uniform(self, name, value):
        """The engine's setUniform: 'power' or 'uPower'."""
        u = _uname(name)
        if u not in self.uniforms:
            return self
        cur = self.uniforms[u]
        self.uniforms[u] = tuple(float(x) for x in value) if isinstance(cur, tuple) else float(value)
        return self

    def dispose(self):
        import bpy
        self._shader = None
        if self.image is not None and self.image.users == 0:
            bpy.data.images.remove(self.image)
        self.image = self.texture = None

    # --------------------------------------------------------------------------------------------- the film ----
    def bake(self, frame_start=None, frame_end=None, fps=None, every=None, controls=None, log=print):
        """Render frames frame_start..frame_end (t = (frame - frame_start) / fps) into <cache_dir>/<name>_####.png and
        make .image play them as a sequence (plus a hold copy before the first frame, which an image sequence shows
        ahead of its range). every = update_every: a new frame each N film frames, held between. controls(frame, t)
        -> {uniform: value} sets uniforms before each rendered frame (the engine's per-frame setUniform /
        setCameraPos calls), e.g. an orbiting camera."""
        import bpy
        import OpenImageIO as oiio
        sc = bpy.context.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = fps or sc.render.fps / sc.render.fps_base
        every = max(1, int(every or self.update_every))
        os.makedirs(self.cache_dir, exist_ok=True)
        last = None
        for f in range(fs, fe + 1):
            path = os.path.join(self.cache_dir, f'{self.stem}_{f:04d}.png')
            if (f - fs) % every == 0 or last is None:
                if controls:
                    for k, v in (controls(f, (f - fs) / fps) or {}).items():
                        self.set_uniform(k, v)
                img = self._texels(self.render((f - fs) / fps))[::-1, :, :3]
                last = np.ascontiguousarray((img * 255.0 + 0.5).astype(np.uint8))
            out = oiio.ImageOutput.create(path)
            out.open(path, oiio.ImageSpec(self.width, self.height, 3, 'uint8'))
            out.write_image(last)
            out.close()
            if f == fs:
                import shutil
                shutil.copyfile(path, os.path.join(self.cache_dir, f'{self.stem}_{fs - 1:04d}.png'))
        first = os.path.join(self.cache_dir, f'{self.stem}_{fs:04d}.png')
        old = self.image
        img = bpy.data.images.load(first, check_existing=False)
        img.name = self.name + '_seq'
        img.source = 'SEQUENCE'
        img.colorspace_settings.name = 'sRGB'
        self.image = self.texture = img
        self.sequence = (fs, fe)
        for mat in bpy.data.materials:
            if mat.node_tree is None:
                continue
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image == old:
                    node.image = img
                    self._sequence_user(node.image_user)
        if log:
            log(f'[sdf.texture] {self.name}: baked frames {fs}..{fe} -> {self.cache_dir}')
        return self

    def _sequence_user(self, iu):
        fs, fe = self.sequence
        iu.frame_duration = fe - fs + 1
        iu.frame_start = fs
        iu.frame_offset = fs - 1
        iu.use_auto_refresh = True
        iu.use_cyclic = False

    def material(self, name=None, emission_strength=0.9, roughness=0.5, metallic=0.0):
        """A Principled material showing the texture as colour and as emission (the engine's documented use:
        MeshStandardMaterial({ map, emissiveMap, emissive: 0xffffff, emissiveIntensity: 0.9 }))."""
        import bpy
        mat = bpy.data.materials.new(name or self.name + '_screen')
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes['Principled BSDF']
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = self.image
        tex.interpolation = 'Linear'
        tex.extension = 'EXTEND'
        if self.sequence is not None:
            self._sequence_user(tex.image_user)
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        nt.links.new(tex.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = float(emission_strength)
        b.inputs['Roughness'].default_value = float(roughness)
        b.inputs['Metallic'].default_value = float(metallic)
        return mat


def make_sdf_texture(opts=None, **kwargs):
    """The engine's makeSdfTexture(opts): recipe ('mandelbulb' | 'sierpinski_tetra' | 'menger_sponge' | 'gyroid'),
    width, height, aspect, uniforms, camera_orbit_radius / _speed, camera_pitch, camera_fov, camera_target,
    custom_de / custom_shade (GLSL), update_every, anisotropy. camelCase keys are accepted as the engine spelled
    them. Extra: name, cache_dir, samples (jittered passes per frame), encoding ('linear', the default: the engine's
    look, as its sRGB render target stored the shader's values; 'srgb': the values as display colours, darker)."""
    o = dict(opts or {})
    o.update(kwargs)
    o = {_CAMEL_OPTS.get(k, k): v for k, v in o.items()}
    return SdfTexture(**o)


# ============================================================================================ explosion texture ====
# The backup's EXPLOSION_FRAGMENT_SHADER, as written. Its uniforms (uRes, uTime, uCamPos, uCamTarget) arrive as macros
# over the uniform block, so their declarations and `precision` are left out; gl_FragColor is sdfTexColor; and the
# pixel position takes the supersampling jitter (zero for the first sample, the engine's one sample per texel).
# The animation is a 15-second loop:
#     0.00-0.05  initial flash, the cap forms at the ground
#     0.05-0.40  the cap rises fast, the stem extends
#     0.40-0.85  the cloud expands and billows
#     0.85-1.00  dissipation and fade
EXPLOSION_FRAGMENT_SHADER = r"""
float hash(vec3 p){
  p = fract(p*0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x*p.y*p.z*(p.x+p.y+p.z));
}
float vnoise(vec3 p){
  vec3 i = floor(p); vec3 f = fract(p); f = f*f*(3.0 - 2.0*f);
  float a = hash(i + vec3(0,0,0)); float b = hash(i + vec3(1,0,0));
  float c = hash(i + vec3(0,1,0)); float d = hash(i + vec3(1,1,0));
  float e = hash(i + vec3(0,0,1)); float g = hash(i + vec3(1,0,1));
  float h = hash(i + vec3(0,1,1)); float k = hash(i + vec3(1,1,1));
  return mix(mix(mix(a,b,f.x), mix(c,d,f.x), f.y),
             mix(mix(e,g,f.x), mix(h,k,f.x), f.y), f.z);
}
float fbm(vec3 p){
  float f = 0.0, amp = 0.5;
  for(int i = 0; i < 5; i++){ f += amp*vnoise(p); p = p*2.07 + vec3(13.1, 7.3, 19.2); amp *= 0.5; }
  return f;
}
float smin_cubic(float a, float b, float k){
  float h = max(k - abs(a-b), 0.0)/k;
  return min(a, b) - h*h*h*k*(1.0/6.0);
}
float ridgeFbm(vec3 p, float t){
  float sum = 0.0; float a = 0.8;
  for(int i = 0; i < 7; i++){
    float c = cos(4.0), s = sin(4.0);
    vec2 xz = mat2(c, -s, s, c) * p.xz; p.x = xz.x; p.z = xz.y;
    sum += exp(sin(p.z / a + t * 0.5) - 3.0) * a;
    sum += exp(sin(p.x / a + t * 0.3) - 3.0) * a * 0.6;
    a *= 0.8;
  }
  return sum;
}
float easeOutCubic(float t){ return 1.0 - pow(1.0 - t, 3.0); }
const float LOOP = 15.0;
float sdStem(vec3 p, float stemTop, float baseR, float topR, float t){
  float y = clamp(p.y, 0.0, stemTop);
  float h = y / max(stemTop, 0.001);
  float r = mix(baseR, topR, pow(h, 0.7));
  vec3 q = p; float swirl = fbm(vec3(q.xz * 0.6, q.y * 0.4 + t * 0.3));
  r += (swirl - 0.5) * 0.4 * h;
  float radial = length(p.xz) - r;
  float yClip = max(p.y - stemTop, -p.y);
  return max(radial, yClip);
}
float sdCap(vec3 p, vec3 capCenter, float capR, float t){
  vec3 q = p - capCenter;
  float n1 = fbm(q * 0.45 + vec3(0.0, t * 0.15, t * 0.08));
  float n2 = fbm(q * 1.2  + vec3(t * 0.2, 0.0, -t * 0.1));
  float disp = n1 * 0.55 + n2 * 0.25;
  float ridge = ridgeFbm(q * 0.6, t); disp += ridge * 1.4;
  vec3 qStretch = q / vec3(1.0, 0.78, 1.0);
  return length(qStretch) - capR - disp * 0.85 + 0.25;
}
float sdSmokeTrail(vec3 p, float trailY, float trailR, float t){
  vec3 q = p - vec3(0.0, trailY, 0.0);
  float n = fbm(q * 0.5 + vec3(0.0, t * 0.12, 0.0));
  float r = trailR + n * 0.6 * trailR;
  return length(q / vec3(1.3, 0.9, 1.3)) - r;
}
float sdBaseSurge(vec3 p, float t, float surgeR, float ringTube, float padH){
  float radial = length(p.xz) - surgeR;
  float n1 = fbm(vec3(p.xz * 0.30, t * 0.4));
  float n2 = fbm(vec3(p.xz * 0.80, t * 0.6));
  float ringDisp = n1 * 0.8 + n2 * 0.4;
  float effRingTube = ringTube + ringDisp * 0.7;
  float dRing = length(vec2(radial, p.y - ringTube * 0.6)) - effRingTube;
  float innerR = surgeR - ringTube * 0.4;
  float heightAtR = padH * smoothstep(innerR, innerR * 0.2, length(p.xz));
  float padN = fbm(vec3(p.xz * 0.4, t * 0.3));
  float effInnerR = innerR + padN * 0.8;
  float padRadial = length(p.xz) - effInnerR;
  float padY = max(p.y - heightAtR, -p.y);
  float dPad = max(padRadial, padY);
  return smin_cubic(dRing, dPad, 0.6);
}
vec2 mapScene(vec3 p, float t){
  float tn = mod(uTime, LOOP) / LOOP;
  float capY = mix(1.0, 9.0, easeOutCubic(min(tn / 0.6, 1.0))) + tn * 1.2;
  float capR = mix(0.4, 3.4, easeOutCubic(min(tn / 0.5, 1.0))) + tn * 0.3;
  float stemTop = capY - 0.6;
  float stemBaseR = mix(0.25, 0.9, easeOutCubic(min(tn / 0.4, 1.0)));
  float stemTopR  = mix(0.6, 1.6, easeOutCubic(min(tn / 0.5, 1.0)));
  float dStem = sdStem(p, stemTop, stemBaseR, stemTopR, t);
  float dCap = sdCap(p, vec3(0.0, capY, 0.0), capR, t);
  float dCloud = smin_cubic(dStem, dCap, 0.6);
  float trailRise = clamp((tn - 0.10) / 0.5, 0.0, 1.0);
  float trailY = mix(1.0, capY * 0.60, trailRise);
  float trailR = mix(0.3, 1.7, trailRise);
  if(trailRise > 0.001){
    float dSmoke = sdSmokeTrail(p, trailY, trailR, t);
    dCloud = smin_cubic(dCloud, dSmoke, mix(0.3, 1.0, trailRise));
  }
  float surgeR   = mix(2.0, 16.0, easeOutCubic(min(tn / 0.7, 1.0))) + tn * 4.0;
  float ringPeak = smoothstep(0.0, 0.4, tn);
  float ringFade = 1.0 - smoothstep(0.4, 1.0, tn);
  float ringTube = mix(0.4, 2.2, ringPeak) * mix(0.15, 1.0, ringFade);
  float padH     = mix(0.6, 1.8, easeOutCubic(min(tn / 0.5, 1.0))) * mix(0.3, 1.0, ringFade);
  float dSurge   = sdBaseSurge(p, t, surgeR, ringTube, padH);
  dCloud = smin_cubic(dCloud, dSurge, mix(0.3, 1.0, ringFade));
  float heightTerm = exp(-p.y * 0.18);
  float axialTerm  = exp(-length(p.xz) * 0.4);
  float coreTerm   = exp(-length(p - vec3(0.0, 1.5, 0.0)) * 0.25);
  float temp = clamp(0.55 * heightTerm * axialTerm + 0.6 * coreTerm, 0.0, 1.0);
  float colorNoise = fbm(p * 0.35 + vec3(0.0, t * 0.2, t * 0.15));
  float perturb = (colorNoise - 0.5) * 0.45;
  float perturbStrength = 1.0 - smoothstep(0.5, 0.85, temp);
  temp = clamp(temp + perturb * perturbStrength, 0.0, 1.0);
  float coolFactor = 1.0 - smoothstep(0.7, 1.0, tn);
  temp *= coolFactor;
  return vec2(dCloud, temp);
}
vec3 calcNormal(vec3 p){
  const float e = 0.01;
  vec2 h = vec2(1.0, -1.0) * 0.5773;
  return normalize(
    h.xyy * mapScene(p + e*h.xyy, uTime).x +
    h.yyx * mapScene(p + e*h.yyx, uTime).x +
    h.yxy * mapScene(p + e*h.yxy, uTime).x +
    h.xxx * mapScene(p + e*h.xxx, uTime).x);
}
vec3 skyColor(vec3 rd){
  float horizon = 1.0 - max(rd.y, 0.0);
  vec3 zenith  = vec3(0.015, 0.020, 0.040);
  vec3 horizonCol = vec3(0.08, 0.04, 0.05);
  return mix(zenith, horizonCol, pow(horizon, 4.0));
}
vec3 fireRamp(float t){
  vec3 c0 = vec3(0.020, 0.018, 0.018);
  vec3 c1 = vec3(0.10, 0.08, 0.07);
  vec3 c2 = vec3(0.40, 0.18, 0.08);
  vec3 c3 = vec3(1.40, 0.50, 0.12);
  vec3 c4 = vec3(2.30, 1.20, 0.40);
  vec3 c5 = vec3(3.20, 2.20, 1.10);
  if(t < 0.2)  return mix(c0, c1, t / 0.2);
  if(t < 0.4)  return mix(c1, c2, (t - 0.2) / 0.2);
  if(t < 0.6)  return mix(c2, c3, (t - 0.4) / 0.2);
  if(t < 0.8)  return mix(c3, c4, (t - 0.6) / 0.2);
  return mix(c4, c5, (t - 0.8) / 0.2);
}
void main(){
  vec2 fc = gl_FragCoord.xy + 0.5 * sdfTexJitter;
  vec2 p = (fc - 0.5*uRes) / uRes.y;
  vec3 ro = uCamPos;
  vec3 fwd = normalize(uCamTarget - uCamPos);
  vec3 rt  = normalize(cross(fwd, vec3(0.0, 1.0, 0.0)));
  vec3 up  = cross(rt, fwd);
  float fov = 1.4;
  vec3 rd = normalize(fwd*fov + rt*p.x + up*p.y);
  vec3 col = vec3(0.0);
  bool hit = false;
  float t = 0.0; float maxT = 200.0;
  vec3 hitPos = ro; float hitTemp = 0.0;
  float accumulated = 0.0; vec3 accumColor = vec3(0.0);
  for(int i = 0; i < 64; i++){
    vec3 q = ro + rd * t;
    vec2 m = mapScene(q, uTime);
    float d = m.x; float temp = m.y;
    if(d < 0.4){
      float density = clamp(1.0 - d / 0.4, 0.0, 1.0);
      vec3 fc2 = fireRamp(temp);
      float contribution = density * 0.05 * (1.0 - accumulated);
      accumColor += fc2 * contribution; accumulated += contribution;
      if(accumulated > 0.95) break;
    }
    if(d < 0.01){ hit = true; hitPos = q; hitTemp = temp; break; }
    t += max(d * 0.7, 0.08);
    if(t > maxT) break;
  }
  if(hit){
    vec3 base = fireRamp(hitTemp);
    vec3 n = calcNormal(hitPos);
    vec3 toCore = normalize(vec3(0.0, 1.5, 0.0) - hitPos);
    float coreGlow = max(dot(n, toCore), 0.0);
    base *= 0.7 + 0.6 * coreGlow;
    col = base + accumColor;
  } else {
    col = skyColor(rd) + accumColor;
  }
  float horizonHaze = exp(-max(rd.y, -0.2) * 3.0) * 0.06;
  col += horizonHaze * vec3(0.8, 0.3, 0.1);
  col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
  col = pow(clamp(col, 0.0, 1.0), vec3(1.0/2.2));
  vec2 vc = (fc / uRes - 0.5);
  float vig = 1.0 - dot(vc, vc) * 0.6;
  col *= vig;
  sdfTexColor = vec4(col, 1.0);
}
"""

EXPLOSION_LOOP_SECONDS = 15.0

_EXPLOSION_CAMEL = {'cameraPos': 'camera_pos', 'cameraTarget': 'camera_target', 'updateEvery': 'update_every',
                    'timeScale': 'time_scale', 'timeOffset': 'time_offset'}


class ExplosionTexture(SdfTexture):
    """What make_explosion_texture returns: the SdfTexture contract (.image / .texture, update(t), bake(), material(),
    dispose()) around the engine's mushroom-cloud shader, plus set_camera_pos / set_camera_target. The shader's own
    time is t * time_scale + time_offset, as the engine's update(t) set it."""

    _SWIZZLE = dict(SdfTexture._SWIZZLE, uRes='.xy', uCamPos='.xyz', uCamTarget='.xyz')

    def __init__(self, width=512, height=512, camera_pos=(18.0, 7.0, 22.0), camera_target=(0.0, 5.0, 0.0),
                 update_every=1, time_scale=1.0, time_offset=0.0, name=None, cache_dir='//sdf_cache', samples=1,
                 encoding='linear'):
        import bpy
        self.encoding = _check_encoding(encoding)
        self.recipe = 'explosion'
        self.width = int(width) or 512
        self.height = int(height) or 512
        self.aspect = self.width / self.height
        self.update_every = max(1, int(update_every or 1))
        self.time_scale = 1.0 if time_scale is None else float(time_scale)
        self.time_offset = 0.0 if time_offset is None else float(time_offset)
        self.anisotropy = None
        self.samples = max(1, int(samples))
        self.name = name or 'sdf_tex_explosion'
        self.cache_dir = resolve_cache_dir(cache_dir)
        self.uniforms = {'uRes': (float(self.width), float(self.height)), 'uTime': 0.0,
                         'uCamPos': tuple(float(x) for x in camera_pos),
                         'uCamTarget': tuple(float(x) for x in camera_target)}
        self._user = []
        self.de = ''
        self.custom_shade = None
        self._shader = None
        self._frames = 0
        self.image = bpy.data.images.new(self.name, self.width, self.height, alpha=False, float_buffer=False)
        self.image.colorspace_settings.name = 'sRGB'
        self.texture = self.image
        self.sequence = None
        self.stem = file_stem(self.image.name)

    def _layout(self):
        return ['uRes', 'uTime', 'uCamPos', 'uCamTarget', 'sdfTexSize', 'sdfTexJitter']

    def source(self):
        return self._uniform_macros() + '\n' + EXPLOSION_FRAGMENT_SHADER

    def render(self, t):
        """The shader at film time t (its own clock: t * time_scale + time_offset), (H, W, 4), row 0 at the bottom.
        The shader tone-maps and gamma-encodes itself, so its values were written as display colours; the engine's
        sRGB render target read them as linear light (see the module's note on encoding)."""
        return super().render(float(t) * self.time_scale + self.time_offset)

    def set_camera_pos(self, x, y=None, z=None):
        """The engine's setCameraPos(x, y, z): the shader camera, in its own y-up frame (default (18, 7, 22))."""
        self.uniforms['uCamPos'] = tuple(float(v) for v in ((x, y, z) if y is not None else x))
        return self

    def set_camera_target(self, x, y=None, z=None):
        """The engine's setCameraTarget(x, y, z) (default (0, 5, 0))."""
        self.uniforms['uCamTarget'] = tuple(float(v) for v in ((x, y, z) if y is not None else x))
        return self


def make_explosion_texture(opts=None, **kwargs):
    """The engine's makeExplosionTexture(opts) (its GLSL edition; the TSL migration dropped it): an animated
    raymarched mushroom-cloud detonation rendered into an image, on a 15-second loop. Options: width, height (512),
    camera_pos (18, 7, 22), camera_target (0, 5, 0), update_every, time_scale, time_offset; camelCase keys as the
    engine spelled them. Extra: name, cache_dir, samples, encoding. Returns an ExplosionTexture: update(t), bake(fs, fe,
    controls=), set_camera_pos / set_camera_target, material(), dispose(), .image / .texture."""
    o = dict(opts or {})
    o.update(kwargs)
    o = {_EXPLOSION_CAMEL.get(k, k): v for k, v in o.items()}
    return ExplosionTexture(**o)
