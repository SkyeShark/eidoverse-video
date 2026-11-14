"""The stock finish's noise is MaterialX's noise_float, measured in an EEVEE render.

The WebGPU finishStock draws its broad grain and its patina with three's TSL mx_noise_float(p), which is MaterialX's
mx_perlin_noise_float: OSL's Perlin noise (Bob Jenkins' lookup3 hash of the lattice cell, the 12-direction gradient
pick, the quintic fade, scaled by 0.982). finish_stock draws them with Blender's Noise Texture at Detail 0, whose Fac
is 0.5 + 0.5 x that same noise. This renders the Noise Texture finish_stock builds over a 256 x 256 grid of points
(a plane seen square by an orthographic camera, its Object coordinates scaled and offset off the lattice, Standard
view, 32-bit EXR, one sample) and compares every pixel with a Python transcription of three's mx_noise.js (uint32
arithmetic) at the pixel's centre. EEVEE's render buffers hold half floats (a step of 4.9e-4 near 1), so the plane
emits Fac in red and fract(64 Fac) in green, and Fac is rebuilt from the two as (round(64 R - G) + G) / 64, good to
about 1e-5. Writes out/noise_materialx/ (the EXR and the difference over that precision as a PNG).

    bash run_blender.sh blender/tests/fabrication/test_finish_noise_materialx.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import os
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402

OUT = os.path.join(U.OUT, 'noise_materialx')
os.makedirs(OUT, exist_ok=True)
N = 256
SCALE = np.array([38.0 * .31, 27.0 * .31, 19.0])        # the broad grain's frequencies, over a 0.31 m plane
OFFSET = np.array([3.137, -5.291, 0.4189])               # off the lattice, and through negative cells
FINE = 64.0                                              # the green channel holds fract(FINE x Fac)


# ------------------------------------------------------------- three's mx_noise.js, transcribed (uint32 arithmetic) ---
M32 = np.uint64(0xFFFFFFFF)


def _u(x):
    return np.asarray(x, dtype=np.uint64) & M32


def _rotl(x, k):
    return ((x << np.uint64(k)) | (x >> np.uint64(32 - k))) & M32


def _bjfinal(a, b, c):
    c = _u(c ^ b)
    c = _u(c - _rotl(b, 14) + (M32 + np.uint64(1)))
    a = _u(a ^ c)
    a = _u(a - _rotl(c, 11) + (M32 + np.uint64(1)))
    b = _u(b ^ a)
    b = _u(b - _rotl(a, 25) + (M32 + np.uint64(1)))
    c = _u(c ^ b)
    c = _u(c - _rotl(b, 16) + (M32 + np.uint64(1)))
    a = _u(a ^ c)
    a = _u(a - _rotl(c, 4) + (M32 + np.uint64(1)))
    b = _u(b ^ a)
    b = _u(b - _rotl(a, 14) + (M32 + np.uint64(1)))
    c = _u(c ^ b)
    c = _u(c - _rotl(b, 24) + (M32 + np.uint64(1)))
    return c


def _hash(x, y, z):
    seed = np.uint64((0xdeadbeef + (3 << 2) + 13) & 0xFFFFFFFF)
    a = _u(seed + _u(x.astype(np.int64)))
    b = _u(seed + _u(y.astype(np.int64)))
    c = _u(seed + _u(z.astype(np.int64)))
    return _bjfinal(a, b, c)


def _gradient(h, x, y, z):
    h = h & np.uint64(15)
    u = np.where(h < 8, x, y)
    v = np.where(h < 4, y, np.where((h == 12) | (h == 14), x, z))
    return np.where(h & np.uint64(1), -u, u) + np.where(h & np.uint64(2), -v, v)


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def mx_perlin_noise_float(p):
    p = np.asarray(p, dtype=np.float32).astype(np.float64)
    X, Y, Z = (np.floor(p[..., k]).astype(np.int64) for k in range(3))
    fx, fy, fz = (p[..., k] - np.floor(p[..., k]) for k in range(3))
    u, v, w = _fade(fx), _fade(fy), _fade(fz)
    g = {}
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                g[i, j, k] = _gradient(_hash(X + i, Y + j, Z + k), fx - i, fy - j, fz - k)
    s1, t1, r1 = 1 - u, 1 - v, 1 - w
    r = (r1 * (t1 * (g[0, 0, 0] * s1 + g[1, 0, 0] * u) + v * (g[0, 1, 0] * s1 + g[1, 1, 0] * u))
         + w * (t1 * (g[0, 0, 1] * s1 + g[1, 0, 1] * u) + v * (g[0, 1, 1] * s1 + g[1, 1, 1] * u)))
    return 0.9820 * r


# ------------------------------------------------------------------------------------------------ the render ---
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = sc.render.resolution_y = N
sc.render.resolution_percentage = 100
sc.render.filter_size = 0.0
sc.eevee.taa_render_samples = 1
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0.0
sc.view_settings.gamma = 1.0
sc.render.dither_intensity = 0.0
sc.world = bpy.data.worlds.new('noise black')
sc.world.color = (0, 0, 0)
me = bpy.data.meshes.new('noise plane')
me.from_pydata([(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0)], [], [(0, 1, 2, 3)])
plane = bpy.data.objects.new('noise plane', me)
sc.collection.objects.link(plane)
cd = bpy.data.cameras.new('noise camera')
cd.type, cd.ortho_scale = 'ORTHO', 1.0
cam = bpy.data.objects.new('noise camera', cd)
cam.location = (0, 0, 2)
sc.collection.objects.link(cam)
sc.camera = cam

# the Noise Texture exactly as finish_stock builds it (fabrication.cutting.finish_stock's mx_noise), fed the scaled point
mat = bpy.data.materials.new('noise')
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
tc = nt.nodes.new('ShaderNodeTexCoord')
mp = nt.nodes.new('ShaderNodeMapping')
mp.vector_type = 'POINT'
mp.inputs['Scale'].default_value = tuple(SCALE)
mp.inputs['Location'].default_value = tuple(OFFSET)
noise = nt.nodes.new('ShaderNodeTexNoise')
noise.noise_dimensions = '3D'
noise.normalize = True
noise.inputs['Scale'].default_value = 1.0
noise.inputs['Detail'].default_value = 0.0
noise.inputs['Roughness'].default_value = 0.5
noise.inputs['Distortion'].default_value = 0.0
em = nt.nodes.new('ShaderNodeEmission')
out = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
nt.links.new(mp.outputs['Vector'], noise.inputs['Vector'])
# red: Fac; green: fract(FINE Fac), its digits below 1 / FINE (each channel is stored as a half float)
fine = nt.nodes.new('ShaderNodeMath')
fine.operation = 'MULTIPLY'
fine.inputs[1].default_value = FINE
frac = nt.nodes.new('ShaderNodeMath')
frac.operation = 'FRACT'
rgb = nt.nodes.new('ShaderNodeCombineColor')
nt.links.new(noise.outputs['Fac'], fine.inputs[0])
nt.links.new(fine.outputs[0], frac.inputs[0])
nt.links.new(noise.outputs['Fac'], rgb.inputs['Red'])
nt.links.new(frac.outputs[0], rgb.inputs['Green'])
nt.links.new(rgb.outputs['Color'], em.inputs['Color'])
nt.links.new(em.outputs[0], out.inputs['Surface'])
me.materials.append(mat)
exr = os.path.join(OUT, 'noise_fac.exr')
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'OPEN_EXR'
sc.render.image_settings.color_depth = '32'
sc.render.filepath = exr
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(exr)
px = np.empty(N * N * 4, np.float32)
img.pixels.foreach_get(px)
px = px.reshape(N, N, 4).astype(np.float64)                  # rows from the bottom
coarse, digits = px[..., 0], px[..., 1]
fac = (np.round(coarse * FINE - digits) + digits) / FINE     # Fac rebuilt: the whole 1/FINE steps from red, the rest green

c = (np.arange(N) + 0.5) / N - 0.5                           # pixel centres in the plane's object space
ox, oy = np.meshgrid(c, c)                                   # [row (y, from the bottom), column (x)]
p = np.stack([ox * SCALE[0] + OFFSET[0], oy * SCALE[1] + OFFSET[1], np.full(ox.shape, OFFSET[2])], -1)
want = 0.5 + 0.5 * mx_perlin_noise_float(p)
d = np.abs(fac - want)
d_coarse = np.abs(coarse - want)
# the measurement's precision at each pixel: green's half-float step (at most 2^-11 below 1) over FINE, rounded twice
# at most (the shading buffer, then the film); and the shading point in float32 (the Mapping node's o x scale + offset
# and the interpolated object coordinate: two float32 steps of each coordinate) times the noise's slope there
h = 1e-4
slope = [np.abs(0.5 * (mx_perlin_noise_float(p + np.eye(3)[k] * h) - mx_perlin_noise_float(p - np.eye(3)[k] * h)) / (2 * h))
         for k in range(3)]
dp = [2 * np.spacing(np.abs(p[..., k]).astype(np.float32)).astype(np.float64) + SCALE[k] * 2 ** -24 for k in range(3)]
bound = 2 * 2.0 ** -11 / FINE + sum(s * e for s, e in zip(slope, dp))
print(f'[noise] {N * N} pixels: Blender Noise Texture Fac vs 0.5 + 0.5 mx_noise_float: rebuilt from two channels max '
      f'{d.max():.2e}, mean {d.mean():.2e}, at most {(d / bound).max():.2f} of the precision at its pixel (that '
      f'precision {bound.min():.1e} .. {bound.max():.1e}); red alone, a half float, max {d_coarse.max():.2e}; the noise '
      f'spans {np.ptp(want):.3f}', flush=True)
a = np.clip(d / bound, 0, 1)
vis = bpy.data.images.new('noise diff', N, N, alpha=False)
vis.pixels.foreach_set(np.stack([a, a, a, np.ones_like(a)], -1).astype(np.float32).ravel())
vis.filepath_raw = os.path.join(OUT, 'noise_diff_over_precision.png')
vis.file_format = 'PNG'
vis.save()
U.check(f'the finish noise is MaterialX noise_float: {N * N} pixels of a {np.ptp(want):.2f}-wide pattern equal to it '
        f'within the measurement\'s precision at every pixel (max {d.max():.1e}, mean {d.mean():.1e}; precision '
        f'{bound.min():.1e} .. {bound.max():.1e})', (d <= bound).all() and np.ptp(want) > 0.5)
ok = U.summary('finish_noise_materialx')
print('ALL PASS' if ok else 'FAIL')
