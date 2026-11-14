"""make_sdf_texture: the four SDF_TEX_RECIPES rendered into images, a bank of four screens showing them in an EEVEE
scene (the engine's documented use: the texture as map + emissiveMap), and a baked sequence that plays.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_sdf_texture.py
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

out/tex_<recipe>.png (each texture as the engine's render target held it), out/tex_screens.png (the screens), and
PASS lines: every recipe renders a subject (hit pixels) over its sky, the custom_de / custom_shade overrides take,
set_uniform changes the picture, the baked frames differ and the material plays them.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402

CACHE = os.path.join(C.OUT, 'cache')
C.stage(960, 540, 16, world_color=(0.05, 0.05, 0.06), world_strength=1.0, sun=True, sun_energy=1.0,
        floor_color=(0.12, 0.12, 0.12))
texes = {}
for i, recipe in enumerate(sdf.SDF_TEX_RECIPES):
    tex = sdf.make_sdf_texture(recipe=recipe, width=512, height=256, name=f'tex_{recipe}', cache_dir=CACHE, samples=2)
    tex.update(3.0)
    path = os.path.join(C.OUT, f'tex_{recipe}.png')
    tex.image.filepath_raw = path
    tex.image.file_format = 'PNG'
    tex.image.save()
    px = np.empty(512 * 256 * 4, np.float32)
    tex.image.pixels.foreach_get(px)
    px = px.reshape(256, 512, 4)
    C.check(f'{recipe}: renders', px[..., :3].std() > 0.03 and np.isfinite(px).all(),
            f'mean {px[..., :3].mean():.3f}, std {px[..., :3].std():.3f}')
    texes[recipe] = tex

# a custom DE + custom shade, and a live uniform
cust = sdf.make_sdf_texture({'customDe': 'float DE(vec3 p) { return length(p) - 0.8; }',
                             'customShade': 'return vec3(0.9, 0.3, 0.1) * max(dot(n, normalize(vec3(0.6, 0.8, -0.3))), 0.1);',
                             'width': 128, 'height': 64}, name='tex_custom', cache_dir=CACHE)
img = cust.render(0.0)
centre = img[24:40, 56:72, :3].mean(axis=(0, 1))
C.check('custom_de / custom_shade', centre[0] > 2 * centre[2], f'centre colour {centre.round(3).tolist()}')
mb = texes['mandelbulb']
a = mb.render(3.0)
mb.set_uniform('power', 4.0)
b = mb.render(3.0)
mb.set_uniform('uPower', 8.0)
C.check('set_uniform changes the picture', float(np.abs(a - b).mean()) > 0.01, f'mean change {np.abs(a - b).mean():.3f}')

# the screens: four planes, each the engine's MeshStandardMaterial({map, emissiveMap, emissive: white, 0.9})
for i, (recipe, tex) in enumerate(texes.items()):
    me = bpy.data.meshes.new(f'screen_{recipe}')
    w, h = 1.6, 0.8
    me.from_pydata([(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for k, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[k].uv = c
    ob = bpy.data.objects.new(f'screen_{recipe}', me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = ((i % 2) * 1.75 - 0.875, 0.0, 0.25 + (i // 2) * 0.9)
    me.materials.append(tex.material(emission_strength=0.9))
C.camera((0.0, -3.6, 1.15), (0.0, 0.0, 1.05), lens=45)
shot = os.path.join(C.OUT, 'tex_screens.png')
C.check('screens render', C.render(shot), shot)

# a baked sequence the material plays
g = texes['gyroid']
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 4
g.bake(1, 4, fps=2.0)
frames = [os.path.join(CACHE, f'tex_gyroid_{f:04d}.png') for f in (0, 1, 2, 3, 4)]
C.check('bake wrote the frames and the hold copy', all(os.path.exists(f) for f in frames), f'{len(frames)} files')
import OpenImageIO as oiio  # noqa: E402
f1 = np.asarray(oiio.ImageBuf(frames[1]).get_pixels(oiio.FLOAT))
f4 = np.asarray(oiio.ImageBuf(frames[4]).get_pixels(oiio.FLOAT))
C.check('frames differ', float(np.abs(f1 - f4).mean()) > 0.01, f'mean change {np.abs(f1 - f4).mean():.3f}')
mat = bpy.data.objects['screen_gyroid'].data.materials[0]
node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
C.check('the screen plays the sequence', node.image.source == 'SEQUENCE' and node.image_user.frame_duration == 4,
        f'{node.image.name}: {node.image.source}, frames {node.image_user.frame_start}+{node.image_user.frame_duration}')
sc.frame_set(4)
shot4 = os.path.join(C.OUT, 'tex_screens_f4.png')
C.check('screens render at frame 4', C.render(shot4), shot4)
C.summary()
