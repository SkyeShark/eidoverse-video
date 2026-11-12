"""engine_march: the engine's own raymarch of an SDF, run in Blender: the reference the SDF tests set beside EEVEE.

createSdfObject drew each SDF by sphere tracing inside its bounds box, per pixel, with the quality preset's
maxSteps / surfEps / stepScale / maxDist, then coloured the hit with the example's own shade() (its hand lights,
soft shadow, fresnel). createSdfVolume marched its sample() front to back through the box and reshaped the sum with
post(). MarchProgram is an SDF's program (eidoblend.sdf.gpu_eval.SdfProgram) with those two fragment shaders as
kernels, driven by a Blender camera moved into the SDF's local three.js frame.

    import engine_march as EM                                  # tests/sdf on sys.path (_common, _vcommon)
    img = EM.march(obj, camera, 480, 270, samples=4, t=1.0)    # linear (H, W, 4), row 0 at the bottom
    img = EM.march(vol, camera, samples=2, t=1.0)              # a volume: premultiplied
    img = EM.march(fx, camera, samples=2, t=3.0)               # a NuclearExplosion: its volumes composited
    EM.save_png(path, img)

march() takes an SdfObject, an SdfVolume or a NuclearExplosion. t sets the SDF's own uTime as well (its program's,
as the bake reads it). values={name: value} sets uniforms for the march alone (the explosion ring's engine look:
{'uFoldGamma': 1.0}, its sample() unfolded, with its post).
"""

from __future__ import annotations

import os
import sys
import weakref

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(os.path.dirname(HERE))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

from eidoblend.sdf import gpu_eval  # noqa: E402
from eidoblend.sdf.solid import T2B  # noqa: E402

# createSdfVolume's march, from a Blender camera in the volume's local three frame: front-to-back premultiplied
# accumulation through the bounds box, the sample's own alpha and step, early out at 0.99, the optional post(sum),
# and the engine's discard below 0.01.
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
        // emission, plus the scattering colour under a flat ambient (no shadowing: the march shows the medium's
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
# moved into the object's local three frame. With sdfUseClip on (an example cut_by_bounds, whose surface runs past
# its box on purpose) it marches the field cut by the bounds box, the solid the mesh is; the engine's own march walked
# back out of the box there and drew the uncut surface in front.
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

# the marches' own uniforms, beside the program's: (name, type, default)
MARCH_UNIFORMS = [
    ('uMaxSteps', 'float', 128.0),
    ('uSurfEps', 'float', 0.001),
    ('uStepScale', 'float', 0.85),
    ('uMaxDist', 'float', 100.0),
    ('sdfVolSteps', 'float', 96.0),
    ('sdfMediumStep', 'float', 0.01),
    ('sdfMediumAmbient', 'vec3', (0.0, 0.0, 0.0)),
    ('sdfCamFwd', 'vec3', (0.0, 0.0, -1.0)),
    ('sdfCamRight', 'vec3', (1.0, 0.0, 0.0)),
    ('sdfCamUp', 'vec3', (0.0, 1.0, 0.0)),
    ('sdfCamTan', 'vec2', (0.5, 0.5)),
    ('sdfImageSize', 'vec2', (1.0, 1.0)),
    ('sdfJitter', 'vec2', (0.0, 0.0)),
]
_ENGINE = {n for n, _t, _d in gpu_eval.ENGINE_UNIFORMS}


class MarchProgram(gpu_eval.SdfProgram):
    """An SDF's program with the engine's two marches as kernels: 'raymarch' (map, then shade at the hit) and
    'volume_raymarch' (sample or medium along the ray, then post), next to the program's own kernels."""

    def __init__(self, prog):
        """The same stages, textures, environment and uniforms as `prog`, plus the marches' uniforms."""
        own = {n: (t, prog.values[n]) for n, t, _slot in prog.layout if n not in _ENGINE}
        for n, t, d in MARCH_UNIFORMS:
            own.setdefault(n, (t, d))
        super().__init__(map=prog.map, shade=prog.shade, sample=prog.sample, medium=prog.medium, post=prog.post,
                         extra=prog.extra, uniforms=own, textures=prog.textures, defines=prog.defines,
                         label=f'{prog.label} (engine march)', shade_as=None)
        stage = 'sample' if prog.sample is not None else 'medium'
        head = ''.join(('#define SDF_VOLUME_MEDIUM 1\n' if stage == 'medium' else '',
                        '#define SDF_HAS_POST 1\n' if gpu_eval._is_glsl(prog.post) else ''))
        self.KERNELS = dict(gpu_eval.KERNELS, raymarch=(KERNEL_RAYMARCH, 1, ('field', 'shade')),
                            volume_raymarch=(head + KERNEL_VOLUME_RAYMARCH, 1, (stage, 'post')))
        self.sync(prog)

    def sync(self, prog):
        """Take the program's current uniform values and environment map."""
        for n, v in prog.values.items():
            if n in self.values:
                self.values[n] = v
        self._env = prog._env


