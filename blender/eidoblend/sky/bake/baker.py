"""Runs the ported sky shader (sky.glsl) in Blender's own GPU module and returns float images.

Three products per film frame, all from one shader and one uniform set (the sky's `U`):
  camera_layer()  background + clouds for the bake camera's exact screen rays (with overscan)
  camera_layers() the same rays split into layers: background, shield and clouds apart (a sky world's sky
                  elements composite the shield and clouds over themselves; a cloud dome draws the clouds)
  environment()   an equirect in Blender's Environment Texture convention, for EEVEE world lighting
  shadow_map()    transmittance toward the cloud key over a top-down square (the cloud-shadow caster)

The weather map is our own 512^2 1/f field (fbmAt with the same integer hash as the JS), the star map
and the moon are the repo's assets. Draws are split into strips so one frame never holds the GPU long.
A sky world compiles its own variant of the shader: `defines` switch the ring deck, the celestial body, the
shield, the moon dust and the analytic band in the environment (see sky.glsl), and `celestial` / `dust` carry
the GLSL bake/celestial.py generates for the world's authored constants.
"""
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WSZ = 512

# (glsl name, push-constant type, source): a str is a key of the sky's U; None is set per render
UNIFORMS = [
    ('uTime', 'FLOAT', 'time'), ('uSunDir', 'VEC3', 'sunDir'), ('uLightDir', 'VEC3', 'cloudLightDir'),
    ('uLightColor', 'VEC3', 'cloudLightColor'), ('uAmbSky', 'VEC3', 'cloudAmbSky'),
    ('uAmbGround', 'VEC3', 'cloudAmbGround'), ('uZenith', 'VEC3', 'zenith'), ('uHorizon', 'VEC3', 'horizon'),
    ('uSunColor', 'VEC3', 'sunColor'), ('uSunDiscI', 'FLOAT', 'sunDiscI'), ('uSolarVis', 'FLOAT', 'solarVisibility'),
    ('uSolarSkyVis', 'FLOAT', 'solarSkyVisibility'), ('uSunGlowI', 'FLOAT', 'sunGlowI'),
    ('uStarFade', 'FLOAT', 'starFade'), ('uSkyGlow', 'VEC3', 'skyGlow'), ('uMoonDir', 'VEC3', 'moonDir'),
    ('uMoonRight', 'VEC3', 'moonRight'), ('uMoonUp', 'VEC3', 'moonUp'), ('uMoonCos', 'FLOAT', 'moonCos'),
    ('uMoonLightK', 'FLOAT', 'moonLightK'), ('uLargeT', 'FLOAT', 'largeT'), ('uLargeA', 'FLOAT', 'largeA'),
    ('uWeatherT', 'FLOAT', 'weatherT'), ('uFinalMul', 'FLOAT', 'finalMul'), ('uWScale', 'FLOAT', 'wScale'),
    ('uDScale', 'FLOAT', 'dScale'), ('uCloudStart', 'FLOAT', 'cloudStart'), ('uCloudHeight', 'FLOAT', 'cloudHeight'),
    ('uStretch', 'VEC3', 'stretch'), ('uLightK', 'FLOAT', 'lightK'), ('uLightCacheDirect', 'FLOAT', 'lightCacheDirect'),
    ('uCloudTint', 'VEC3', 'cloudTint'), ('uCloudDim', 'FLOAT', 'cloudDim'), ('uCloudRadiance', 'FLOAT', 'cloudRadiance'),
    ('uWeatherGrey', 'FLOAT', 'cloudWeatherGrey'), ('uCloudRadianceScale', 'FLOAT', 'cloudRadianceScale'),
    ('uWispColor', 'VEC3', 'wispColor'), ('uWispStretch', 'VEC3', 'wispStretch'), ('uWispOn', 'FLOAT', 'wispOn'),
    ('uWispScale', 'FLOAT', 'wispScale'), ('uWispThreshold', 'FLOAT', 'wispThreshold'),
    ('uWispStrength', 'FLOAT', 'wispStrength'), ('uWispOpacity', 'FLOAT', 'wispOpacity'),
    ('uWispFloor', 'FLOAT', 'wispFloor'), ('uWispFilament', 'FLOAT', 'wispFilament'),
    ('uStormCanopy', 'FLOAT', 'stormCanopy'), ('uCelestialVis', 'FLOAT', 'celestialVisibility'),
    ('uFlashColor', 'VEC3', 'lightningFlashColor'), ('uStrike', 'VEC4', 'lightningStrike'),
    ('uShaftK', 'FLOAT', 'shaftK'), ('uShaftDen', 'FLOAT', 'shaftDen'), ('uPrecipK', 'FLOAT', 'precipK'),
    ('uPrecipLo', 'FLOAT', 'precipLo'), ('uPrecipHi', 'FLOAT', 'precipHi'), ('uDisp', 'VEC3', 'cloudDisplacement'),
    ('uSkyWind', 'VEC3', 'skyWind'), ('uWallCloud', 'VEC4', 'wallCloud'), ('uFadeDist', 'FLOAT', 'fadeDist'),
    ('uCloudShadowStrength', 'FLOAT', 'cloudShadowStrength'),
    # the red giant and its shield (redgiant.js uniforms: starDir/Right/Up, starT, the impact slots)
    ('uStarDir', 'VEC3', 'starDir'), ('uStarRight', 'VEC3', 'starRight'), ('uStarUp', 'VEC3', 'starUp'),
    ('uStarT', 'FLOAT', 'starT'), ('uFlareBoost', 'FLOAT', 'flareBoost'), ('uStarTint', 'VEC3', 'starTint'),
    ('uShieldColor', 'VEC3', 'shieldColorU'), ('uImpact', 'VEC4[5]', 'impacts'),
    # the shattered moon's dust (asteroid_moon.js march uniforms, in the dust's own frame)
    ('uDustOrigin', 'VEC3', 'dustOrigin'), ('uDustM0', 'VEC3', 'dustM0'), ('uDustM1', 'VEC3', 'dustM1'),
    ('uDustM2', 'VEC3', 'dustM2'), ('uDustSunL', 'VEC3', 'dustSunL'), ('uDustT', 'FLOAT', 'dustT'),
    ('uDustSunCol', 'VEC3', 'dustSunCol'), ('uDustGain', 'FLOAT', 'dustGain'), ('uDustFade', 'FLOAT', 'dustFade'),
    ('uPlume', 'VEC4[3]', 'plumes'), ('uPieceL', 'VEC4[16]', 'pieces'),
    # options and per-render values
    ('uOutput', 'INT', None),
    ('uPhaseSoften', 'FLOAT', None), ('uMsFloor', 'FLOAT', None),
    ('uMode', 'INT', None), ('uWithDisc', 'INT', None), ('uHasStars', 'INT', None), ('uHasMoon', 'INT', None),
    ('uHasCirrus', 'INT', None), ('uSize', 'VEC2', None), ('uOrg', 'VEC3', None), ('uCamRight', 'VEC3', None),
    ('uCamUp', 'VEC3', None), ('uCamBack', 'VEC3', None), ('uTanHalf', 'VEC2', None), ('uJitterSeed', 'VEC2', None),
    ('uTransientLight', 'FLOAT', None), ('uBelowHorizonDim', 'FLOAT', None), ('uShadowExtent', 'FLOAT', None),
    ('uShadowY', 'FLOAT', None),
]


