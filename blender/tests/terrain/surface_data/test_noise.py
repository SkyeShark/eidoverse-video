"""The noise port (surface/noise.glsl, its twin surface/noise.py) against Blender's own nodes (SURFACING_DESIGN.md
5.4, package 1, item 2: within 1e-3):

    bash run_blender.sh blender/tests/terrain/surface_data/test_noise.py
    (queue it with EIDO_GPU_WRAP on a shared machine: blender/tests/_where.py)

1. GLSL against the twin: a compute kernel evaluates the variants below at 128 x 96 points scattered over a terrain's
   extent (world metres, heights to 2 km), against noise.py at the same points.
2. The twin against Blender's nodes: a 512 m plane at (3000, -2000, 37.5) under an orthographic camera, 256 x 256
   pixels of 2 m, its material an Emission of the node (Object coordinates, the terrain's frame), rendered with
   EEVEE at one sample, filter 0, Standard view, to a float EXR; each pixel against the twin at its centre. The
   Voronoi colour is compared away from cell edges (where the cell a pixel centre falls in is ambiguous to a
   sub-pixel jitter).
Writes out/surface_data/noise.json. Exit 0 when both pass.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import numpy as np  # noqa: E402

from eidoblend.terrain.surface import noise as BN  # noqa: E402

OUT = os.path.join(HERE, '..', 'out', 'surface_data')
F = np.float32
# (name, kind, args): kind n3 = Noise 3D (scale, detail, roughness), n4 = Noise 4D (w, scale, detail, roughness),
# v2 / v3 = Voronoi F1 colour (scale)
VARIANTS = [('noise3_d2', 'n3', (1 / 40.0, 2.0, 0.5)), ('noise4_d2', 'n4', (3.7, 1 / 55.0, 2.0, 0.5)),
            ('fbm3_d5', 'n3', (1 / 90.0, 5.0, 0.6)), ('noise3_d2p5', 'n3', (1 / 25.0, 2.5, 0.55)),
            ('vor2', 'v2', (1 / 30.0,)), ('vor3', 'v3', (1 / 45.0,))]


def twin(kind, args, co):
    if kind == 'n3':
        return BN.noise_node3(co, *args)
    if kind == 'n4':
        w, s, d, r = args
        return BN.noise_node4(co, w, s, d, r)
    if kind == 'v2':
        return BN.voronoi_f1_colour2(co[..., :2], args[0], 1.0)[..., 0]
    return BN.voronoi_f1_colour3(co, args[0], 1.0)[..., 0]


def glsl_call(kind, args):
    f = lambda v: repr(float(v))                                       # noqa: E731
    if kind == 'n3':
        return f'bn_noise_node3(co, {f(args[0])}, {f(args[1])}, {f(args[2])})'
    if kind == 'n4':
        return f'bn_noise_node4(co, {f(args[0])}, {f(args[1])}, {f(args[2])}, {f(args[3])})'
    if kind == 'v2':
        return f'bn_voronoi_f1_colour2(co.xy, {f(args[0])}, 1.0).x'
    return f'bn_voronoi_f1_colour3(co, {f(args[0])}, 1.0).x'


def gpu_parity():
    from eidoblend.terrain.core import gpu as G
    rng = np.random.default_rng(3)
    H, W = 96, 128
    co = np.stack([rng.uniform(-16000, 16000, (H, W)), rng.uniform(-16000, 16000, (H, W)),
                   rng.uniform(-200, 2000, (H, W))], -1).astype(F)
    out = []
    for name, kind, args in VARIANTS:
        src = ('//! sampler coT\n//! image outN rgba32f\n' + BN.source() +
               '\nvoid main() {\n  ivec2 p = ivec2(gl_GlobalInvocationID.xy);\n  ivec2 n = textureSize(coT, 0);\n'
               '  if (!inside(p, n)) return;\n  vec3 co = texelFetch(coT, p, 0).xyz;\n'
               f'  imageStore(outN, p, vec4({glsl_call(kind, args)}, 0.0, 0.0, 0.0));\n}}\n')
        k = G.kernel(source=src, name=f'noise_{name}')
        o = G.empty((H, W), 4)
        G.run(k, None, samplers={'coT': G.texture(np.concatenate([co, np.zeros((H, W, 1), F)], -1))},
              images={'outN': o})
        got = G.read(o)[..., 0]
        want = twin(kind, args, co)
        d = np.abs(got.astype(np.float64) - want)
        out.append(dict(variant=name, max=float(d.max()), p999=float(np.percentile(d, 99.9)),
                        frac_over_1e3=float((d > 1e-3).mean()), ok=bool(np.percentile(d, 99.9) <= 1e-3)))
        print(f'[gpu] {name}: max {d.max():.2e}, p99.9 {np.percentile(d, 99.9):.2e}', flush=True)
    return out


def render_parity():
    import bpy
    import OpenImageIO as oiio
    scene = bpy.data.scenes.new('noise_probe')
    X0, Y0, Z0, S, N = 3000.0, -2000.0, 37.5, 512.0, 256
    me = bpy.data.meshes.new('plane')
    me.from_pydata([(X0 - S / 2, Y0 - S / 2, Z0), (X0 + S / 2, Y0 - S / 2, Z0), (X0 + S / 2, Y0 + S / 2, Z0),
                    (X0 - S / 2, Y0 + S / 2, Z0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new('plane', me)
    scene.collection.objects.link(ob)
    cam = bpy.data.cameras.new('cam')
    cam.type = 'ORTHO'
    cam.ortho_scale = S
    cam.clip_end = 10000.0
    co = bpy.data.objects.new('cam', cam)
    co.location = (X0, Y0, Z0 + 1000.0)
    scene.collection.objects.link(co)
    scene.camera = co
    r = scene.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x = r.resolution_y = N
    r.resolution_percentage = 100
    r.filter_size = 0.0
    scene.eevee.taa_render_samples = 1
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.display_settings.display_device = 'sRGB'
    r.image_settings.file_format = 'OPEN_EXR'
    r.image_settings.color_depth = '32'
    r.image_settings.color_mode = 'RGBA'
    scene.world = bpy.data.worlds.new('w')
    xs = X0 - S / 2 + (np.arange(N) + 0.5) * (S / N)
    ys = Y0 - S / 2 + (np.arange(N) + 0.5) * (S / N)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.stack([XX, YY, np.full_like(XX, Z0)], -1).astype(F)
    out = []
    for name, kind, args in VARIANTS:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        tc = nt.nodes.new('ShaderNodeTexCoord')
        if kind in ('n3', 'n4'):
            tx = nt.nodes.new('ShaderNodeTexNoise')
            tx.noise_dimensions = '3D' if kind == 'n3' else '4D'
            if kind == 'n3':
                s, d, rg = args
            else:
                w, s, d, rg = args
                tx.inputs['W'].default_value = w
            tx.inputs['Scale'].default_value = s
            tx.inputs['Detail'].default_value = d
            tx.inputs['Roughness'].default_value = rg
            val = tx.outputs['Fac']
        else:
            tx = nt.nodes.new('ShaderNodeTexVoronoi')
            tx.voronoi_dimensions = '2D' if kind == 'v2' else '3D'
            tx.feature = 'F1'
            tx.inputs['Scale'].default_value = args[0]
            tx.inputs['Randomness'].default_value = 1.0
            val = tx.outputs['Color']
        nt.links.new(tc.outputs['Object'], tx.inputs['Vector'])
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Strength'].default_value = 1.0
        nt.links.new(val, em.inputs['Color'])
        mo = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(em.outputs['Emission'], mo.inputs['Surface'])
        me.materials.clear()
        me.materials.append(mat)
        path = os.path.join(OUT, 'noise_render', f'{name}.exr')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        r.filepath = path
        bpy.ops.render.render(write_still=True, scene=scene.name)
        inp = oiio.ImageInput.open(path)
        img = np.asarray(inp.read_image('float'), np.float64)[::-1]
        inp.close()
        got = img[..., 0]
        want = twin(kind, args, pts).astype(np.float64)
        d = np.abs(got - want)
        if kind in ('v2', 'v3'):
            # away from cell edges: the twin's value equal over the 3 x 3 neighbourhood
            pad = np.pad(want, 1, mode='edge')
            same = np.ones(want.shape, bool)
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    same &= pad[1 + dj:1 + dj + N, 1 + di:1 + di + N] == want
            d = d[same]
        rec = dict(variant=name, max=float(d.max()), p999=float(np.percentile(d, 99.9)), mean=float(d.mean()),
                   ok=bool(np.percentile(d, 99.9) <= 1e-3))
        out.append(rec)
        print(f'[render] {name}: max {d.max():.2e}, p99.9 {np.percentile(d, 99.9):.2e}, mean {d.mean():.2e}',
              flush=True)
    return out


def main():
    t0 = time.perf_counter()
    rep = dict(gpu=gpu_parity(), render=render_parity())
    rep['ok'] = all(r['ok'] for r in rep['gpu'] + rep['render'])
    rep['seconds'] = round(time.perf_counter() - t0, 1)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'noise.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1)
    print(f"[test_noise] {'PASS' if rep['ok'] else 'FAIL'}", flush=True)
    return 0 if rep['ok'] else 1


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
