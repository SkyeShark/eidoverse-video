"""The terrain family's GPU runner: GLSL compute kernels over 2D float textures (design section 2.5).

The pattern of eidoblend/fx/_gpu.py, copied rather than imported (the family contract keeps families
self-contained). Blender 5.2 runs compute shaders headless (gpu.compute.dispatch), and inserts a texture-fetch +
image-access barrier after every dispatch, so kernels chain in submission order.

    from eidoblend.terrain.core import gpu as G
    G.init()                                   # gpu.init() in background mode; raises without compute support
    k = G.kernel('route_incise')               # terrain/kernels/route_incise.glsl, common.glsl prefixed, compiled
                                               # once per process per source hash
    k = G.kernel(path='/abs/sample.glsl')      # or a file anywhere, or G.kernel(source=text, name='x')
    t = G.texture(arr)                         # (H, W) or (H, W, 1|2|4) float -> R32F / RG32F / RGBA32F
    o = G.empty((H, W), channels=4)            # a zeroed RGBA32F texture
    G.run(k, None, samplers={'st': t}, images={'outS': o}, uniforms={'uDx': 7.8})   # groups None: cover the image
    a = G.read(o)                              # numpy float32 (H, W, C), exactly what the texture holds
    pp = G.PingPong(arr)                       # pp.src / pp.dst, pp.swap(), pp.read()

Arrays are [row j, column i] with row 0 the SOUTH edge (core/grid.py); texel (x, y) = (i, j), so
texelFetch(s, ivec2(i, j), 0) reads arr[j, i] and +y in a kernel is north.

A kernel file declares its interface in `//!` lines (the runner builds the shader's create-info from them):

    //! sampler st                 an input: sampler2D, read with texelFetch (no filtering)
    //! image   outS rgba32f       an output: image2D, write-only (rgba32f is the default; r32f, rg32f)
    //! uniform float uDx          a push constant: float int vec2 vec3 vec4 ivec2 ivec3 ivec4
    //! local   16 16              the work-group size (16 x 16 is the default and the house rule)

Samplers bind to slots 0.. and images to 0.. in the order declared. Every declared binding and uniform must be
given on every run (a uniform left out would keep whatever the last run set), and a texture may not be a sampler
and an image of the same dispatch (ping-pong instead). common.glsl (neighbour tables, boundary modes, pins, PCG
hash) is prefixed to every kernel.

The runner fails loudly without compute support; there is no CPU path in production. The numpy twins
(core/twins.py) are test oracles only.
"""

from __future__ import annotations

import difflib
import hashlib
import math
import os
import re
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_DIR = os.path.normpath(os.path.join(HERE, '..', 'kernels'))
COMMON = os.path.join(KERNEL_DIR, 'common.glsl')
LOCAL = (16, 16)                                    # the house work-group size
PUSH_LIMIT_BYTES = 128                              # Vulkan's guaranteed minimum; keep kernels portable

_FMT_CHANNELS = {'R32F': 1, 'RG32F': 2, 'RGBA32F': 4, 'RGBA16F': 4}
_CHANNEL_FMT = {1: 'R32F', 2: 'RG32F', 4: 'RGBA32F'}
_UNIFORM_TYPES = {'float': ('FLOAT', 4), 'int': ('INT', 4), 'vec2': ('VEC2', 8), 'vec3': ('VEC3', 12),
                  'vec4': ('VEC4', 16), 'ivec2': ('IVEC2', 8), 'ivec3': ('IVEC3', 12), 'ivec4': ('IVEC4', 16)}
_HEADER = re.compile(r'^\s*//!\s*(\w+)\s*(.*?)\s*$')

_state = {'gpu': None, 'info': None}
KERNELS = {}                                        # source hash -> Kernel (the per-process compile cache)
COMPILE_MS = {}                                     # kernel name -> compile time of its first build, ms


# ------------------------------------------------------------------------------------------------ the context ---

