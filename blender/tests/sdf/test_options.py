"""Every create_sdf_object option the examples do not exercise, in one lit scene.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_options.py

Left to right in out/opt_scene.png: a peanut written in PYTHON (SDF_NP map and surface), a GLSL shape on the 'vertex'
carrier with 'vertex' normals, a two-material SDF whose box takes a Blender material by id (materials={2: mat}), a
shape textured through a sampler (textures={'uChecker': array}) with a #define, and a live uniform (set_uniform)
rebuilt bigger. The world is an equirect sky bound by register_sdf_helper, so the reference raymarch's
sampleEnvMap() reads it (out/opt_env_ref.png). PASS lines for each, plus quality presets, bounds_report, a custom
register_example, help(), and the mesher's own options measured on a box's exact corners (voxel, refine, qef_lambda,
brick, lipschitz_k, texels). `-- render=0` runs everything but the scene render.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402
from eidoblend.common import asset_path  # noqa: E402
from eidoblend.sdf import SDF_NP as S  # noqa: E402

CACHE = os.path.join(C.OUT, 'cache_opt')
sc = C.stage(1280, 540, 16, sun_energy=2.5, floor_color=(0.22, 0.22, 0.22))
w = sc.world
nt = w.node_tree
env = nt.nodes.new('ShaderNodeTexEnvironment')
env.image = bpy.data.images.load(asset_path('sky', 'kloppenheim_puresky_ldr.png'))
nt.links.new(env.outputs['Color'], nt.nodes['Background'].inputs['Color'])
nt.nodes['Background'].inputs['Strength'].default_value = 1.0


# ---- 1. Python map + surface (the SDF_NP path) ------------------------------------------------------------------
def peanut_map(p):
    a = S.sd_sphere(p - S.vec3(-0.25, 0.35, 0.0), 0.3)
    b = S.sd_sphere(p - S.vec3(0.25, 0.35, 0.0), 0.3)
    return S.smin(a, b, 0.2) + (S.fbm(p * 9.0) - 0.5) * 0.01, 1.0


def peanut_surface(p, n, mat):
    shell = S.mix(S.vec3(0.55, 0.36, 0.18), S.vec3(0.78, 0.6, 0.38), S.fbm(p * 14.0)[:, None])
    return {'albedo': shell, 'roughness': 0.75}


py = sdf.create_sdf_object(map=peanut_map, surface=peanut_surface, bounds={'min': [-0.6, 0.0, -0.35], 'max': [0.6, 0.7, 0.35]},
                           cells=120, name='opt_python', cache_dir=CACHE, location=(-2.6, 0, 0))
py.place_on_ground(0.0)
C.check('python map/surface builds', py.stats.get('quads', 0) > 1000, f'{py.stats.get("quads")} quads, atlas {py.stats.get("atlas")}')

# ---- 2. vertex carrier + vertex normals ----------------------------------------------------------------------------
TWIST = r"""
vec2 map(vec3 p) {
    vec3 q = opRotateY(p, p.y * 2.2);
    return vec2(sdRoundBox(q - vec3(0.0, 0.45, 0.0), vec3(0.22, 0.42, 0.22), 0.05), 1.0);
}"""
TWIST_SURF = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    SdfSurface s = sdfSurface(mix(vec3(0.1, 0.35, 0.8), vec3(0.9, 0.9, 0.95), smoothstep(0.2, 0.8, p.y)), 0.3);
    s.metallic = 0.6;
    return s;
}"""
vx = sdf.create_sdf_object(map=TWIST, surface=TWIST_SURF, bounds={'min': [-0.4, 0.0, -0.4], 'max': [0.4, 0.95, 0.4]},
                           cells=160, carrier='vertex', normals='vertex', name='opt_vertex', cache_dir=CACHE,
                           location=(-1.3, 0, 0))