_PROGRAMS = weakref.WeakKeyDictionary()      # SdfProgram -> (its stages' signature, MarchProgram)


def _signature(prog):
    return (prog.map, prog.shade, prog.sample, prog.medium, prog.post, prog.extra,
            tuple(sorted(prog.defines.items())), tuple((k, id(v)) for k, v in sorted(prog.textures.items())))


def march_program(prog):
    """The MarchProgram of an SDF program, compiled once while its stages stay the same; its values synced."""
    sig = _signature(prog)
    have = _PROGRAMS.get(prog)
    if have is None or have[0] != sig:
        if have is not None:
            have[1].free()
        have = (sig, MarchProgram(prog))
        _PROGRAMS[prog] = have
    else:
        have[1].sync(prog)
    return have[1]


# ------------------------------------------------------------------------------------------------- the camera ---
def _local_frame(obj):
    """4x4: Blender world -> the SDF's local three frame."""
    mw = np.array(obj.matrix_world, dtype=np.float64)
    t2b = np.eye(4)
    t2b[:3, :3] = T2B
    return np.linalg.inv(mw @ t2b)


def camera_rays(scene, camera, obj):
    """(position, forward, right, up, (tan_x, tan_y)) of a Blender camera in obj's local three frame."""
    inv = _local_frame(obj)
    cw = np.array(camera.matrix_world, dtype=np.float64)
    pos = (inv @ cw[:, 3])[:3]
    rot = inv[:3, :3] @ cw[:3, :3]
    right, up, back = rot[:, 0], rot[:, 1], rot[:, 2]
    frame = camera.data.view_frame(scene=scene)
    xs = [abs(v.x) for v in frame]
    ys = [abs(v.y) for v in frame]
    z = abs(frame[0].z)
    tx, ty = max(xs) / z, max(ys) / z
    # unit-length axes, so tan scales the ray exactly (non-uniform object scale stays in the lengths below)
    return pos, -back, right, up, (tx, ty)


def model_matrix_three(obj):
    """The object's world matrix in three's axes (local three frame -> three world), as uModelMatrix: what
    sdfReflectWorld and the originals' mat3(uModelMatrix) * n read."""
    mw = np.array(obj.matrix_world, dtype=np.float64)
    t2b = np.eye(4)
    t2b[:3, :3] = T2B
    return np.linalg.inv(t2b) @ mw @ t2b


def _camera_values(scene, camera, obj, width, height):
    import bpy
    bpy.context.view_layer.update()          # a camera or object moved since the last update has a stale matrix_world
    pos, fwd, right, up, tan = camera_rays(scene, camera, obj)
    m3 = model_matrix_three(obj)
    cw = np.array(camera.matrix_world, dtype=np.float64)[:3, 3]
    cam_three_world = (cw[0], cw[2], -cw[1])
    return {
        'sdfCameraUniform': tuple(float(x) for x in pos),
        'cameraPositionWorld': tuple(float(x) for x in cam_three_world),
        'uModelMatrix': tuple(float(x) for x in m3.T.ravel()),
        'sdfCamFwd': tuple(float(x) for x in fwd), 'sdfCamRight': tuple(float(x) for x in right),
        'sdfCamUp': tuple(float(x) for x in up), 'sdfCamTan': (float(tan[0]), float(tan[1])),
        'sdfImageSize': (float(width), float(height)),
    }


def _accumulate(prog, kind, width, height, samples):
    acc = np.zeros((height * width, 4), np.float64)
    rng = np.random.default_rng(7)
    dummy = np.zeros((width * height, 3), np.float32)
    for s in range(max(1, int(samples))):
        j = (0.0, 0.0) if s == 0 else tuple(rng.uniform(-1.0, 1.0, 2))
        prog.values['sdfJitter'] = (float(j[0]), float(j[1]))
        acc += prog.eval(kind, dummy, width=width)[0]
    return (acc / max(1, int(samples))).reshape(height, width, 4).astype(np.float32)


