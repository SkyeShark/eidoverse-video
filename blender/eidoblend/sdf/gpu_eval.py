"""SdfProgram: an example's GLSL compiled into Blender's GPU module and evaluated over point lists.

Blender 5.2 has no compute shaders from Python, so every kernel is a fragment pass: the points to evaluate are an
RGBA32F texture (one point per texel), a full-screen triangle runs the kernel once per texel, and up to six RGBA32F
colour targets come back as numpy arrays. Long passes are drawn in scissored strips with a one-pixel read between
them, so no single submission holds the GPU long (the machine is shared; Windows resets a GPU that hangs ~2 s).

Uniforms (uTime, the example's own, the engine's) live in one uniform buffer of vec4 slots with #define macros
giving each its GLSL name back, the layout the sky baker uses: std140-safe on every backend.

    prog = SdfProgram(map=MAP_GLSL, surface=SURF_GLSL, uniforms={'uPaint': ('vec3', (0.8, 0.8, 0.82))})
    d, mat = prog.dist(points)                     # (N,) distances and material ids
    out = prog.eval('surface', points)             # list of six (N, 4) arrays (see glsl_lib.KERNEL_SURFACE)
    prog.set_uniform('uTime', 2.5)

A Python callable may stand in for any GLSL stage (map(p) -> (d, mat) over (N, 3) arrays, surface(p, n, mat) ->
dict); the evaluation then runs in numpy (np_lib) and returns the same arrays.
"""

from __future__ import annotations

import math
import re
import time

import numpy as np

from . import glsl_lib

# kernel name -> (GLSL main, number of colour targets)
KERNELS = {
    'dist': (glsl_lib.KERNEL_DIST, 1),
    'grad': (glsl_lib.KERNEL_GRAD, 2),
    'surface': (glsl_lib.KERNEL_SURFACE, 6),
    'sample': (glsl_lib.KERNEL_SAMPLE, 2),
    'medium': (glsl_lib.KERNEL_MEDIUM, 2),
    'raymarch': (glsl_lib.KERNEL_RAYMARCH, 1),
    'volume_raymarch': (glsl_lib.KERNEL_VOLUME_RAYMARCH, 1),
}

# engine uniforms every program carries: (name, type, default)
ENGINE_UNIFORMS = [
    ('uTime', 'float', 0.0),
    ('sdfNormalH', 'float', 0.0004),
    ('sdfGradH', 'float', 0.001),
    ('sdfProject', 'float', 0.0),
    ('sdfIso', 'float', 0.0),
    ('sdfUseClip', 'float', 0.0),
    ('sdfClipMin', 'vec3', (-1e4, -1e4, -1e4)),
    ('sdfClipMax', 'vec3', (1e4, 1e4, 1e4)),
    ('uMaxSteps', 'float', 128.0),
    ('uSurfEps', 'float', 0.001),
    ('uStepScale', 'float', 0.85),
    ('uMaxDist', 'float', 100.0),
    ('sdfVolSteps', 'float', 96.0),
    ('sdfMediumStep', 'float', 0.01),
    ('sdfMediumAmbient', 'vec3', (0.0, 0.0, 0.0)),
    ('uEnvMapStrength', 'float', 0.0),
    ('uModelMatrix', 'mat4', None),
    ('sdfCameraUniform', 'vec3', (0.0, 0.0, 0.0)),
    ('cameraPositionWorld', 'vec3', (0.0, 0.0, 0.0)),
    ('sdfCamFwd', 'vec3', (0.0, 0.0, -1.0)),
    ('sdfCamRight', 'vec3', (1.0, 0.0, 0.0)),
    ('sdfCamUp', 'vec3', (0.0, 1.0, 0.0)),
    ('sdfCamTan', 'vec2', (0.5, 0.5)),
    ('sdfImageSize', 'vec2', (1.0, 1.0)),
    ('sdfJitter', 'vec2', (0.0, 0.0)),
]

_SLOTS = {'float': 1, 'int': 1, 'bool': 1, 'vec2': 1, 'vec3': 1, 'vec4': 1, 'color': 1, 'mat4': 4}
_SWZ = {'float': '.x', 'int': '.x', 'bool': '.x', 'vec2': '.xy', 'vec3': '.xyz', 'color': '.xyz', 'vec4': ''}

_FULLSCREEN_VS = 'void main() { gl_Position = vec4(pos, 0.0, 1.0); }'