def _whash(i, j, s):
    """The JS wHash: (i*374761393 + j*668265263 + s*2246822519) >>> 0, imul-mix, /2^32 (exact in uint64)."""
    n = (i.astype(np.uint64) * np.uint64(374761393) + j.astype(np.uint64) * np.uint64(668265263)
         + np.uint64(s) * np.uint64(2246822519)) & np.uint64(0xFFFFFFFF)
    n = ((n ^ (n >> np.uint64(13))) * np.uint64(1274126177)) & np.uint64(0xFFFFFFFF)
    n = (n ^ (n >> np.uint64(16))) & np.uint64(0xFFFFFFFF)
    return n.astype(np.float64) / 4294967296.0


def _fbm_at(uu, vv, seed_base, base_cells=8):
    val = np.zeros_like(uu)
    amp, cells, norm = 0.5, base_cells, 0.0
    for o in range(5):
        x, y = uu * cells, vv * cells
        xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
        xf, yf = x - xi, y - yi
        sx = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
        sy = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        w = lambda a, b: _whash(((a % cells) + cells) % cells, ((b % cells) + cells) % cells, seed_base + o)
        w00, w10, w01, w11 = w(xi, yi), w(xi + 1, yi), w(xi, yi + 1), w(xi + 1, yi + 1)
        n0 = w00 + (w10 - w00) * sx
        n1 = w01 + (w11 - w01) * sx
        val += amp * (n0 + (n1 - n0) * sy)
        norm += amp
        amp *= 0.55
        cells *= 2
    return np.clip(((val / norm) - 0.5) * 1.9 + 0.5, 0.0, 1.0)


