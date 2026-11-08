"""eidoblend.harness.gpu_check: eidoverse/gpu_check.mjs in Blender. Is the GPU Blender renders and computes on real
hardware, or a software fallback that runs on the CPU and is many times slower; and does a compute dispatch with a
readback return the right numbers (the path the fx and sky families' GPU bakes take)?

    from eidoblend.harness import gpu_check
    info = gpu_check.adapter_info()            # {'vendor', 'device', 'description', 'architecture', 'backend', ...}
    res = gpu_check.check_gpu()                # info + {'compute_readback': 'passed'}, or raises with the reason
    gpu_check.classify(info, warn=print)       # the engine's hardware / software / unknown rule (plain Python)

    bash run_blender.sh blender/eidoblend/harness/gpu_check.py      # prints one JSON line; exit 1 on a failure

The engine asked WebGPU for a high-performance adapter and, failing that, for an explicit fallback; Blender picks its
GPU when it starts (Preferences > System > GPU Backend / Device), so there is nothing to request: the check reads
what Blender chose (gpu.platform) and classifies it by the same names. Blender reports a software OpenGL / Vulkan
device as device type 'SOFTWARE', the twin of WebGPU's isFallbackAdapter.
"""

from __future__ import annotations

import json
import re
import sys

HELP = ('See docs/SETUP.md for the GPU setup; on a machine with no usable GPU Blender falls back to a software '
        'renderer (Mesa llvmpipe / lavapipe, Microsoft WARP).')
SOFTWARE = re.compile(r'llvmpipe|lavapipe|swiftshader|software|basic render|\bwarp\b|softpipe', re.I)


def classify(info: dict, warn=None) -> dict:
    """gpu_check.mjs requestRenderAdapter's classification. info: {'vendor', 'device', 'description',
    'architecture', 'is_fallback_adapter' (True / False / None)}. Sets info['backend'] to 'software' (the fallback
    flag, or a software renderer's name, even when the flag says otherwise), 'hardware' (a named adapter that is not
    a fallback) or 'unknown' (nothing to verify by); warns for software and unknown. Returns info."""
    warn = warn or (lambda m: print(m, file=sys.stderr))
    label = ' / '.join(str(info.get(k) or '') for k in ('description', 'vendor', 'device', 'architecture')
                       if info.get(k))
    fallback = info.get('is_fallback_adapter')
    software = bool(SOFTWARE.search(label))
    info['backend'] = ('software' if fallback is True or software else
                       'hardware' if fallback is False and label else 'unknown')
    if info['backend'] == 'software':
        warn(f"[gpu] WARNING: Software GPU fallback: {label or '(unnamed)'}. Rendering/compute will run on the CPU and "
             f'may be much slower. If GPU access is available, check its driver/backend configuration. {HELP}')
    elif info['backend'] == 'unknown':
        warn(f"[gpu] WARNING: Cannot verify the GPU adapter type: {label or '(unnamed)'}. {HELP}")
    return info


def _init_gpu():
    import bpy
    import gpu
    if bpy.app.background:
        try:
            gpu.init()
        except Exception:                                          # noqa: BLE001 - already initialised
            pass
    return gpu


def adapter_info(warn=None) -> dict:
    """What Blender's GPU module reports, classified (classify)."""
    gpu = _init_gpu()
    p = gpu.platform
    dev = p.device_type_get()
    info = {'vendor': p.vendor_get(), 'device': dev, 'description': p.renderer_get(),
            'architecture': f'{p.backend_type_get()} {p.version_get()}',
            'is_fallback_adapter': True if dev == 'SOFTWARE' else (False if dev not in ('UNKNOWN', '') else None)}
    return classify(info, warn)


COMPUTE = """
void main() {
    uint id = gl_GlobalInvocationID.x;
    imageStore(result, ivec2(int(id), 0), vec4(float(id * 3u + 7u), 0.0, 0.0, 1.0));
}
"""


def compute_readback(count: int = 64) -> list:
    """gpu_check.mjs checkWebGPU's dispatch: one workgroup of 64 writes id * 3 + 7, read back. Returns the values."""
    gpu = _init_gpu()
    info = gpu.types.GPUShaderCreateInfo()
    info.local_group_size(count, 1, 1)
    info.image(0, 'R32F', 'FLOAT_2D', 'result', qualifiers={'WRITE'})
    info.compute_source(COMPUTE)
    shader = gpu.shader.create_from_info(info)
    tex = gpu.types.GPUTexture((count, 1), format='R32F')
    shader.image('result', tex)
    gpu.compute.dispatch(shader, 1, 1, 1)
    buf = tex.read()
    return [float(v) for v in list(buf.to_list())[0]][:count] if hasattr(buf, 'to_list') else list(buf)[:count]


def check_gpu(warn=None) -> dict:
    """The adapter, classified, and a compute dispatch whose readback must hold exactly i * 3 + 7. Raises
    RuntimeError naming the device when the values are wrong or the dispatch fails."""
    info = adapter_info(warn)
    try:
        vals = compute_readback()
    except Exception as e:                                          # noqa: BLE001
        raise RuntimeError(f"GPU compute check failed on {info['description']}: {e}") from e
    flat = []
    for v in vals:
        flat.append(v[0] if isinstance(v, (list, tuple)) else v)
    bad = [i for i, v in enumerate(flat) if int(round(v)) != i * 3 + 7]
    if len(flat) != 64 or bad:
        raise RuntimeError(f"GPU compute check failed on {info['description']}: GPU compute readback returned "
                           f'incorrect values (first wrong at {bad[:3]} of {len(flat)})')
    info['compute_readback'] = 'passed'
    return info


if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from eidoblend.harness import gpu_check as _g
    try:
        print(json.dumps(_g.check_gpu()), flush=True)
        code = 0
    except Exception as e:                                          # noqa: BLE001
        print(f'[gpu] {e}', file=sys.stderr, flush=True)
        code = 1
    os._exit(code)
