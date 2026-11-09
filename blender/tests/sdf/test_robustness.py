"""The engine under the uses a film puts it to: several objects of one example, frames with nothing to show, the
TSL edition's shade(p, n, mat, ctx), and screens and volumes side by side.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_robustness.py          (-- render=0 runs without the GPU slot)

PASS lines:
  * two explosions of one example with different speeds keep their own atlases: each object's cache files are named
    for it (explosion, explosion.001), each image holds its own atlas, after a save and a reopen too, and the
    reopened file renders as the saved scene did (out/robust_two_explosions.png: left the slow one, right the fast)
  * build(t) inside the explosion's collapse (its radius goes through zero for part of its 25 s cycle) empties the
    object, and a later build brings it back
  * a vertex bake through the collapse: frames with no surface are empty meshes, the others play
  * an atlas_sequence bake that starts inside the collapse: every frame of every image sequence exists, and the
    frames with a surface play
  * two volumes, and two screens of one recipe, keep their own files
  * make_sdf_texture's encoding: 'linear' (the default, the WebGL engine's sRGB render target) stores what decodes
    to the shader's values, 'srgb' the values themselves; update() packs its frame, so a saved file keeps it
    (out/robust_screen_encoding.png: the image a screen shows, 'srgb' left, 'linear' right)
  * a Python shade(p, n, mat, ctx), the engine's TSL form: ctx.softShadow darkens the floor under a sphere, and
    ctx.ro is the bake's viewer, straight along the normal
"""

import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402

A = C.args()
RENDER = A.get('render', '1') != '0'
CACHE = os.path.join(C.OUT, 'cache_robust')
shutil.rmtree(CACHE, ignore_errors=True)
os.makedirs(CACHE, exist_ok=True)
BLEND = os.path.join(CACHE, 'robust_two_explosions.blend')


def ply_vertices(path):
    with open(path, 'rb') as fh:
        for line in fh:
            if line.startswith(b'element vertex'):
                return int(line.split()[2])
    return -1


def evaluated_count(ob, frame):
    bpy.context.scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    return len(ob.evaluated_get(dg).data.vertices)


def image_size(path):
    import OpenImageIO as oiio
    s = oiio.ImageBuf(path).spec()
    return (s.width, s.height)


# ------------------------------------------------------------------- 1. two objects of one example, saved ----
sc = C.stage(640, 360, 16, world_color=(0.25, 0.25, 0.27), world_strength=1.0, floor_color=(0.2, 0.2, 0.2))
sc.frame_start, sc.frame_end = 1, 1
slow = sdf.EXAMPLES['explosion'].make(speed=0.3, cache_dir=CACHE, cells=96, time=4.0, location=(-1.3, 0.0, 0.0),
                                      scale=0.55, log=None)
fast = sdf.EXAMPLES['explosion'].make(cache_dir=CACHE, cells=96, time=4.0, location=(1.3, 0.0, 0.0), scale=0.55,
                                      log=None)
for o in (slow, fast):
    o.place_on_ground(0.0)
own = all(image_size(bpy.path.abspath(o.images['base'].filepath)) == tuple(o.stats['atlas']) for o in (slow, fast))
C.check('two objects of one example: their own cache files',
        slow.stem != fast.stem and slow.images['base'].filepath != fast.images['base'].filepath and own,
        f'stems {slow.stem!r} / {fast.stem!r}; atlases {slow.stats["atlas"]} / {fast.stats["atlas"]}, each file its '
        f'own atlas: {own}')
names = (slow.object.name, fast.object.name)
atlases = {slow.object.name: tuple(slow.stats['atlas']), fast.object.name: tuple(fast.stats['atlas'])}
cam = C.camera((0.0, -6.2, 1.5), (0.0, 0.0, 0.6), lens=40)
shot = os.path.join(C.OUT, 'robust_two_explosions.png')
if RENDER:
    C.check('two explosions render', C.render(shot), shot)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.wm.open_mainfile(filepath=BLEND)
ok = True
detail = []
for nm in names:
    ob = bpy.data.objects[nm]
    img = next(n.image for n in ob.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and 'base' in n.image.name)
    img.reload()
    got = tuple(img.size)
    ok &= got == atlases[nm]
    detail.append(f'{nm}: image {got}, atlas {atlases[nm]}')