def weather_map():
    """The 512^2 weather map exactly as the JS fills its Uint8 texture: .r macro coverage, .g puff field."""
    wy, wx = np.mgrid[0:WSZ, 0:WSZ].astype(np.float64)
    uu, vv = wx / WSZ, wy / WSZ
    out = np.zeros((WSZ, WSZ, 4), np.float32)
    out[..., 0] = np.floor(_fbm_at(uu, vv, 11) * 255) / 255.0
    out[..., 1] = np.floor(_fbm_at(uu, vv, 137, 32) * 255) / 255.0
    out[..., 3] = 1.0
    return out


def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


LINEAR_FILES = ('.exr', '.hdr')


def load_image_rgba(path, srgb):
    """Pixels of an image file as float32 (H, W, 4), row 0 at the bottom (Blender/GL order), linear. srgb: a colour
    map (JPEG, PNG ...) is decoded from sRGB; an OpenEXR or Radiance HDR file is linear already and read as stored."""
    import bpy
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'Non-Color'          # raw stored values; linearize ourselves
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    if srgb and not path.lower().endswith(LINEAR_FILES):
        px[..., :3] = _srgb_to_linear(px[..., :3])
    bpy.data.images.remove(img)
    return px


def _uniform_rows(entry):
    """How many vec4 rows of the uniform block an UNIFORMS entry takes (an array 'VEC4[n]' takes n)."""
    typ = entry[1]
    return int(typ[5:-1]) if typ.startswith('VEC4[') else 1