# --------------------------------------------------------------------------------------------------- marches ---
def solid_march(sdf, camera, width=480, height=270, samples=4, t=None, scene=None, values=None):
    """Linear (H, W, 4) image of sdf (an SdfObject) through the engine's raymarch + shade(); alpha = coverage."""
    import bpy
    scene = scene or bpy.context.scene
    if not gpu_eval._is_glsl(sdf.program.map) or not gpu_eval._is_glsl(sdf.program.shade):
        raise ValueError(f'{sdf.name}: the engine march runs a GLSL map() and shade()')
    if t is not None:
        sdf.program.values['uTime'] = float(t)
    prog = march_program(sdf.program)
    sp = sdf.spec
    prog.values.update(_camera_values(scene, camera, sdf.object, width, height))
    prog.values.update({
        'uMaxSteps': float(sp.max_steps), 'uSurfEps': float(sp.surf_eps), 'uStepScale': float(sp.step_scale),
        'uMaxDist': float(sp.max_dist), 'sdfNormalH': 0.0004,
        'sdfClipMin': tuple(float(x) for x in sp.bounds_min), 'sdfClipMax': tuple(float(x) for x in sp.bounds_max),
        # the engine marched the bare map; an example cut_by_bounds is the field cut by its box, as its mesh is
        'sdfUseClip': 1.0 if getattr(sp, 'cut_by_bounds', False) else 0.0,
    })
    for n, v in (values or {}).items():
        prog.set_uniform(n, v)
    return _accumulate(prog, 'raymarch', width, height, samples)


def volume_march(vol, camera, width=480, height=270, samples=4, t=None, scene=None, medium_step=None,
                 ambient=(0.0, 0.0, 0.0), values=None):
    """Linear premultiplied (H, W, 4) image of vol (an SdfVolume) through createSdfVolume's own march: its sample()
    (alpha, step) or, for a medium() volume, an emission-absorption march at medium_step with its scattering colour
    under a flat `ambient` light; then post(sum)."""
    import bpy
    scene = scene or bpy.context.scene
    stage = vol.spec.sample if vol.mode == 'sample' else vol.spec.medium
    if not isinstance(stage, str):
        raise ValueError(f'{vol.name}: the engine march runs GLSL; a Python {vol.mode}() has none')
    if t is not None:
        vol.program.values['uTime'] = float(t)
    prog = march_program(vol.program)
    prog.values.update(_camera_values(scene, camera, vol.object, width, height))
    prog.values.update({
        'sdfVolSteps': float(vol.spec.steps),
        'sdfMediumStep': float(medium_step or vol.voxel),
        'sdfMediumAmbient': tuple(float(x) for x in ambient),
        'sdfClipMin': tuple(float(x) for x in vol.spec.bounds_min),
        'sdfClipMax': tuple(float(x) for x in vol.spec.bounds_max),
    })
    for n, v in (values or {}).items():
        prog.set_uniform(n, v)
    return _accumulate(prog, 'volume_raymarch', width, height, samples)


def explosion_march(fx, camera, width=480, height=270, samples=2, t=None, values=None):
    """A NuclearExplosion's own march from a Blender camera (premultiplied linear (H, W, 4)): each volume's march,
    composited front to back by the camera distance of its box centre."""
    from mathutils import Vector
    cam = camera.matrix_world.translation
    order = sorted(fx.volumes, key=lambda v: (v.object.matrix_world @ Vector(0.5 * (v.lo + v.hi)) - cam).length)
    out = None
    for vol in order:
        img = volume_march(vol, camera, width, height, samples, t=t, values=values)
        out = img if out is None else out + img * (1.0 - out[..., 3:4])
    return out


def march(x, camera, width=480, height=270, samples=4, t=None, **kw):
    """The engine's march of an SdfObject, an SdfVolume or a NuclearExplosion (see the module docstring)."""
    from eidoblend.sdf.nuclear_explosion import NuclearExplosion
    from eidoblend.sdf.volume import SdfVolume
    if isinstance(x, NuclearExplosion):
        return explosion_march(x, camera, width, height, samples, t=t, **kw)
    if isinstance(x, SdfVolume):
        return volume_march(x, camera, width, height, samples, t=t, **kw)
    return solid_march(x, camera, width, height, samples, t=t, **kw)


def save_png(path, img, exposure=0.0):
    """A linear (H, W, 4) image (row 0 at the bottom) to an 8-bit sRGB PNG (the engine's display encoding),
    composited over black."""
    import OpenImageIO as oiio
    a = np.asarray(img, np.float64)[::-1]
    rgb = np.clip(a[..., :3] * (2.0 ** exposure), 0.0, 1.0)
    srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.ascontiguousarray((srgb * 255 + 0.5).astype(np.uint8))
    h, w = data.shape[:2]
    out = oiio.ImageOutput.create(path)
    out.open(path, oiio.ImageSpec(w, h, 3, 'uint8'))
    out.write_image(data)
    out.close()
