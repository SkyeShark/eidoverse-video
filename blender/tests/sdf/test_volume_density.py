"""create_sdf_volume's grids measured in a render: EEVEE against the closed-form answer.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_volume_density.py

Three 0.9 m cubes of constant medium in a row in front of a white emissive backdrop. The camera ray through a
cube's centre crosses s = 0.9 m / cos(its angle off the axis): 0.928 m for A (2.25 m off-axis), 0.903 m for B and C.
  A  medium(): a pure absorber, density 2 /m           -> transmittance exp(-2 s)
  B  sample(): the engine contract, alpha 0.01 per 0.01 m -> density -ln(0.99) / 0.01, transmittance exp(-1.005 s)
  C  medium(): a pure emitter-absorber, density 1 /m, emission (1, 0.5, 0.25) /m
     -> E (1 - exp(-s)) + backdrop exp(-s)
  D  medium(): a scattering slab (density 4 /m, albedo 0.9) under a sun: measured and printed
The render goes to linear EXR ('Standard' view) and the centre pixels are compared with those numbers (within 3 %).
out/vol_density_eevee.png shows the probe. Before it, without rendering (`-- render=0` runs only
these): sample_as='albedo' grids, and Python sample() / medium() stages against their GLSL twins.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402

CACHE = os.path.join(C.OUT, 'cache_density')
BOUNDS = {'min': [-0.5, -0.5, -0.5], 'max': [0.5, 0.5, 0.5]}
SLAB = 'float slab(vec3 p) { return sdBox(p, vec3(0.45)); }'

ABSORB = SLAB + r"""
SdfMedium medium(vec3 p) {
    float inside = slab(p) < 0.0 ? 1.0 : 0.0;
    return sdfMedium(2.0 * inside, vec3(0.0), vec3(0.0));
}"""
ENGINE = SLAB + r"""
SdfSample sample(vec3 p) {
    float inside = slab(p) < 0.0 ? 1.0 : 0.0;
    return sdfSample(vec3(0.0), 0.01 * inside, 0.01);
}"""
EMIT = SLAB + r"""
SdfMedium medium(vec3 p) {
    float inside = slab(p) < 0.0 ? 1.0 : 0.0;
    return sdfMedium(1.0 * inside, vec3(0.0), vec3(1.0, 0.5, 0.25) * inside);
}"""
# D, measured only: a scattering slab (density 4 /m, albedo 0.9) under a sun from the camera's side. There is no
# closed form for its multiple scattering (EEVEE's volumes scatter the sun once), so its colour is printed.
SCATTER = SLAB + r"""
SdfMedium medium(vec3 p) {
    float inside = slab(p) < 0.0 ? 1.0 : 0.0;
    return sdfMedium(4.0 * inside, vec3(0.9), vec3(0.0));
}"""
L = 0.9
BACK = 1.0


def path(i):
    """The medium the camera ray through slab i's centre crosses: the slabs stand at x = (i - 1.5) * 1.5 and the
    camera 9 m back on the axis, so an outer slab is seen 14 degrees off-axis and the ray runs 0.9 / cos(angle)
    through it (0.928 m for A, 0.903 m for B and C)."""
    x = (i - 1.5) * 1.5
    return L * math.sqrt(x * x + 81.0) / 9.0


EXPECT = {
    'A': np.full(3, BACK * math.exp(-2.0 * path(0))),
    'B': np.full(3, BACK * math.exp(-(-math.log(0.99) / 0.01) * path(1))),
    'C': np.array([1.0, 0.5, 0.25]) * (1.0 - math.exp(-path(2))) + BACK * math.exp(-path(2)),
}
SLABS = (('A', {'medium': ABSORB}), ('B', {'sample': ENGINE}), ('C', {'medium': EMIT}), ('D', {'medium': SCATTER}))

sc = C.stage(480, 160, 32, world_color=(0.0, 0.0, 0.0), world_strength=0.0, floor=False, sun=False)
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'OPEN_EXR'
sc.render.image_settings.color_depth = '32'
sdf.volume_render_settings(sc, tile_size='2', samples=128, end=20.0)
sc.eevee.volumetric_start = 1.0
sun_d = bpy.data.lights.new('sun', 'SUN')
sun_d.energy = 3.0
sun_o = bpy.data.objects.new('sun', sun_d)
sc.collection.objects.link(sun_o)
sun_o.rotation_euler = (math.radians(55.0), 0.0, 0.0)          # from the camera's side, 35 degrees above

for i, (key, kw) in enumerate(SLABS):
    sdf.create_sdf_volume(bounds=BOUNDS, cells=60, name=f'density_{key}', cache_dir=CACHE,
                          location=((i - 1.5) * 1.5, 0.0, 1.0), log=None, **kw)

# sample_as='albedo': the engine colour read as the scattering colour, no emission (grids only, not rendered)
GREY = SLAB + r"""
SdfSample sample(vec3 p) {
    float inside = slab(p) < 0.0 ? 1.0 : 0.0;
    return sdfSample(vec3(0.7, 0.6, 0.5), 0.02 * inside, 0.01);
}"""
lit = sdf.create_sdf_volume(sample=GREY, sample_as='albedo', bounds=BOUNDS, cells=24, name='density_albedo',
                            cache_dir=CACHE, build=False, log=None)
g = lit.sample_grids(0.0)
inside = g['density'] > 0.5
C.check("sample_as='albedo': colour -> scattering albedo, no emission",
        'albedo' in g and float(g['emission'].max()) == 0.0 and
        np.allclose(g['albedo'][inside], [0.7, 0.6, 0.5], atol=1e-3) and
        abs(float(g['density'][inside].mean()) + math.log(0.98) / 0.01) < 1e-3,
        f'albedo {g["albedo"][inside].mean(axis=0).round(3).tolist()}, density {g["density"][inside].mean():.3f} /m')
bpy.data.objects.remove(lit.object)

# a Python sample() / medium() (the engine's TSL stages were host-language functions): the same grids as the GLSL
from eidoblend.sdf import SDF_NP as S  # noqa: E402


def py_engine(p):
    inside = (S.sd_box(p, S.vec3(0.45, 0.45, 0.45)) < 0.0).astype(np.float32)
    return {'color': (0.0, 0.0, 0.0), 'alpha': 0.01 * inside, 'step': 0.01}


def py_medium(p):
    return {'density': np.full(len(p), 1.0 + float(S.time), np.float32), 'albedo': (0.2, 0.4, 0.6)}


pyv = sdf.create_sdf_volume(sample=py_engine, bounds=BOUNDS, cells=24, name='density_py', cache_dir=CACHE,
                            build=False, log=None)
glv = sdf.create_sdf_volume(sample=ENGINE, bounds=BOUNDS, cells=24, name='density_glsl', cache_dir=CACHE,
                            build=False, log=None)
pym = sdf.create_sdf_volume(medium=py_medium, bounds=BOUNDS, cells=12, name='density_pymed', cache_dir=CACHE,
                            build=False, log=None)
gp, gg, gm = pyv.sample_grids(0.0), glv.sample_grids(0.0), pym.sample_grids(2.0)
C.check('a Python sample() gives the GLSL grids', float(np.abs(gp['density'] - gg['density']).max()) < 1e-4,
        f'max density difference {np.abs(gp["density"] - gg["density"]).max():.2e} /m')
C.check('a Python medium() reads S.time', np.allclose(gm['density'], 3.0) and np.allclose(gm['albedo'], [0.2, 0.4, 0.6]),
        f'density {gm["density"].mean():.3f} /m at t = 2 s (1 + t)')
for v in (pyv, glv, pym):
    bpy.data.objects.remove(v.object)
# the backdrop: an emitter of radiance BACK, 3 m behind the slabs
me = bpy.data.meshes.new('backdrop')
me.from_pydata([(-4, 3, -2), (4, 3, -2), (4, 3, 4), (-4, 3, 4)], [], [(0, 1, 2, 3)])
bd = bpy.data.objects.new('backdrop', me)
sc.collection.objects.link(bd)
m = bpy.data.materials.new('backdrop')
m.use_nodes = True
nt = m.node_tree
for n in list(nt.nodes):
    if n.type != 'OUTPUT_MATERIAL':
        nt.nodes.remove(n)
em = nt.nodes.new('ShaderNodeEmission')
em.inputs['Strength'].default_value = BACK
nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
me.materials.append(m)
cam = C.camera((0.0, -9.0, 1.0), (0.0, 0.0, 1.0), lens=50)


def centres(path):
    import OpenImageIO as oiio
    a = np.asarray(oiio.ImageBuf(path).get_pixels(oiio.FLOAT))[..., :3]
    h, w = a.shape[:2]
    out = {}
    for i, (key, _kw) in enumerate(SLABS):
        # each slab's centre, projected
        from bpy_extras.object_utils import world_to_camera_view
        from mathutils import Vector
        v = world_to_camera_view(sc, cam, Vector(((i - 1.5) * 1.5, 0.0, 1.0)))
        x, y = int(v.x * w), int((1.0 - v.y) * h)
        out[key] = a[y - 3:y + 4, x - 3:x + 4].reshape(-1, 3).mean(axis=0)
    return out


scattered = {}
for engine in (('BLENDER_EEVEE',) if C.args().get('render', '1') == '1' else ()):
    sc.render.engine = engine
    tag = 'eevee'
    exr = os.path.join(C.OUT, f'vol_density_{tag}.exr')
    sc.render.filepath = exr
    bpy.ops.render.render(write_still=True)
    if not C.check(f'{tag}: render written', os.path.exists(exr), exr):
        continue
    got = centres(exr)
    for key in 'ABC':
        rel = float(np.max(np.abs(got[key] - EXPECT[key]) / EXPECT[key]))
        C.check(f'{tag} slab {key}', rel < 0.03, f'got {got[key].round(4).tolist()}, expected {EXPECT[key].round(4).tolist()} '
                f'(worst channel {rel * 100:.1f}% off)')
    scattered[tag] = got['D']
    print(f'[density] {tag} slab D (scattering, sunlit): {got["D"].round(4).tolist()}', flush=True)
    import OpenImageIO as oiio
    buf = oiio.ImageBuf(exr)
    a = np.asarray(buf.get_pixels(oiio.FLOAT))[..., :3]
    C.save_linear_png(os.path.join(C.OUT, f'vol_density_{tag}.png'), a[::-1], agx=False)
    os.remove(exr)
C.summary()