def init():
    """Bring up Blender's GPU module (gpu.init() in background mode) and check that a compute dispatch reads back
    the right numbers. Returns {'vendor', 'renderer', 'version', 'backend', 'device'}; raises RuntimeError when
    there is no Blender, no compute support or a wrong readback. Safe to call again (does the work once)."""
    if _state['info'] is not None:
        return _state['info']
    try:
        import bpy
        import gpu
    except ImportError as e:
        raise RuntimeError('the terrain GPU runner needs Blender (bpy and gpu); the numpy twins are test oracles, '
                           'not a fallback') from e
    if bpy.app.background:
        try:
            gpu.init()
        except Exception:                                          # noqa: BLE001 - already initialised
            pass
    p = gpu.platform
    info = {'vendor': p.vendor_get(), 'renderer': p.renderer_get(), 'version': p.version_get(),
            'backend': p.backend_type_get(), 'device': p.device_type_get()}
    # Blender 5.2 deprecates compute_shader_support_get ("all platforms have support"): the self test below is the
    # check that a dispatch really runs and reads back right
    if info['device'] == 'SOFTWARE':
        print(f"[terrain.gpu] WARNING: software GPU {info['renderer']}: kernels run on the CPU, many times slower",
              flush=True)
    _state['gpu'] = gpu
    _state['info'] = info
    _self_test()
    return info


def _gpu():
    if _state['gpu'] is None:
        init()
    return _state['gpu']


def _self_test():
    """One tiny dispatch whose readback must be exact (gpu_check's idea), so a broken driver fails here, loudly."""
    src = ('void main() { ivec2 p = ivec2(gl_GlobalInvocationID.xy); '
           'imageStore(outT, p, vec4(float(p.x) * 3.0 + 7.0, float(p.y), 0.0, 1.0)); }')
    k = kernel(source='//! image outT rgba32f\n' + src, name='_self_test', common=False)
    t = empty((3, 20), channels=4)
    run(k, None, images={'outT': t})
    a = read(t)
    jj, ii = np.mgrid[0:3, 0:20]
    if not (np.array_equal(a[..., 0], ii * 3.0 + 7.0) and np.array_equal(a[..., 1], jj.astype(np.float32))):
        raise RuntimeError(f"terrain GPU runner: a compute dispatch on {_state['info']['renderer']} read back wrong "
                           f'values; see docs/SETUP.md for the GPU setup')


def sync(tex):
    """Wait for every dispatch that leads to `tex` (reads one texture back; the chain before it must finish)."""
    tex.read()


# ------------------------------------------------------------------------------------------------- textures ---

def _as_hwc(arr):
    a = np.asarray(arr, dtype=np.float32)
    if a.ndim == 2:
        a = a[:, :, None]
    if a.ndim != 3:
        raise ValueError(f'texture data must be (H, W) or (H, W, C), got shape {a.shape}')
    c = a.shape[2]
    if c == 3:                                                     # no RGB32F image format: pad to four
        a = np.concatenate([a, np.zeros(a.shape[:2] + (1,), np.float32)], axis=2)
    elif c not in (1, 2, 4):
        raise ValueError(f'texture data has {c} channels; 1, 2, 3 or 4 are supported')
    return np.ascontiguousarray(a)


def texture(arr, fmt=None):
    """A 2D float texture holding `arr` exactly: (H, W) or (H, W, 1) -> R32F, (H, W, 2) -> RG32F, (H, W, 3|4) ->
    RGBA32F (3 is padded with zeros). Row 0 of the array is texel row 0 (y = 0, the south edge). Nearest
    filtering, so a sampler read is the texel."""
    gpu = _gpu()
    a = _as_hwc(arr)
    h, w, c = a.shape
    fmt = fmt or _CHANNEL_FMT[c]
    if _FMT_CHANNELS.get(fmt) != c:
        raise ValueError(f'format {fmt} holds {_FMT_CHANNELS.get(fmt)} channels, the data has {c}')
    buf = gpu.types.Buffer('FLOAT', a.size, a.ravel())
    tex = gpu.types.GPUTexture((w, h), format=fmt, data=buf)
    tex.filter_mode(False)
    return tex