vx.place_on_ground(0.0)
attrs = [a.name for a in vx.object.data.attributes]
C.check('vertex carrier: channels as point attributes', 'sdf_albedo' in attrs and vx.material['sdf_carrier'] == 'vertex',
        f'{[a for a in attrs if a.startswith("sdf_")]}, constants {vx.stats.get("constants")}')

# ---- 3. materials by id ----------------------------------------------------------------------------------------------
TWO = r"""
vec2 map(vec3 p) {
    vec2 a = vec2(sdSphere(p - vec3(0.0, 0.62, 0.0), 0.28), 1.0);
    vec2 b = vec2(sdBox(p - vec3(0.0, 0.2, 0.0), vec3(0.3, 0.2, 0.3)), 2.0);
    return opU(a, b);
}"""
gold = bpy.data.materials.new('opt_gold')
gold.use_nodes = True
gb = gold.node_tree.nodes['Principled BSDF']
gb.inputs['Base Color'].default_value = (1.0, 0.71, 0.29, 1.0)
gb.inputs['Metallic'].default_value = 1.0
gb.inputs['Roughness'].default_value = 0.25
two = sdf.create_sdf_object(map=TWO, surface='SdfSurface surface(vec3 p, vec3 n, float mat) { return sdfSurface(vec3(0.8, 0.1, 0.1), 0.4); }',
                            bounds={'min': [-0.35, 0.0, -0.35], 'max': [0.35, 0.92, 0.35]}, cells=140,
                            materials={2: gold}, name='opt_two', cache_dir=CACHE, location=(0.0, 0, 0))
two.place_on_ground(0.0)
idx = np.empty(len(two.object.data.polygons), np.int32)
two.object.data.polygons.foreach_get('material_index', idx)
C.check('materials by id', set(np.unique(idx).tolist()) == {0, 1} and two.object.data.materials[1] == gold,
        f'{int((idx == 1).sum())} faces gold, {int((idx == 0).sum())} baked')