_SAMPLE_CALL = re.compile(r'\bsample\b(?=\s*\()')
_UNIFORM_DECL = re.compile(r'^[ \t]*uniform\s+(\w+)\s+(\w+)\s*;[^\n]*$', re.M)


def _is_glsl(x):
    return isinstance(x, str)


def normalize_uniforms(uniforms):
    """{name: value | (type, value) | {'value': v, 'type': t}} -> {name: (type, value)}.

    The engine's spec.uniforms were {name: {value: ...}}; plain numbers become float, 3-sequences vec3, a hex string
    or 0xRRGGBB int with type 'color' a linear colour."""
    out = {}
    for name, v in (uniforms or {}).items():
        if isinstance(v, dict):
            t, val = v.get('type'), v.get('value')
        elif isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str):
            t, val = v
        else:
            t, val = None, v
        if t is None:
            if isinstance(val, bool):
                t = 'bool'
            elif isinstance(val, (int, float)):
                t = 'float'
            else:
                t = {1: 'float', 2: 'vec2', 3: 'vec3', 4: 'vec4', 16: 'mat4'}[len(val)]
        out[name] = (t, _coerce(t, val))
    return out


def _srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _coerce(t, val):
    if t == 'color':
        if isinstance(val, str):
            h = val.lstrip('#')
            val = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
            return tuple(float(x) for x in _srgb_to_linear(val))
        if isinstance(val, int):
            val = [((val >> 16) & 255) / 255.0, ((val >> 8) & 255) / 255.0, (val & 255) / 255.0]
            return tuple(float(x) for x in _srgb_to_linear(val))
        return tuple(float(x) for x in val)
    if t in ('float', 'int', 'bool'):
        return float(val)
    if t == 'mat4':
        if val is None:
            return tuple(float(x) for x in np.eye(4).T.ravel())
        a = np.asarray(val, dtype=np.float64)
        if a.shape == (4, 4):
            a = a.T.ravel()                 # rows given -> column-major like three's Matrix4.elements
        return tuple(float(x) for x in a.ravel())
    return tuple(float(x) for x in val)