class SkyBaker:
    def __init__(self, stars=None, moon=None, cirrus=None, n_march=60, n_light=20, m_pass=8, n_storm_steps=12,
                 n_cloud_shadow=64, phase_soften=0.0, ms_floor=0.008, strip_rows=48, defines=None, celestial='',
                 dust='', ring_map=None, ring_mask=None):
        """defines: the sky world's switches and constants (sky.glsl's RING_ON, HAS_CELESTIAL, R_EARTH ...); celestial
        / dust: GLSL (bake/celestial.py generates the red giant's and the dust's); ring_map / ring_mask: the band's
        albedo map and land mask for the analytic band in the environment (HAS_RING_ENV). n_storm_steps: the storm
        layer's march (opts.stormSamples, at least 4; the JS's two interleaved passes stay); n_cloud_shadow: the
        cloud-shadow march (opts.cloudShadowSamples, Eanpa's 32-64)."""
        self.paths = dict(stars=stars, moon=moon, cirrus=cirrus, ring_map=ring_map, ring_mask=ring_mask)
        self.defines = dict(N_MARCH=n_march, N_LIGHT=n_light, M_PASS=max(1, m_pass),
                            N_STORM_STEPS=max(4, int(round(n_storm_steps))), N_STORM_PASSES=2,
                            N_CLOUD_SHADOW=max(32, min(64, int(round(n_cloud_shadow)))), N_SHIELD_OCC=24)
        self.defines.update(defines or {})
        self.celestial_src = celestial
        self.dust_src = dust
        self.phase_soften = phase_soften
        self.ms_floor = ms_floor
        self.strip_rows = strip_rows
        self.shader = None
        self.batch = None
        self.tex = {}
        self.weather = None

    def has(self, flag):
        return int(float(self.defines.get(flag, 0))) != 0

    # ---- GPU resources ----
    def _texture(self, arr, fmt='RGBA16F', repeat=True):
        import gpu
        h, w = arr.shape[:2]
        buf = gpu.types.Buffer('FLOAT', w * h * 4, np.ascontiguousarray(arr, np.float32).ravel())
        t = gpu.types.GPUTexture((w, h), format=fmt, data=buf)
        t.filter_mode(True)
        t.extend_mode('REPEAT' if repeat else 'EXTEND')
        return t

    def ensure(self):
        if self.shader is not None:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        try:
            gpu.init()
        except Exception:
            pass
        self.weather = weather_map()
        self.tex['weather'] = self._texture(self.weather, 'RGBA32F', repeat=True)
        dummy = np.zeros((2, 2, 4), np.float32)
        for key in ('stars', 'moon', 'cirrus', 'ring_map', 'ring_mask'):
            p = self.paths.get(key)
            if p and os.path.exists(p):
                arr = load_image_rgba(p, srgb=(key in ('stars', 'moon', 'ring_map')))
                self.tex[key] = self._texture(arr, 'RGBA16F', repeat=True)
                self.tex[key + '_ok'] = True
            else:
                self.tex[key] = self._texture(dummy, 'RGBA16F')
                self.tex[key + '_ok'] = False
        # every uniform lives in its own vec4 of one uniform buffer (std140-safe, any backend); macros give
        # the shader its TSL names back (an array uniform is a function-like macro over its rows)
        rows = sum(_uniform_rows(e) for e in UNIFORMS)
        info = gpu.types.GPUShaderCreateInfo()
        info.typedef_source('struct SkyParams { vec4 v[%d]; };' % rows)
        info.uniform_buf(0, 'SkyParams', 'P')
        swz = dict(FLOAT='.x', VEC2='.xy', VEC3='.xyz', VEC4='', INT='.x')
        macros = []
        row = 0
        for entry in UNIFORMS:
            name, typ = entry[0], entry[1]
            if typ.startswith('VEC4['):
                macros.append('#define %s(i) (P.v[%d + (i)])' % (name, row))
            else:
                ref = 'P.v[%d]%s' % (row, swz[typ])
                macros.append('#define %s %s' % (name, ('int(%s)' % ref) if typ == 'INT' else '(%s)' % ref))
            row += _uniform_rows(entry)
        info.sampler(0, 'FLOAT_2D', 'weatherTex')
        info.sampler(1, 'FLOAT_2D', 'starTex')
        info.sampler(2, 'FLOAT_2D', 'moonTex')
        info.sampler(3, 'FLOAT_2D', 'cirrusTex')
        if self.has('HAS_RING_ENV'):
            info.sampler(4, 'FLOAT_2D', 'ringMapTex')
            info.sampler(5, 'FLOAT_2D', 'ringMaskTex')
        info.vertex_in(0, 'VEC2', 'pos')
        info.fragment_out(0, 'VEC4', 'FragColor')
        for k, v in self.defines.items():
            # ints (counts, switches) stay ints; floats are written as GLSL float literals
            info.define(k, v if isinstance(v, str) else str(int(v)) if isinstance(v, (bool, int)) else repr(float(v)))
        info.vertex_source('void main() { gl_Position = vec4(pos, 0.0, 1.0); }')
        with open(os.path.join(HERE, 'sky.glsl'), encoding='utf-8') as f:
            src = f.read()
        src = src.replace('//@@CELESTIAL@@', self.celestial_src or '').replace('//@@DUST@@', self.dust_src or '')
        info.fragment_source('\n'.join(macros) + '\n' + src)
        self.shader = gpu.shader.create_from_info(info)
        self.batch = batch_for_shader(self.shader, 'TRIS', {'pos': [(-1, -1), (3, -1), (-1, 3)]})

    # ---- one draw ----
    def _render(self, U, width, height, per):
        import gpu
        self.ensure()
        sh = self.shader
        off = gpu.types.GPUOffScreen(width, height, format='RGBA32F')
        out = np.empty((height, width, 4), np.float32)
        rows = sum(_uniform_rows(e) for e in UNIFORMS)
        block = np.zeros((rows, 4), np.float32)
        row = 0
        for entry in UNIFORMS:
            name, typ, src = entry
            n = _uniform_rows(entry)
            v = per.get(name) if src is None else U.get(src)       # a world uniform another world lacks: zeros
            if v is None:
                row += n
                continue
            if n > 1:
                for k, item in enumerate(list(v)[:n]):
                    item = [float(x) for x in item]
                    block[row + k, :len(item)] = item
            else:
                v = [float(v)] if isinstance(v, (int, float)) else [float(x) for x in v]
                block[row, :len(v)] = v
            row += n
        ubo = gpu.types.GPUUniformBuf(gpu.types.Buffer('FLOAT', block.size, block.ravel()))
        try:
            with off.bind():
                fb = gpu.state.active_framebuffer_get()
                fb.clear(color=(0.0, 0.0, 0.0, 0.0))
                sh.bind()
                sh.uniform_block('P', ubo)
                sh.uniform_sampler('weatherTex', self.tex['weather'])
                sh.uniform_sampler('starTex', self.tex['stars'])
                sh.uniform_sampler('moonTex', self.tex['moon'])
                sh.uniform_sampler('cirrusTex', self.tex['cirrus'])
                if self.has('HAS_RING_ENV'):
                    sh.uniform_sampler('ringMapTex', self.tex['ring_map'])
                    sh.uniform_sampler('ringMaskTex', self.tex['ring_mask'])
                gpu.state.scissor_test_set(True)
                y = 0
                while y < height:
                    rows = min(self.strip_rows, height - y)
                    gpu.state.scissor_set(0, y, width, rows)
                    self.batch.draw(sh)
                    fb.read_color(0, y, 1, 1, 4, 0, 'FLOAT')     # wait for the strip: no long GPU hold
                    y += rows
                gpu.state.scissor_test_set(False)
                buf = fb.read_color(0, 0, width, height, 4, 0, 'FLOAT')
                out[:] = np.asarray(buf, dtype=np.float32).reshape(height, width, 4)
        finally:
            off.free()
        return out

    def _common(self):
        self.ensure()
        return dict(uPhaseSoften=self.phase_soften, uMsFloor=self.ms_floor,
                    uHasStars=int(self.tex['stars_ok']), uHasMoon=int(self.tex['moon_ok']),
                    uHasCirrus=int(self.tex['cirrus_ok']), uTransientLight=1.0, uBelowHorizonDim=0.45,
                    uShadowExtent=6144.0, uShadowY=0.0, uJitterSeed=(0.0, 0.0),
                    uCamRight=(1, 0, 0), uCamUp=(0, 0, 1), uCamBack=(0, -1, 0), uTanHalf=(1, 1), uOrg=(0, 2, 0))

    def camera_layer(self, U, cam_basis, tan_half, origin_three, width, height, with_disc=True, jitter_seed=(0, 0),
                     output=0):
        """cam_basis = (right, up, back) Blender world vectors of the camera; tan_half = (tan x, tan y).
        output: 0 composite, 1 clouds alone (premultiplied), 2 background alone, 3 shield alone (premultiplied)."""
        per = self._common()
        per.update(uMode=0, uWithDisc=int(with_disc), uSize=(width, height), uOrg=origin_three,
                   uCamRight=cam_basis[0], uCamUp=cam_basis[1], uCamBack=cam_basis[2], uTanHalf=tan_half,
                   uJitterSeed=jitter_seed, uTransientLight=1.0, uOutput=int(output))
        return self._render(U, width, height, per)

    def camera_layers(self, U, cam_basis, tan_half, origin_three, width, height, with_disc=True):
        """The camera rays as separate layers, one pass each: {'cloud', 'back', 'cam'} (+ 'shield' with HAS_SHIELD).

        cloud: the clouds alone, premultiplied RGBA (the expensive march, once); back: the sky behind them (background,
        celestial body, moon dust, and the shield over them); cam: the clouds over back, alpha the cloud cover, the
        same image camera_layer(output=0) renders."""
        args = (U, cam_basis, tan_half, origin_three, width, height, with_disc)
        cloud = self.camera_layer(*args, output=1)
        bg = self.camera_layer(*args, output=2)
        back = bg.copy()
        out = dict(cloud=cloud)
        if self.has('HAS_SHIELD'):
            shield = self.camera_layer(*args, output=3)
            back[..., :3] = shield[..., :3] + (1.0 - shield[..., 3:4]) * bg[..., :3]
            out['shield'] = shield
        back[..., 3] = 1.0
        cam = np.empty_like(cloud)
        cam[..., :3] = cloud[..., :3] + (1.0 - cloud[..., 3:4]) * back[..., :3]
        cam[..., 3] = cloud[..., 3]
        out.update(back=back, cam=cam)
        return out

    def environment(self, U, width, height, origin_three=(0.0, 2.0, 0.0), with_disc=False, include_flash=False):
        per = self._common()
        per.update(uMode=1, uWithDisc=int(with_disc), uSize=(width, height), uOrg=origin_three,
                   uTransientLight=1.0 if include_flash else 0.0, uBelowHorizonDim=0.45)
        return self._render(U, width, height, per)

    def shadow_map(self, U, size, centre_three, extent=6144.0, ground_y=0.0):
        per = self._common()
        per.update(uMode=2, uWithDisc=0, uSize=(size, size), uOrg=centre_three, uShadowExtent=extent,
                   uShadowY=ground_y)
        return self._render(U, size, size, per)

    # ---- CPU access to the same weather field (weatherAt) ----
    def weather_at(self, U, x, z):
        if self.weather is None:
            self.weather = weather_map()
        sc = 0.00005 * U['wScale']
        drift = U['cloudDisplacement']
        uu = ((-((z - drift[2]) * sc)) % 1.0) * WSZ
        vv = ((-((x - drift[0]) * sc)) % 1.0) * WSZ
        x0, y0 = int(math.floor(uu)) % WSZ, int(math.floor(vv)) % WSZ
        x1, y1 = (x0 + 1) % WSZ, (y0 + 1) % WSZ
        fx, fy = uu - math.floor(uu), vv - math.floor(vv)
        r = self.weather[..., 0]
        val = (r[y0, x0] * (1 - fx) + r[y0, x1] * fx) * (1 - fy) + (r[y1, x0] * (1 - fx) + r[y1, x1] * fx) * fy
        return max(0.0, min(2.0, (val - U['largeT']) * U['largeA']))


def write_exr(path, arr, channels='RGBA', half=True):
    """Float image (H, W, C), row 0 at the bottom, to an EXR (OpenImageIO bundled with Blender)."""
    import OpenImageIO as oiio
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.ascontiguousarray(arr[::-1, :, :len(channels)])      # EXR rows run top-down
    h, w, c = data.shape
    spec = oiio.ImageSpec(w, h, c, 'half' if half else 'float')
    spec.channelnames = tuple(channels)
    spec.attribute('compression', 'zip')
    out = oiio.ImageOutput.create(path)
    if out is None:
        raise RuntimeError('cannot write ' + path)
    out.open(path, spec)
    out.write_image(data)
    out.close()