C.check('reopened: each object reads its own atlas', ok, '; '.join(detail))
if RENDER:
    shot2 = os.path.join(C.OUT, 'robust_two_explosions_reopened.png')
    C.render(shot2)
    import OpenImageIO as oiio
    a = np.asarray(oiio.ImageBuf(shot).get_pixels(oiio.FLOAT))
    b = np.asarray(oiio.ImageBuf(shot2).get_pixels(oiio.FLOAT))
    C.check('the reopened file renders the saved scene', float(np.abs(a - b).mean()) < 0.01,
            f'mean difference {np.abs(a - b).mean():.4f}')

# ------------------------------------------------------------------- 2. nothing to show: the explosion's collapse ----
C.stage(320, 180, 8, floor=False, sun=False)
sc = bpy.context.scene
ex = sdf.EXAMPLES['explosion'].make(name='robust_collapse', cache_dir=CACHE, cells=64, carrier='vertex', time=4.0,
                                    log=None)
n4 = len(ex.object.data.vertices)
ex.build(19.0, log=None)
n19 = len(ex.object.data.vertices)
ex.build(4.0, log=None)
C.check('build(t) in the collapse empties the object, a later build restores it',
        n4 > 1000 and n19 == 0 and len(ex.object.data.vertices) == n4,
        f'{n4} -> {n19} -> {len(ex.object.data.vertices)} vertices')

sc.render.fps, sc.render.fps_base = 2, 1.0
vb = sdf.EXAMPLES['explosion'].make(name='robust_vertex_bake', cache_dir=CACHE, cells=48, log=None)
vb.bake(1, 6, time_offset=15.0, log=None)          # t = 15.0 .. 17.5 s: the radius shrinks to nothing
counts = {f: ply_vertices(os.path.join(CACHE, f'{vb.stem}_{f:04d}.ply')) for f in range(1, 7)}
shown = {f: evaluated_count(vb.object, f) for f in range(1, 7)}
C.check('vertex bake through the collapse: empty frames are empty meshes, the rest play',
        any(c == 0 for c in counts.values()) and any(c > 0 for c in counts.values()) and
        all((counts[f] > 0) == (shown[f] > 0) for f in counts),
        f'PLY vertices {counts}, shown {shown}')

sc.render.fps = 1
ab = sdf.EXAMPLES['explosion'].make(name='robust_atlas_bake', cache_dir=CACHE, cells=48, carrier='atlas_sequence',
                                    log=None)
ab.bake(1, 4, time_offset=20.5, log=None)          # t = 20.5 .. 23.5 s: from inside the collapse back to a fireball
counts = {f: ply_vertices(os.path.join(CACHE, f'{ab.stem}_{f:04d}.ply')) for f in range(1, 5)}
keys = sorted(ab.images)
complete = all(os.path.exists(os.path.join(CACHE, f'{ab.stem}_{f:04d}_{k}.exr')) for f in range(0, 5) for k in keys)
shown = {f: evaluated_count(ab.object, f) for f in range(1, 5)}
C.check('atlas_sequence from inside the collapse: every frame of every sequence, the surface frames play',
        counts[1] == 0 and counts[4] > 0 and complete and bool(keys) and
        all((counts[f] > 0) == (shown[f] > 0) for f in counts) and
        all(img.source == 'SEQUENCE' for img in ab.images.values()),
        f'PLY vertices {counts}, shown {shown}, sequences {keys}, all frames 0-4 on disk: {complete}')
sc.render.fps = 24

# ------------------------------------------------------------------- 3. volumes and screens side by side ----
V = ('SdfSample sample(vec3 p) { float d = clamp(0.5 - length(p), 0.0, 1.0); '
     'return sdfSample(vec3(uK), d * 0.2, 0.02); }')
v1 = sdf.create_sdf_volume(sample=V, uniforms={'uK': 1.0}, bounds={'min': [-0.6] * 3, 'max': [0.6] * 3}, cells=24,
                           name='robust_volume', cache_dir=CACHE, log=None)
v2 = sdf.create_sdf_volume(sample=V, uniforms={'uK': 5.0}, bounds={'min': [-0.6] * 3, 'max': [0.6] * 3}, cells=24,
                           name='robust_volume', cache_dir=CACHE, log=None)
t1 = sdf.make_sdf_texture(recipe='gyroid', width=64, height=32, name='robust_screen', cache_dir=CACHE)
t2 = sdf.make_sdf_texture(recipe='gyroid', width=64, height=32, name='robust_screen', cache_dir=CACHE,
                          uniforms={'paletteMode': 1.0})