def empty(shape, channels=4, fmt=None):
    """A zeroed texture of (H, W) texels."""
    gpu = _gpu()
    h, w = int(shape[0]), int(shape[1])
    fmt = fmt or _CHANNEL_FMT[channels]
    tex = gpu.types.GPUTexture((w, h), format=fmt)
    tex.clear(format='FLOAT', value=(0.0,) * _FMT_CHANNELS[fmt])
    tex.filter_mode(False)
    return tex


def like(tex):
    """A zeroed texture of the same size and format."""
    return empty((tex.height, tex.width), fmt=tex.format)


def read(tex):
    """The texture's contents as float32 numpy (H, W, C): bit for bit what it holds."""
    buf = tex.read()
    a = np.asarray(buf, dtype=np.float32)
    c = _FMT_CHANNELS.get(tex.format, 4)
    return np.array(a, dtype=np.float32, copy=True).reshape(tex.height, tex.width, c)


def pack(arrays, names, shape=None):
    """Stack up to four named (H, W) arrays into one (H, W, 4) float32 array for an RGBA32F texture; a name that is
    None or missing from `arrays` gives a zero channel. `arrays` is a dict (a Fields, say)."""
    if len(names) > 4:
        raise ValueError(f'an RGBA texture packs at most four fields, got {list(names)}')
    if shape is None:
        shape = next(np.shape(arrays[n]) for n in names if n is not None and n in arrays)
    out = np.zeros(tuple(shape)[:2] + (4,), np.float32)
    for c, n in enumerate(names):
        if n is not None and n in arrays:
            out[..., c] = arrays[n]
    return out


def unpack(arr, names):
    """The inverse of pack: {name: (H, W) float32} for every name that is not None."""
    a = np.asarray(arr, dtype=np.float32)
    return {n: np.array(a[..., c], copy=True) for c, n in enumerate(names) if n is not None}


class PingPong:
    """Two textures of one size and format for an iterated kernel: read .src, write .dst, then swap()."""

    def __init__(self, arr=None, shape=None, channels=4):
        if arr is not None:
            self.src = texture(arr)
            self.dst = like(self.src)
        else:
            self.src = empty(shape, channels)
            self.dst = like(self.src)

    def swap(self):
        self.src, self.dst = self.dst, self.src

    def read(self):
        return read(self.src)


# -------------------------------------------------------------------------------------------------- kernels ---

class KernelSpec:
    """A kernel's interface, parsed from its `//!` lines: samplers, images {name: format}, uniforms
    {name: glsl type}, local size. Plain Python: no GPU needed (the twins check themselves against it)."""

    def __init__(self, name, samplers, images, uniforms, local):
        self.name = name
        self.samplers = samplers
        self.images = images
        self.uniforms = uniforms
        self.local = local

    def push_bytes(self):
        return sum(_UNIFORM_TYPES[t][1] for t in self.uniforms.values())

    def __repr__(self):
        return (f'KernelSpec({self.name!r}, samplers={self.samplers}, images={self.images}, '
                f'uniforms={self.uniforms}, local={self.local})')


_IDENT = re.compile(r'^[A-Za-z_]\w*$')
_LOOKS_LIKE_FORMAT = re.compile(r'^(r|rg|rgb|rgba)\d+(f|i|ui)?$', re.I)