class SdfProgram:
    """GLSL stages of one SDF (extra, map, shade, surface, sample, medium, post) and their compiled kernels."""

    def __init__(self, map=None, surface=None, shade=None, sample=None, medium=None, extra='', uniforms=None,
                 textures=None, defines=None, label='sdf', post=None, shade_as='albedo'):
        self.label = label
        self.extra = extra or ''
        self.map, self.surface, self.shade, self.sample, self.medium = map, surface, shade, sample, medium
        self.post = post
        self.defines = dict(defines or {})
        # the engine's contract was map + shade (both required). A spec that brings shade() and no surface() gets
        # one made from it: the shade colour seen head-on as the base colour ('albedo') or as emission
        # ('emission', the engine's exact unlit colours); None keeps the plain grey default
        if shade_as not in ('albedo', 'emission', None):
            raise ValueError(f"{label}: shade_as must be 'albedo', 'emission' or None, not {shade_as!r}")
        self.shade_as = shade_as
        self.surface_from_shade = surface is None and shade is not None and shade_as is not None
        if self.surface_from_shade and _is_glsl(shade):
            self.surface = glsl_lib.SHADE_SURFACE
            self.defines['SDF_SHADE_AS_EMISSION'] = 1 if shade_as == 'emission' else 0
        # (a Python shade with no surface: np_lib.surface colours from it)
        user = normalize_uniforms(uniforms)
        # the engine's GLSL originals declared their own uniforms (`uniform vec3 uPaint;` in extra): the
        # declaration gives the type, a value the spec does not set starts at zero, and the line itself goes (the
        # values arrive through the uniform block)
        declared = self.declared_uniforms()
        self.declared_samplers = sorted(n for n, t in declared.items() if t.startswith('sampler'))
        engine_names = {n for n, _t, _d in ENGINE_UNIFORMS}
        for name, t in declared.items():
            if t.startswith('sampler') or name in engine_names or t not in _SLOTS:
                continue
            if name in user:
                user[name] = (('color' if user[name][0] == 'color' and t == 'vec3' else t),
                              _coerce(t, user[name][1]) if user[name][0] != 'color' else user[name][1])
            else:
                user[name] = (t, _coerce(t, 0.0 if t in ('float', 'int', 'bool') else [0.0] * {'vec2': 2, 'vec3': 3, 'vec4': 4, 'mat4': 16}[t]))
        self.layout = []                     # [(name, type, first slot)]
        self.values = {}
        slot = 0
        for name, t, default in ENGINE_UNIFORMS:
            if name in user:                 # an example may override an engine default (uTime start)
                t, default = user.pop(name)
            self.layout.append((name, t, slot))
            self.values[name] = _coerce(t, default)
            slot += _SLOTS[t]
        for name, (t, v) in user.items():
            self.layout.append((name, t, slot))
            self.values[name] = v
            slot += _SLOTS[t]
        self.n_slots = slot
        self.types = {n: t for n, t, _ in self.layout}
        self.textures = dict(textures or {})     # GLSL sampler name -> numpy (H, W, 4) float | bpy Image | path
        for name in self.declared_samplers:
            if name not in self.textures and name != 'uEnvMap':
                # declared but not given: a 1 x 1 black texture keeps the shader valid
                self.textures[name] = np.zeros((1, 1, 4), np.float32)
        self._gpu_textures = {}
        self._shaders = {}
        self._env = None
        self.stats = {'points': 0, 'seconds': 0.0}

    def _stages(self):
        return [s for s in (self.extra, self.map, self.surface, self.shade, self.sample, self.medium, self.post)
                if _is_glsl(s)]

    def declared_uniforms(self):
        """{name: GLSL type} of the `uniform <type> <name>;` lines in the program's GLSL stages."""
        out = {}
        for s in self._stages():
            for t, n in _UNIFORM_DECL.findall(s):
                out[n] = t
        return out

    # ------------------------------------------------------------------------------------------- uniforms ----
    def set_uniform(self, name, value):
        """Set a uniform by its GLSL name (uPaint) or the engine's option style (paint -> uPaint)."""
        if name not in self.types:
            alt = 'u' + name[:1].upper() + name[1:]
            if alt in self.types:
                name = alt
            else:
                raise KeyError(f'{self.label}: no uniform {name!r} (has {sorted(self.types)})')
        self.values[name] = _coerce(self.types[name], value)

    def get_uniform(self, name):
        return self.values[name]

    def _ubo_array(self):
        block = np.zeros((max(1, self.n_slots), 4), np.float32)
        for name, t, slot in self.layout:
            v = self.values[name]
            if t == 'mat4':
                block[slot:slot + 4] = np.asarray(v, np.float32).reshape(4, 4)      # column vectors
            else:
                v = [v] if isinstance(v, float) else list(v)
                block[slot, :len(v)] = v
        return block

    def _macros(self):
        lines = []
        for name, t, slot in self.layout:
            if t == 'mat4':
                lines.append('#define %s mat4(sdf_U.v[%d], sdf_U.v[%d], sdf_U.v[%d], sdf_U.v[%d])'
                             % (name, slot, slot + 1, slot + 2, slot + 3))
            elif t == 'int':
                lines.append('#define %s int(sdf_U.v[%d].x)' % (name, slot))
            elif t == 'bool':
                lines.append('#define %s (sdf_U.v[%d].x > 0.5)' % (name, slot))
            else:
                lines.append('#define %s (sdf_U.v[%d]%s)' % (name, slot, _SWZ[t]))
        return '\n'.join(lines)

    # ------------------------------------------------------------------------------------------- sources -----
    def source(self, kind):
        """The full fragment source of one kernel (for reading, and for compile-error messages)."""
        if kind in ('dist', 'grad', 'surface', 'raymarch') and not _is_glsl(self.map):
            raise TypeError('map is not GLSL')
        volume_kind = kind in ('sample', 'medium') or kind == 'volume_raymarch'
        parts = [
            '#define SDF_KERNEL_%s 1' % kind.upper(),
            '#define SDF_VIEW_DEPENDENT %d' % (1 if kind in ('raymarch', 'volume_raymarch') else 0),
        ]
        if kind == 'volume_raymarch' and self.sample is None and self.medium is not None:
            parts.append('#define SDF_VOLUME_MEDIUM 1')
        if kind == 'volume_raymarch' and _is_glsl(self.post):
            parts.append('#define SDF_HAS_POST 1')
        parts += ['#define %s %s' % (k, v) for k, v in self.defines.items()]
        # the original's order: uniforms, sampleEnvMap / sdfReflectWorld, the primitives, extra, map, calcNormal /
        # softShadow, shade (an example's extra may call the env helpers)
        parts += [self._macros(), glsl_lib.VIEW_PRELUDE, glsl_lib.ENV_HELPERS, glsl_lib.SDF_PRIMITIVES,
                  glsl_lib.SURFACE_RECORD, glsl_lib.VOLUME_RECORDS, self.extra]
        if volume_kind:
            parts.append('vec4 sdfFetchPoint() { return texelFetch(sdfPoints, ivec2(gl_FragCoord.xy), 0); }')
            if kind == 'sample' or (kind == 'volume_raymarch' and self.sample is not None):
                if not _is_glsl(self.sample):
                    raise TypeError('sample is not GLSL')
                parts.append(self.sample)
            else:
                if not _is_glsl(self.medium):
                    raise TypeError('medium is not GLSL')
                parts.append(self.medium)
            if kind == 'volume_raymarch' and _is_glsl(self.post):
                parts.append(self.post)
        elif kind in ('dist', 'grad', 'surface', 'raymarch'):
            parts.append(self.map)
            parts.append(glsl_lib.NORMAL_AND_SHADOW)
            parts.append(glsl_lib.KERNEL_COMMON)
            if kind == 'surface':
                if not _is_glsl(self.surface):
                    raise TypeError('surface is not GLSL')
                if self.surface_from_shade and _is_glsl(self.shade):
                    parts.append(self.shade)
                parts.append(self.surface)
            if kind == 'raymarch':
                if not _is_glsl(self.shade):
                    raise TypeError('shade is not GLSL')
                parts.append(self.shade)
        parts.append(KERNELS[kind][0])
        src = '\n'.join(p for p in parts if p)
        if volume_kind:
            # `sample` is a reserved word in desktop GLSL 4.x (the per-sample interpolation qualifier): the engine's
            # sample(p) contract keeps its name in the examples and is renamed here, calls and definition alike
            src = _SAMPLE_CALL.sub('sdf_sample_fn', src)
        # the originals' own `uniform` lines: their values come through the uniform block (and the samplers through
        # the shader's create-info), so each declaration stays only as a comment
        src = _UNIFORM_DECL.sub(lambda m: '// (bound by the engine) ' + m.group(0).strip(), src)
        # GLSL ES / WebGL leftovers the desktop compiler or Blender's preprocessor may not take
        src = '\n'.join(ln for ln in src.split('\n') if not ln.strip().startswith('precision '))
        return src

    def _shader(self, kind):
        sh = self._shaders.get(kind)
        if sh is not None:
            return sh
        import gpu
        from gpu_extras.batch import batch_for_shader
        _ensure_gpu()
        nout = KERNELS[kind][1]
        info = gpu.types.GPUShaderCreateInfo()
        info.typedef_source('struct SdfParams { vec4 v[%d]; };' % max(1, self.n_slots))
        info.uniform_buf(0, 'SdfParams', 'sdf_U')
        info.sampler(0, 'FLOAT_2D', 'sdfPoints')
        info.sampler(1, 'FLOAT_2D', 'sdfEnvMap')
        for i, name in enumerate(sorted(self.textures)):
            info.sampler(2 + i, 'FLOAT_2D', name)
        info.vertex_in(0, 'VEC2', 'pos')
        for i in range(nout):
            info.fragment_out(i, 'VEC4', 'out%d' % i)
        info.vertex_source(_FULLSCREEN_VS)
        src = self.source(kind)
        info.fragment_source(src)
        try:
            shader = gpu.shader.create_from_info(info)
        except Exception as e:
            numbered = '\n'.join('%4d  %s' % (i + 1, ln) for i, ln in enumerate(src.split('\n')))
            raise RuntimeError(f'[sdf] {self.label}: the {kind} kernel did not compile: {e}\n{numbered}') from e
        batch = batch_for_shader(shader, 'TRIS', {'pos': [(-1, -1), (3, -1), (-1, 3)]})
        self._shaders[kind] = (shader, batch)
        return self._shaders[kind]

    def _texture(self, name):
        t = self._gpu_textures.get(name)
        if t is not None:
            return t
        import gpu
        src = self.textures[name]
        arr = _image_array(src)
        h, w = arr.shape[:2]
        buf = gpu.types.Buffer('FLOAT', arr.size, np.ascontiguousarray(arr, np.float32).ravel())
        t = gpu.types.GPUTexture((w, h), format='RGBA32F', data=buf)
        t.filter_mode(True)
        t.extend_mode('REPEAT')
        self._gpu_textures[name] = t
        return t

    def set_env_map(self, arr_or_image, strength=1.0):
        """Bind an equirect (numpy (H, W, 4) linear, a bpy Image or a path) as sampleEnvMap's HDRI."""
        import gpu
        _ensure_gpu()
        arr = _image_array(arr_or_image)
        h, w = arr.shape[:2]
        buf = gpu.types.Buffer('FLOAT', arr.size, np.ascontiguousarray(arr, np.float32).ravel())
        self._env = gpu.types.GPUTexture((w, h), format='RGBA32F', data=buf)
        self._env.filter_mode(True)
        self._env.extend_mode('REPEAT')
        self.values['uEnvMapStrength'] = float(strength)

    # ---------------------------------------------------------------------------------------- evaluation -----
    def eval(self, kind, points, width=2048, max_batch=1 << 21, target_ms=60.0):
        """Run one kernel over (N, 3) points (the SDF's local three frame); returns a list of (N, 4) arrays."""
        pts = np.ascontiguousarray(np.asarray(points, dtype=np.float32).reshape(-1, 3))
        n = len(pts)
        nout = KERNELS[kind][1]
        outs = [np.empty((n, 4), np.float32) for _ in range(nout)]
        if n == 0:
            return outs
        t0 = time.perf_counter()
        for s in range(0, n, max_batch):
            e = min(n, s + max_batch)
            res = self._eval_batch(kind, pts[s:e], width, target_ms)
            for o, r in zip(outs, res):
                o[s:e] = r
        self.stats['points'] += n
        self.stats['seconds'] += time.perf_counter() - t0
        return outs

    def _eval_batch(self, kind, pts, width, target_ms):
        import gpu
        shader, batch = self._shader(kind)
        nout = KERNELS[kind][1]
        n = len(pts)
        w = min(width, n)
        h = int(math.ceil(n / w))
        data = np.zeros((h * w, 4), np.float32)
        data[:n, :3] = pts
        if n < h * w:
            data[n:, :3] = pts[-1]
        buf = gpu.types.Buffer('FLOAT', data.size, data.ravel())
        tin = gpu.types.GPUTexture((w, h), format='RGBA32F', data=buf)
        tin.filter_mode(False)
        targets = [gpu.types.GPUTexture((w, h), format='RGBA32F') for _ in range(nout)]
        fb = gpu.types.GPUFrameBuffer(color_slots=tuple(targets))
        ubo = gpu.types.GPUUniformBuf(gpu.types.Buffer('FLOAT', self.n_slots * 4 if self.n_slots else 4,
                                                       self._ubo_array().ravel()))
        env = self._env
        if env is None:
            env = self._dummy_env()
        try:
            with fb.bind():
                shader.bind()
                shader.uniform_block('sdf_U', ubo)
                shader.uniform_sampler('sdfPoints', tin)
                shader.uniform_sampler('sdfEnvMap', env)
                for name in sorted(self.textures):
                    shader.uniform_sampler(name, self._texture(name))
                gpu.state.scissor_test_set(True)
                rows = max(1, min(h, int(4096 // max(1, w // 64))))     # first strip: a modest probe
                y = 0
                while y < h:
                    r = min(rows, h - y)
                    gpu.state.scissor_set(0, y, w, r)
                    t0 = time.perf_counter()
                    batch.draw(shader)
                    fb.read_color(0, y, 1, 1, 4, 0, 'FLOAT')        # wait for this strip
                    dt = (time.perf_counter() - t0) * 1000.0
                    y += r
                    # aim each strip at target_ms
                    if dt > 0.0:
                        rows = int(max(1, min(h, r * min(4.0, max(0.25, target_ms / dt)))))
                gpu.state.scissor_test_set(False)
            return [_read_texture(t).reshape(h * w, 4)[:n] for t in targets]
        finally:
            del fb

    def _dummy_env(self):
        import gpu
        if getattr(self, '_dummy', None) is None:
            buf = gpu.types.Buffer('FLOAT', 16, [0.5] * 16)
            self._dummy = gpu.types.GPUTexture((2, 2), format='RGBA32F', data=buf)
        return self._dummy

    # convenience wrappers --------------------------------------------------------------------------------------
    def dist(self, points):
        """(d, mat) at points: the clipped field when sdfUseClip is on."""
        if not _is_glsl(self.map):
            from . import np_lib
            with np_lib.current(self):
                d, m = np_lib.call_map(self.map, points)
            if self.values['sdfUseClip'] > 0.5:
                d = np.maximum(d, np_lib.box_dist(points, self.values['sdfClipMin'], self.values['sdfClipMax']))
            return d, m
        o = self.eval('dist', points)[0]
        return o[:, 0].copy(), o[:, 1].copy()

    def grad(self, points, h):
        """(d, mat, gradient (N, 3)) with the tetrahedral difference at step h."""
        self.values['sdfGradH'] = float(h)
        if not _is_glsl(self.map):
            from . import np_lib
            return np_lib.grad(self, points, h)
        o0, o1 = self.eval('grad', points)
        return o0[:, 0].copy(), o0[:, 1].copy(), o1[:, :3].copy()

    def surface_eval(self, points, project=1, grad_h=0.001, normal_h=0.0004):
        """The surface kernel: dict of channel arrays at the (projected) points."""
        self.values['sdfProject'] = float(project)
        self.values['sdfGradH'] = float(grad_h)
        self.values['sdfNormalH'] = float(normal_h)
        if not _is_glsl(self.map):
            from . import np_lib
            return np_lib.surface(self, points, project, grad_h, normal_h)
        python_surface = self.surface if callable(self.surface) else None
        python_shade = self.shade if (self.surface_from_shade and callable(self.shade)) else None
        if python_surface is not None or self.surface is None:
            # a GLSL map without a GLSL surface: the GPU projects and takes normals under a plain surface; a
            # Python surface(p, n, mat) (or a Python shade) then colours those points on the CPU
            self.surface = glsl_lib.DEFAULT_SURFACE
            self._shaders.pop('surface', None)
        o = self.eval('surface', points)
        out = {
            'albedo': o[0][:, :3], 'roughness': o[0][:, 3], 'emission': o[1][:, :3], 'metallic': o[1][:, 3],
            'sheen_tint': o[2][:, :3], 'sheen': o[2][:, 3], 'subsurface': o[3][:, 0], 'coat': o[3][:, 1],
            'specular': o[3][:, 2], 'transmission': o[3][:, 3], 'position': o[4][:, :3], 'dist': o[4][:, 3],
            'normal': o[5][:, :3], 'mat': o[5][:, 3],
        }
        if python_surface is not None or python_shade is not None:
            from . import np_lib
            with np_lib.current(self):
                if python_surface is not None:
                    self.surface = python_surface
                    s = python_surface(out['position'], out['normal'], out['mat'])
                else:
                    s = np_lib.shade_surface(python_shade(out['position'], out['normal'], out['mat']), self.shade_as)
            out.update(np_lib.surface_channels(s, len(points)))
        return out

    def free(self):
        self._shaders.clear()
        self._gpu_textures.clear()
        self._env = None


def _read_texture(tex):
    """A float texture's texels as a flat float32 array (the buffer protocol when the Buffer offers it)."""
    buf = tex.read()
    try:
        return np.asarray(memoryview(buf), dtype=np.float32).reshape(-1).copy()
    except TypeError:
        return np.array(buf, dtype=np.float32).reshape(-1)


_GPU_READY = [False]


def _ensure_gpu():
    if _GPU_READY[0]:
        return
    import bpy
    import gpu
    if bpy.app.background:
        try:
            gpu.init()
        except Exception:
            pass
    _GPU_READY[0] = True


def _image_array(src):
    """numpy (H, W, 4) float32, row 0 at the bottom (GL order), from an array, a bpy Image or an image path."""
    if isinstance(src, np.ndarray):
        a = np.asarray(src, np.float32)
        if a.ndim == 2:
            a = np.stack([a, a, a, np.ones_like(a)], -1)
        if a.shape[-1] == 3:
            a = np.concatenate([a, np.ones(a.shape[:2] + (1,), np.float32)], -1)
        return a
    import bpy
    img = src
    loaded = False
    if isinstance(src, str):
        img = bpy.data.images.load(src, check_existing=True)
        loaded = True
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    if loaded and img.users == 0:
        pass
    return px.reshape(h, w, 4)