t1.bake(1, 2, log=None)
t2.bake(1, 2, log=None)
C.check('two volumes and two screens of one name keep their own files',
        v1.object.data.filepath != v2.object.data.filepath and t1.image.filepath != t2.image.filepath and
        os.path.exists(v1.object.data.filepath) and os.path.exists(v2.object.data.filepath),
        f'{os.path.basename(v1.object.data.filepath)}, {os.path.basename(v2.object.data.filepath)}; '
        f'{os.path.basename(t1.image.filepath)}, {os.path.basename(t2.image.filepath)}')

TW, TH = 320, 160
lin = sdf.make_sdf_texture(recipe='mandelbulb', width=TW, height=TH, name='robust_linear', cache_dir=CACHE,
                           encoding='linear')
srg = sdf.make_sdf_texture(recipe='mandelbulb', width=TW, height=TH, name='robust_srgb', cache_dir=CACHE,
                           encoding='srgb')
lin.update(1.0)
srg.update(1.0)
raw = np.clip(srg.render(1.0), 0.0, 1.0)[..., :3]
a_l = np.array(lin.image.pixels[:], np.float32).reshape(TH, TW, 4)[..., :3]
a_s = np.array(srg.image.pixels[:], np.float32).reshape(TH, TW, 4)[..., :3]
import OpenImageIO as oiio  # noqa: E402
enc = []
for tag, a in (('srgb', a_s), ('linear', a_l)):     # the image bytes a screen shows: left 'srgb', right 'linear'
    p = os.path.join(C.OUT, f'_robust_{tag}.png')
    data = np.ascontiguousarray((np.clip(a[::-1], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))
    out = oiio.ImageOutput.create(p)
    out.open(p, oiio.ImageSpec(TW, TH, 3, 'uint8'))
    out.write_image(data)
    out.close()
    enc.append(p)
C.sheet(enc, os.path.join(C.OUT, 'robust_screen_encoding.png'), cols=2)
for p in enc:
    os.remove(p)
dec = np.where(a_l <= 0.04045, a_l / 12.92, ((a_l + 0.055) / 1.055) ** 2.4)
C.check("screen encoding: 'srgb' holds the shader's values, 'linear' what decodes to them",
        float(np.abs(a_s - raw).max()) < 0.003 and float(np.abs(dec - raw).max()) < 0.01,
        f'srgb max error {np.abs(a_s - raw).max():.4f}, linear decoded max error {np.abs(dec - raw).max():.4f}')
C.check('update() packs its frame (a saved file keeps it)',
        lin.image.packed_file is not None and srg.image.packed_file is not None, 'packed')

# ------------------------------------------------------------------- 4. the TSL shade form, shade(p, n, mat, ctx) ----
S = sdf.SDF_NP


def two_shapes(p):
    d_s = S.sd_sphere(p - S.vec3(0.0, 0.5, 0.0), 0.3)
    d_p = p[:, 1] + 0.0
    return {'dist': np.minimum(d_s, d_p), 'mat': np.where(d_s < d_p, 2.0, 1.0)}


def shade_ctx(p, n, mat, ctx):
    sh = ctx.softShadow(p + n * 0.002, S.vec3(0.0, 1.0, 0.0), 0.01, 3.0, 12.0)
    head_on = S.dot(n, S.normalize(ctx.ro - p))
    return np.stack([sh, sh, sh * head_on], -1)


o = sdf.create_sdf_object(map=two_shapes, shade=shade_ctx, bounds={'min': [-1.0, -0.05, -1.0], 'max': [1.0, 0.9, 1.0]},
                          cells=48, carrier='vertex', name='robust_ctx', cache_dir=CACHE, cut_by_bounds=True, log=None)
pts = np.array([[0.0, 0.0, 0.0], [0.9, 0.0, 0.9]], np.float32)
alb = o.program.surface_eval(pts, project=2)['albedo']
C.check('Python shade(p, n, mat, ctx): softShadow under the sphere, ro straight along the normal',
        float(alb[0].max()) < 0.05 and float(alb[1].min()) > 0.95,
        f'under the sphere {alb[0].round(3).tolist()}, in the open {alb[1].round(3).tolist()}')

for p in (BLEND, BLEND + '1'):
    if os.path.exists(p):
        os.remove(p)
C.summary()