def parse_spec(text, name='kernel'):
    """Read the `//!` declarations of a kernel source. Anything after a declaration's name (and an image's format)
    is a description. Raises ValueError naming the line on a bad one."""
    samplers, images, uniforms, local = [], {}, {}, LOCAL
    for ln, line in enumerate(text.splitlines(), 1):
        m = _HEADER.match(line)
        if not m:
            continue
        kind, toks = m.group(1), [t.rstrip(';') for t in m.group(2).split()]
        bad = None
        if kind == 'sampler' and toks and _IDENT.match(toks[0]):
            samplers.append(toks[0])
        elif kind == 'image' and toks and _IDENT.match(toks[0]):
            fmt = 'RGBA32F'
            if len(toks) > 1 and _LOOKS_LIKE_FORMAT.match(toks[1]):
                fmt = toks[1].upper()
                if fmt not in _FMT_CHANNELS:
                    bad = (f'image format {toks[1]!r} is not one of '
                           f'{sorted(f.lower() for f in _FMT_CHANNELS)}')
            images[toks[0]] = fmt
        elif kind == 'uniform' and len(toks) >= 2 and _IDENT.match(toks[1]):
            if toks[0] not in _UNIFORM_TYPES:
                bad = f'uniform type {toks[0]!r} is not one of {sorted(_UNIFORM_TYPES)}'
            uniforms[toks[1]] = toks[0]
        elif kind == 'local' and len(toks) >= 2 and toks[0].isdigit() and toks[1].isdigit():
            local = (int(toks[0]), int(toks[1]))
        else:
            bad = (f"cannot read the declaration {line.strip()!r}; expected '//! sampler <name>', "
                   f"'//! image <name> [format]', '//! uniform <type> <name>' or '//! local <x> <y>' (then any "
                   f"description)")
        if bad:
            raise ValueError(f'{name}:{ln}: {bad}')
    names = samplers + list(images) + list(uniforms)
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ValueError(f'{name}: declared twice: {dup}')
    if not images:
        raise ValueError(f'{name}: a kernel needs at least one `//! image` output')
    spec = KernelSpec(name, samplers, images, uniforms, local)
    if spec.push_bytes() > PUSH_LIMIT_BYTES:
        raise ValueError(f'{name}: {spec.push_bytes()} bytes of uniforms; push constants are limited to '
                         f'{PUSH_LIMIT_BYTES} bytes (put per-cell or long parameter lists in a texture)')
    return spec


def kernel_path(name):
    """terrain/kernels/<name>.glsl"""
    return os.path.join(KERNEL_DIR, name + '.glsl')


def load_source(name=None, path=None, source=None, common=True):
    """(name, full source, spec): the kernel's text with common.glsl prefixed, and its parsed interface."""
    if source is None:
        path = path or kernel_path(name)
        if not os.path.exists(path):
            have = sorted(f[:-5] for f in os.listdir(KERNEL_DIR) if f.endswith('.glsl')) \
                if os.path.isdir(KERNEL_DIR) else []
            near = difflib.get_close_matches(name or '', have, n=3)
            raise FileNotFoundError(f'no kernel file {path}' + (f'; did you mean {near}?' if near else ''))
        with open(path, encoding='utf-8') as f:
            source = f.read()
        name = name or os.path.splitext(os.path.basename(path))[0]
    name = name or 'kernel'
    spec = parse_spec(source, name)
    full = source
    if common:
        with open(COMMON, encoding='utf-8') as f:
            full = f.read() + '\n#line 1\n' + source
    return name, full, spec


class Kernel:
    """A compiled kernel: .name, .spec, .shader, .compile_ms, .groups_for((H, W))."""

    def __init__(self, name, spec, shader, compile_ms, source_hash):
        self.name = name
        self.spec = spec
        self.shader = shader
        self.compile_ms = compile_ms
        self.source_hash = source_hash

    def groups_for(self, shape):
        h, w = int(shape[0]), int(shape[1])
        lx, ly = self.spec.local
        return (int(math.ceil(w / lx)), int(math.ceil(h / ly)), 1)

    def run(self, groups=None, samplers=None, images=None, uniforms=None):
        run(self, groups, samplers, images, uniforms)

    def __repr__(self):
        return f'Kernel({self.name!r}, {self.source_hash[:10]}, compiled in {self.compile_ms:.1f} ms)'