# ---- 4. textures + defines -------------------------------------------------------------------------------------------
chk = np.zeros((64, 64, 4), np.float32)
chk[..., 3] = 1
yy, xx = np.mgrid[0:64, 0:64]
chk[((xx // 8 + yy // 8) % 2) == 0, :3] = 1.0
TEX_SURF = r"""
SdfSurface surface(vec3 p, vec3 n, float mat) {
    vec2 uv = vec2(atan(p.z, p.x) / 6.2831853 + 0.5, p.y * 1.4);
    vec3 c = texture(uChecker, uv).rgb;
#ifdef OPT_WARM
    c *= vec3(1.0, 0.75, 0.45);
#endif
    return sdfSurface(c, 0.5);
}"""
coll = bpy.data.collections.new('opt_props')
sc.collection.children.link(coll)
tx = sdf.create_sdf_object(map='vec2 map(vec3 p) { return vec2(sdCapsule(p, vec3(0.0, 0.25, 0.0), vec3(0.0, 0.7, 0.0), 0.25), 1.0); }',
                           surface=TEX_SURF, textures={'uChecker': chk}, defines={'OPT_WARM': 1},
                           bounds={'min': [-0.3, 0.0, -0.3], 'max': [0.3, 0.97, 0.3]}, cells=140, pack_images=True,
                           name='opt_tex', cache_dir=CACHE, location=(1.3, 0, 0), scene=sc, collection=coll,
                           build=False)
C.check('build=False defers the mesh', len(tx.object.data.vertices) == 0, 'no mesh until build()')
tx.build(t=0.0)
tx.place_on_ground(0.0)
C.check('textures + defines', tx.stats.get('quads', 0) > 1000 and 'base' in tx.images, f'images {sorted(tx.images)}')
C.check('pack_images + collection', all(im.packed_file is not None for im in tx.images.values()) and
        tx.object.name in coll.objects, f'{len(tx.images)} images packed, in {coll.name}')

# ---- 5. a live uniform ---------------------------------------------------------------------------------------------------
UMAP = 'vec2 map(vec3 p) { return vec2(sdSphere(p - vec3(0.0, uRadius, 0.0), uRadius), 1.0); }'
USURF = 'SdfSurface surface(vec3 p, vec3 n, float mat) { return sdfSurface(uTint, 0.35); }'
un = sdf.create_sdf_object(map=UMAP, surface=USURF, uniforms={'uRadius': 0.2, 'uTint': ('color', '#3cbf6a')},
                           bounds={'min': [-0.5, 0.0, -0.5], 'max': [0.5, 1.0, 0.5]}, cells=100, name='opt_uniform',
                           cache_dir=CACHE, location=(2.6, 0, 0))
r0 = un.bounds_report()['mesh_max'][1]
un.set_uniform('radius', 0.4).build()
un.place_on_ground(0.0)
r1 = un.bounds_report()['mesh_max'][1]
C.check('set_uniform + rebuild', abs(r0 - 0.4) < 0.02 and abs(r1 - 0.8) < 0.02, f'top {r0:.3f} -> {r1:.3f} m')

# ---- 6. bounds_report, quality presets, register_example, help ---------------------------------------------------------
tight = sdf.create_sdf_object(map='vec2 map(vec3 p) { return vec2(sdSphere(p, 0.5), 1.0); }',
                              bounds={'min': [-0.4, -0.4, -0.4], 'max': [0.4, 0.4, 0.4]}, cells=64, carrier='vertex',
                              name='opt_tight', cache_dir=CACHE, location=(0, 5, 0))
C.check('bounds_report flags a clipped shape', tight.bounds_report()['clipped'], str(tight.bounds_report()['gap_min']))
qs = {}
for q in ('fast', 'balanced'):
    o = sdf.create_sdf_object(map='vec2 map(vec3 p) { return vec2(sdTorus(p, vec2(0.4, 0.12)), 1.0); }', quality=q,
                              bounds={'min': [-0.55, -0.15, -0.55], 'max': [0.55, 0.15, 0.55]}, carrier='vertex',
                              name=f'opt_q_{q}', cache_dir=CACHE, location=(0, 6, 0))
    qs[q] = (o.voxel, o.stats['quads'])
C.check('quality presets set the voxel', qs['fast'][0] > qs['balanced'][0] and qs['fast'][1] < qs['balanced'][1],
        f'fast {qs["fast"][0] * 1000:.2f} mm / {qs["fast"][1]} quads, balanced {qs["balanced"][0] * 1000:.2f} mm / {qs["balanced"][1]} quads')
mixed = sdf.create_sdf_object(map='vec2 map(vec3 p) { return vec2(sdTorus(p, vec2(0.4, 0.12)), 1.0); }',
                              surface=lambda p, n, m: {'albedo': S.mix(S.vec3(1, 0, 0), S.vec3(0, 0, 1), (p[:, 0:1] + 0.5)),
                                                       'roughness': 0.3},
                              bounds={'min': [-0.55, -0.15, -0.55], 'max': [0.55, 0.15, 0.55]}, cells=64,
                              carrier='vertex', name='opt_mixed', cache_dir=CACHE, location=(0, 8, 0))
alb = np.array([d.color[:3] for d in mixed.object.data.attributes['sdf_albedo'].data])
xs = np.array([v.co.x for v in mixed.object.data.vertices])
C.check('GLSL map + Python surface', float(np.corrcoef(xs, alb[:, 2])[0, 1]) > 0.99,
        f'blue follows x (corr {np.corrcoef(xs, alb[:, 2])[0, 1]:.3f})')
mixed.object.hide_render = True
# the GLSL originals declared their uniforms themselves: the declaration types them, the spec gives the value
DECL = r"""
    uniform vec3  uPaint;
    uniform float uRough;
    uniform sampler2D uDecal;
"""
dec = sdf.create_sdf_object(extra=DECL, map='vec2 map(vec3 p) { return vec2(sdSphere(p, 0.3), 1.0); }',
                            surface='SdfSurface surface(vec3 p, vec3 n, float mat) { return sdfSurface(uPaint + texture(uDecal, vec2(0.5)).rgb, uRough); }',
                            uniforms={'uPaint': ('color', 0x3366cc)}, bounds={'min': [-0.35] * 3, 'max': [0.35] * 3},
                            cells=48, carrier='vertex', name='opt_declared', cache_dir=CACHE, location=(0, 9, 0))
dc = dec.program.declared_uniforms()
bsdf = next(n for n in dec.material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
alb = np.array(bsdf.inputs['Base Color'].default_value[:3])        # constant: stored on the BSDF, not per point
C.check('declared uniforms: typed, defaulted, the sampler bound', dc == {'uPaint': 'vec3', 'uRough': 'float', 'uDecal': 'sampler2D'}
        and abs(alb[2] - dec.program.values['uPaint'][2]) < 1e-4 and 'roughness' in dec.stats['constants'],
        f'{dc}, albedo {alb.round(3).tolist()} (uRough defaults to 0, uDecal to black)')
dec.object.hide_render = True
# bake(controls=...): a uniform keyed per frame (the radius grows), one PLY per frame
grow = sdf.create_sdf_object(map='vec2 map(vec3 p) { return vec2(sdSphere(p, uR), 1.0); }', uniforms={'uR': 0.1},
                             bounds={'min': [-0.45] * 3, 'max': [0.45] * 3}, cells=40, name='opt_grow',
                             cache_dir=CACHE, location=(0, 10, 0))
grow.bake(1, 3, controls=lambda frame, t: {'uR': 0.1 * frame}, log=None)
import struct  # noqa: E402


def ply_extent(path):
    with open(path, 'rb') as fh:
        head = b''
        while not head.endswith(b'end_header\n'):
            head += fh.read(1)
        nv = int(head.split(b'element vertex ')[1].split(b'\n')[0])
        props = head.split(b'element vertex')[1].split(b'element face')[0].count(b'property float')
        v = np.frombuffer(fh.read(nv * props * 4), '<f4').reshape(nv, props)
    return float(np.abs(v[:, :3]).max())


ext = [ply_extent(os.path.join(CACHE, f'opt_grow_{f:04d}.ply')) for f in (1, 2, 3)]
C.check('bake(controls=) keys a uniform per frame', all(abs(e - 0.1 * (i + 1)) < 0.02 for i, e in enumerate(ext)),
        f'radii {[round(e, 3) for e in ext]}')
grow.object.hide_render = True
sdf.register_example('opt_custom', kind='solid', bounds={'min': [-0.3, 0, -0.3], 'max': [0.3, 0.6, 0.3]}, quality='fast',
                     map='vec2 map(vec3 p) { return vec2(sdCone(p - vec3(0.0, 0.6, 0.0), vec2(0.447, 0.894), 0.6), 1.0); }',
                     surface='SdfSurface surface(vec3 p, vec3 n, float mat) { return sdfSurface(vec3(0.9), 0.5); }')
cu = sdf.EXAMPLES['opt_custom'].make(name='opt_custom', cache_dir=CACHE, location=(0, 7, 0), carrier='vertex')
C.check('register_example + make', cu.stats.get('quads', 0) > 100 and 'opt_custom' in sdf.EXAMPLES.solids(),
        f'{cu.stats.get("quads")} quads')
for ob in (tight.object, cu.object) + tuple(bpy.data.objects[f'opt_q_{q}'] for q in qs):
    ob.hide_render = True

# ---- 6b. the mesher's own options on a box with exact corners: voxel, refine, qef_lambda, brick, lipschitz_k, texels --
BOX = 'vec2 map(vec3 p) { return vec2(sdBox(p - vec3(0.013, 0.31, 0.007), vec3(0.25, 0.3, 0.2)), 1.0); }'
CORNERS = np.array([(0.013 + sx * 0.25, 0.31 + sy * 0.3, 0.007 + sz * 0.2) for sx in (-1, 1) for sy in (-1, 1)
                    for sz in (-1, 1)])


def corner_err(o):
    v = o.contour.verts.astype(np.float64)
    return float(np.min(np.linalg.norm(v[:, None, :] - CORNERS[None], axis=2), axis=0).max()) / o.voxel


box_kw = dict(map=BOX, bounds={'min': [-0.3, 0.0, -0.25], 'max': [0.3, 0.65, 0.25]}, cache_dir=CACHE,
              location=(0, 11, 0))
b_ref = sdf.create_sdf_object(name='opt_box', voxel=0.02, carrier='vertex', **box_kw)
b_lin = sdf.create_sdf_object(name='opt_box_linear', voxel=0.02, refine=0, carrier='vertex', **box_kw)
b_soft = sdf.create_sdf_object(name='opt_box_qef', voxel=0.02, qef_lambda=2.0, carrier='vertex', **box_kw)
b_brick = sdf.create_sdf_object(name='opt_box_brick', voxel=0.02, brick=8, lipschitz_k=3.0, carrier='vertex', **box_kw)
b_tex = sdf.create_sdf_object(name='opt_box_tex', voxel=0.02, texels=6, **box_kw)
C.check('voxel= sets the mesh resolution', abs(b_ref.voxel - 0.02) < 1e-9 and b_ref.stats['voxel'] == 0.02,
        f'{b_ref.voxel * 1000:.1f} mm, {b_ref.stats["quads"]} quads')
e_ref, e_lin, e_soft = corner_err(b_ref), corner_err(b_lin), corner_err(b_soft)
C.check('refine: regula falsi crossings keep the corners', e_ref < 0.1 and e_lin > 2 * e_ref,
        f'corner error {e_ref:.3f} voxel refined, {e_lin:.3f} voxel with refine=0')
C.check('qef_lambda: a stiffer pull to the mass point rounds the corners', e_soft > 2 * e_ref,
        f'corner error {e_soft:.3f} voxel at qef_lambda=2 (0.01: {e_ref:.3f})')
C.check('brick / lipschitz_k: the same surface from other brick sizes', b_brick.stats['quads'] == b_ref.stats['quads']
        and b_brick.stats['brick'] == 8, f'{b_brick.stats["quads"]} quads in {b_brick.stats["bricks"]} bricks of 8^3 '
        f'(4^3: {b_ref.stats["bricks"]} bricks)')
C.check('texels= sets the atlas texels per quad side', b_tex.stats.get('texels') == 6, f'{b_tex.stats.get("atlas")}, '
        f'{b_tex.stats.get("texels")} texels a side')
for o in (b_ref, b_lin, b_soft, b_brick, b_tex):
    o.object.hide_render = True

# ---- 7. the helper binds the world's sky to every SDF's sampleEnvMap ---------------------------------------------------
res = sdf.register_sdf_helper(sc)
C.check('register_sdf_helper binds the HDRI', res['env'] is not None and two.program.values['uEnvMapStrength'] > 0,
        str(res))
CHROME = r"""
vec3 shade(vec3 p, vec3 n, float mat) { return sampleEnvMap(sdfReflectWorld(p, n)); }"""
two.program.shade = CHROME
# the five stand from x = -3.2 to 3.4 m: this frame holds +-3.5 m at the line
cam = C.camera((0.0, -7.4, 1.6), (0.0, 0.0, 0.45), lens=38)
ref = two.raymarch_reference(cam, 640, 270, samples=1)
hit = ref[..., 3] > 0.5
C.check('sampleEnvMap reads the sky', hit.any() and float(ref[hit][:, 2].mean()) > 0.05,
        f'mean reflected colour {ref[hit][:, :3].mean(axis=0).round(3).tolist()}')
C.save_linear_png(os.path.join(C.OUT, 'opt_env_ref.png'), ref)
shot = os.path.join(C.OUT, 'opt_scene.png')
if C.args().get('render', '1') == '1':
    C.check('scene renders', C.render(shot), shot)
msg = sdf.help()
C.check('help() lists the custom example', 'opt_custom' in msg, f'{len(msg)} characters')
C.summary()
