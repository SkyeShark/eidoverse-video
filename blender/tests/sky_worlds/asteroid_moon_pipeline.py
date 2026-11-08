"""The asteroid moon's bake-once pipeline and runtime loader, end to end.

bake_asteroid_moon() runs on a CC0 rocky ground set from the shared texture cache (Ground106: a matching tileable height
and albedo, standing in for the WebGPU recipe's AI-generated pair), writes the three artifacts into out/asteroid/,
then make_asteroid_moon() loads them and EEVEE renders the result under a low sun from two sides, plus the atlases.
Checks: the runtime mesh is three's icosahedron(24) (37 500 vertices), the high poly is 16x that, the atlases cover
the UV square, the normal atlas holds unit normals that agree with the runtime mesh's.

    bash run_blender.sh blender/tests/sky_worlds/asteroid_moon_pipeline.py [--size 1024] [--res 640x640]
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky.asteroid_moon import bake_asteroid_moon, make_asteroid_moon  # noqa: E402
from eidoblend.sky.nodes import key_values  # noqa: E402
from eidoblend.sky import moon_materials as MM  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--size', type=int, default=1024)
ap.add_argument('--res', default='640x640')
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'asteroid')
os.makedirs(OUT, exist_ok=True)
TEX = os.path.normpath(os.path.join(REPO, '..', 'eidoverse-video-prealpha-0.01', 'eidoverse', 'assets', 'cache',
                                    'textures', 'Ground106_2k'))


def check(name, ok, detail=''):
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)
    return ok


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
height = os.path.join(TEX, 'Ground106_Displacement.jpg')
albedo = os.path.join(TEX, 'Ground106_Color.jpg')
res = bake_asteroid_moon(height, albedo, out_dir=OUT, opts=dict(bakeSize=args.size))
ok = True
ok &= check('runtime mesh is icosahedron(24) non-indexed', res['runtime_vertices'] == 37500,
            '%d vertices' % res['runtime_vertices'])
ok &= check('high poly is 16 sub-triangles per base face', res['bake_triangles'] == 12500 * 16,
            '%d triangles' % res['bake_triangles'])
alb = res['albedo']
clear = np.abs(alb[..., :3] - np.array([0.40, 0.36, 0.32])).sum(-1) < 1e-4
ok &= check('albedo atlas covers the UV square', clear.mean() < 0.02, 'clear texels %.4f' % clear.mean())
na = res['normal_atlas'][..., :3] * 2 - 1
ln = np.linalg.norm(na, axis=-1)
# the JS writes the high poly's interpolated vertex normal (hnrm * 0.5 + 0.5, not renormalised): lengths sit just
# under 1 inside each triangle, and the runtime material normalises after sampling
ok &= check('normal atlas holds the interpolated high-poly normals (as the JS: normalised at runtime)',
            0.95 < np.median(ln) <= 1.001, 'median length %.4f' % np.median(ln))
# the atlas normal at each runtime vertex's UV against the runtime mesh's own normal
uv = res['uvs']
H, W = na.shape[:2]
px = np.clip((np.mod(uv[:, 0], 1.0) * W).astype(int), 0, W - 1)
py = np.clip((uv[:, 1] * H).astype(int), 0, H - 1)
agree = (na[py, px] * res['normals']).sum(-1)
ok &= check('atlas normals agree with the runtime mesh', np.median(agree) > 0.9, 'median cos %.3f' % np.median(agree))
for f in ('asteroid_moon_mesh.f32', 'asteroid_moon_baked.png', 'asteroid_moon_normal.png'):
    ok &= check('artifact ' + f, os.path.getsize(os.path.join(OUT, f)) > 1000)

# ---- runtime: load the three artifacts and look at them ----
ob = make_asteroid_moon(os.path.join(OUT, 'asteroid_moon_mesh.f32'), os.path.join(OUT, 'asteroid_moon_baked.png'),
                        os.path.join(OUT, 'asteroid_moon_normal.png'), scene=sc)
W_, H_ = (int(v) for v in args.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y = W_, H_
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = 'AgX'
world = bpy.data.worlds.new('black')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
sc.world = world
cd = bpy.data.cameras.new('cam')
cd.lens = 85
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
_ng, handles = MM.moon_keys_group()
for name, sun in (('lit', (0.6, -0.5, 0.62)), ('terminator', (1.0, 0.15, 0.1))):
    n = math.sqrt(sum(c * c for c in sun))
    sun = tuple(c / n for c in sun)
    for k, v in dict(sun_dir=sun, sun_col=(1.0, 0.95, 0.9), gain=1.6, fade=1.0).items():
        nd = handles[k]
        if nd.bl_idname == 'ShaderNodeCombineXYZ':
            for ax, c in zip('XYZ', v):
                nd.inputs[ax].default_value = c
        else:
            nd.outputs[0].default_value = v
    cam.location = (0.0, -6.0, 0.0)
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)
    sc.render.filepath = os.path.join(OUT, 'asteroid_moon_%s.png' % name)
    bpy.ops.render.render(write_still=True)
print('PASS asteroid pipeline' if ok else 'FAIL asteroid pipeline')