def kernel(name=None, path=None, source=None, defines=None, common=True):
    """The compiled kernel for terrain/kernels/<name>.glsl (or a file at `path`, or `source` text), with common.glsl
    prefixed and `defines` set. Compiled once per process per (source, defines): later calls return the cached
    Kernel. Raises RuntimeError naming the kernel when it fails to compile (Blender prints the GLSL log above)."""
    gpu = _gpu()
    name, full, spec = load_source(name, path, source, common)
    defs = sorted((str(k), str(v)) for k, v in (defines or {}).items())
    key = hashlib.sha1((full + '\0' + repr(defs)).encode('utf-8')).hexdigest()
    hit = KERNELS.get(key)
    if hit is not None:
        return hit
    info = gpu.types.GPUShaderCreateInfo()
    info.local_group_size(spec.local[0], spec.local[1], 1)
    for slot, s in enumerate(spec.samplers):
        info.sampler(slot, 'FLOAT_2D', s)
    for slot, (im, fmt) in enumerate(spec.images.items()):
        info.image(slot, fmt, 'FLOAT_2D', im, qualifiers={'WRITE'})
    for un, ty in spec.uniforms.items():
        info.push_constant(_UNIFORM_TYPES[ty][0], un)
    for k, v in defs:
        info.define(k, v)
    info.compute_source(full)
    t0 = time.perf_counter()
    try:
        shader = gpu.shader.create_from_info(info)
    except Exception as e:                                         # noqa: BLE001
        raise RuntimeError(f'kernel {name!r} failed to compile ({path or "source text"}): {e}. The GLSL log is '
                           f'printed above; line numbers count from the kernel file (common.glsl is prefixed with '
                           f'#line 1 after it)') from e
    ms = (time.perf_counter() - t0) * 1000.0
    k = Kernel(name, spec, shader, ms, key)
    KERNELS[key] = k
    COMPILE_MS.setdefault(name, round(ms, 2))
    return k


def _nearest(name, names):
    near = difflib.get_close_matches(name, list(names), n=3)
    return f' (did you mean {near}?)' if near else f' (declared: {sorted(names)})'


def run(kernel, groups=None, samplers=None, images=None, uniforms=None):
    """One dispatch of `kernel` (a Kernel, or a kernel name). groups None covers the first image with the kernel's
    local size. Every declared sampler, image and uniform must be given; names are checked against the kernel's
    `//!` declarations and a mistake names the nearest declared ones."""
    gpu = _gpu()
    if isinstance(kernel, str):
        kernel = globals()['kernel'](kernel)
    spec = kernel.spec
    samplers, images, uniforms = samplers or {}, images or {}, uniforms or {}
    for given, declared, what in ((samplers, spec.samplers, 'sampler'), (images, spec.images, 'image'),
                                  (uniforms, spec.uniforms, 'uniform')):
        for n in given:
            if n not in declared:
                raise KeyError(f'kernel {kernel.name!r} has no {what} {n!r}' + _nearest(n, declared))
        missing = [n for n in declared if n not in given]
        if missing:
            raise KeyError(f'kernel {kernel.name!r}: {what}s not given: {missing} (every declared {what} is '
                           f'required on every run)')
    ids = {id(t) for t in samplers.values()}
    for n, t in images.items():
        if id(t) in ids:
            raise ValueError(f'kernel {kernel.name!r}: texture bound as sampler and as image {n!r} in one dispatch; '
                             f'use a PingPong pair')
        if t.format != spec.images[n]:
            raise ValueError(f'kernel {kernel.name!r}: image {n!r} is declared {spec.images[n]}, the texture is '
                             f'{t.format}')
    sh = kernel.shader
    for n, t in samplers.items():
        sh.uniform_sampler(n, t)
    for n, t in images.items():
        sh.image(n, t)
    for n, v in uniforms.items():
        ty = spec.uniforms[n]
        if ty == 'float':
            sh.uniform_float(n, float(v))
        elif ty == 'int':
            sh.uniform_int(n, int(v))
        elif ty.startswith('ivec'):
            sh.uniform_int(n, [int(x) for x in v])
        else:
            sh.uniform_float(n, [float(x) for x in v])
    if groups is None:
        first = next(iter(images.values()))
        groups = kernel.groups_for((first.height, first.width))
    gpu.compute.dispatch(sh, *[int(g) for g in groups])
