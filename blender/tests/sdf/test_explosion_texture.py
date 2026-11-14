"""make_explosion_texture: the engine's mushroom-cloud detonation shader (makeExplosionTexture, from its GLSL edition;
the TSL migration dropped it) rendered into images at the four beats of its 15-second loop, shown on a screen in an
EEVEE scene, and baked into a sequence the screen plays.
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_explosion_texture.py [-- render=0]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
out/tex_explosion_beats.png: t = 0.5 s (the flash), 3.5 s (the cap rising), 9 s (the cloud billowing) and 14 s (the
fade), each as a screen shows it (the default encoding: the engine's look, its sRGB render target reading the
shader's gamma-encoded values as linear light). out/tex_explosion_screen.png: a monitor in a dark room
playing the baked sequence, at its first and last frame. PASS lines: every beat shows fire over the night sky, the
cap climbs from the flash to the rise, the fire cools by the fade, time_scale / time_offset reach the shader's clock,
the camelCase options are taken, set_camera_pos / set_camera_target move the view, update_every holds frames, the
bake writes its frames and the hold copy, and the screen plays them.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402

CACHE = os.path.join(C.OUT, 'cache_explosion')
RENDER = C.args().get('render', '1') == '1'
W, H = 480, 270


def save_bytes(path, img, tex):
    """The texture's 8-bit values, as a screen shows them (tex.encoding: by default the engine's look, its sRGB
    render target reading the shader's own gamma-encoded values as linear light)."""
    import OpenImageIO as oiio
    a = np.ascontiguousarray((tex._texels(img)[::-1, :, :3] * 255.0 + 0.5).astype(np.uint8))
    out = oiio.ImageOutput.create(path)
    out.open(path, oiio.ImageSpec(a.shape[1], a.shape[0], 3, 'uint8'))
    out.write_image(a)
    out.close()
    return path


def sky(w, h, cam_pos=(18.0, 7.0, 22.0), cam_target=(0.0, 5.0, 0.0)):
    """The shader's own sky with nothing in front of it, per pixel (numpy, row 0 at the bottom): skyColor, the
    horizon haze, the tone curve, the gamma and the vignette, as main() computes them for a ray that hits nothing."""
    x, y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    p = np.stack([(x - 0.5 * w) / h, (y - 0.5 * h) / h], -1)
    ro, ta = np.asarray(cam_pos, float), np.asarray(cam_target, float)
    fwd = (ta - ro) / np.linalg.norm(ta - ro)
    rt = np.cross(fwd, [0.0, 1.0, 0.0])
    rt /= np.linalg.norm(rt)
    up = np.cross(rt, fwd)
    rd = fwd * 1.4 + rt * p[..., :1] + up * p[..., 1:]
    rd /= np.linalg.norm(rd, axis=-1, keepdims=True)
    horizon = 1.0 - np.maximum(rd[..., 1:2], 0.0)
    col = np.array([0.015, 0.020, 0.040]) + (np.array([0.08, 0.04, 0.05]) - [0.015, 0.020, 0.040]) * horizon ** 4
    col = col + np.exp(-np.maximum(rd[..., 1:2], -0.2) * 3.0) * 0.06 * np.array([0.8, 0.3, 0.1])
    col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14)
    col = np.clip(col, 0.0, 1.0) ** (1.0 / 2.2)
    vc = np.stack([x / w - 0.5, y / h - 0.5], -1)
    return col * (1.0 - (vc ** 2).sum(-1, keepdims=True) * 0.6)


SKY = sky(480, 270)


def cloud(img):
    """Pixels where the cloud (its surface or its glow) stands in front of the sky."""
    return np.abs(img[..., :3] - SKY).max(axis=-1) > 0.04


def hot(img):
    """Pixels the upper fire ramp lit: orange to white-yellow."""
    return (img[..., 0] > 0.75) & (img[..., 1] > 0.45)


def top_row(mask):
    rows = np.nonzero(mask.any(axis=1))[0]
    return int(rows.max()) if len(rows) else -1       # row 0 at the bottom: larger is higher in the picture


C.stage(960, 540, 16, world_color=(0.02, 0.02, 0.025), world_strength=1.0, sun=False, floor_color=(0.08, 0.08, 0.08))
tex = sdf.make_explosion_texture(width=W, height=H, name='tex_explosion', cache_dir=CACHE, samples=2)
BEATS = (('flash', 0.5), ('rise', 3.5), ('billow', 9.0), ('fade', 14.0))
imgs = {}
paths = []
for name, t in BEATS:
    img = tex.render(t)
    imgs[name] = img
    cl, ht = cloud(img), hot(img)
    C.check(f'{name} (t = {t} s): the cloud over the sky', np.isfinite(img).all() and cl.mean() > 0.01,
            f'cloud {cl.mean() * 100:.1f}% of the frame, fire {ht.mean() * 100:.2f}%')
    paths.append(save_bytes(os.path.join(C.OUT, f'tex_explosion_{name}.png'), img, tex))
C.sheet(paths, os.path.join(C.OUT, 'tex_explosion_beats.png'), cols=2)
for p in paths:
    os.remove(p)
corner = float(np.abs(imgs['flash'][-20:, :20, :3] - SKY[-20:, :20]).max())
C.check('the sky model is the shader sky (top-left corner at the flash)', corner < 0.01, f'max difference {corner:.4f}')
r0, r1 = top_row(cloud(imgs['flash'])), top_row(cloud(imgs['rise']))
C.check('the cap climbs from the flash to the rise', r1 > r0 + 0.15 * H, f'highest cloud row {r0} -> {r1} of {H}')
heat = {k: float(hot(imgs[k]).mean()) for k in ('flash', 'billow', 'fade')}
C.check('the fire burns, then cools by the fade', heat['flash'] > 0.002 and heat['fade'] < 0.25 * heat['billow'],
        f'fire {heat["flash"] * 100:.2f}% of the frame at 0.5 s, {heat["billow"] * 100:.2f}% at 9 s, '
        f'{heat["fade"] * 100:.2f}% at 14 s')

# the engine's options, camelCase as it spelled them; the shader clock is t * timeScale + timeOffset
t2 = sdf.make_explosion_texture({'width': W, 'height': H, 'timeScale': 2.0, 'timeOffset': 1.0, 'updateEvery': 2,
                                 'cameraPos': [18, 7, 22], 'cameraTarget': [0, 5, 0]}, name='tex_explosion_b',
                                cache_dir=CACHE, samples=2)
C.check('camelCase options', t2.time_scale == 2.0 and t2.time_offset == 1.0 and t2.update_every == 2,
        f'time_scale {t2.time_scale}, time_offset {t2.time_offset}, update_every {t2.update_every}')
same = float(np.abs(t2.render(1.25) - tex.render(3.5)).max())
C.check('time_scale / time_offset reach the shader clock', same < 1e-4,
        f'render(1.25) at 2x + 1 s against render(3.5): max difference {same:.2e}')
base = tex.render(9.0)
tex.set_camera_pos(-6.0, 3.0, 26.0).set_camera_target(0.0, 7.0, 0.0)
moved = tex.render(9.0)
C.check('set_camera_pos / set_camera_target move the view', float(np.abs(moved - base).mean()) > 0.02,
        f'mean change {np.abs(moved - base).mean():.3f}')
tex.set_camera_pos((18.0, 7.0, 22.0)).set_camera_target((0.0, 5.0, 0.0))
px = np.empty(W * H * 4, np.float32)
snaps = []
for t in (3.0, 3.5, 4.0):                       # update_every = 2: calls 0 and 2 render, call 1 keeps the frame
    t2.update(t)
    t2.image.pixels.foreach_get(px)
    snaps.append(px.copy())
C.check('update_every holds frames', np.array_equal(snaps[0], snaps[1]) and not np.array_equal(snaps[1], snaps[2]),
        'the second update kept the first frame, the third rendered')
t2.dispose()

# bake(controls=): the guide's orbit, the camera uniform set before each rendered frame
import math  # noqa: E402
orbit = sdf.make_explosion_texture(width=96, height=54, name='tex_explosion_orbit', cache_dir=CACHE)
seen = []


def orbit_cam(frame, t):
    seen.append(frame)
    return {'uCamPos': (26 * math.sin(0.1 * t), 7.0, 26 * math.cos(0.1 * t))}


orbit.bake(1, 4, fps=0.5, controls=orbit_cam, log=None)          # two shader seconds a frame: 0, 2, 4, 6 s
want = (26 * math.sin(0.6), 7.0, 26 * math.cos(0.6))
C.check('bake(controls=) sets the camera before each frame', seen == [1, 2, 3, 4] and
        np.allclose(orbit.uniforms['uCamPos'], want, atol=1e-5),
        f'controls called for frames {seen}, last uCamPos {tuple(round(x, 3) for x in orbit.uniforms["uCamPos"])}')

# a monitor in a dark room: the engine's documented use (the texture as map + emissiveMap), baked and played
me = bpy.data.meshes.new('screen')
sw, sh = 1.6, 0.9
me.from_pydata([(-sw / 2, 0, 0), (sw / 2, 0, 0), (sw / 2, 0, sh), (-sw / 2, 0, sh)], [], [(0, 1, 2, 3)])
uv = me.uv_layers.new(name='UVMap')
for k, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
    uv.data[k].uv = c
screen = bpy.data.objects.new('screen', me)
bpy.context.scene.collection.objects.link(screen)
screen.location = (0.0, 0.0, 0.55)
me.materials.append(tex.material(emission_strength=1.2))
bez = bpy.data.meshes.new('bezel')
bez.from_pydata([(-sw / 2 - 0.05, 0.01, -0.05), (sw / 2 + 0.05, 0.01, -0.05), (sw / 2 + 0.05, 0.01, sh + 0.05),
                 (-sw / 2 - 0.05, 0.01, sh + 0.05)], [], [(0, 1, 2, 3)])
bezel = bpy.data.objects.new('bezel', bez)
bpy.context.scene.collection.objects.link(bezel)
bezel.location = (0.0, 0.0, 0.55)
bm = bpy.data.materials.new('bezel')
bm.use_nodes = True
bm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1.0)
bm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.3
bez.materials.append(bm)
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 12
tex.bake(1, 12, fps=1.0)                         # one shader second per film frame: 0 .. 11 s of the loop
files = [os.path.join(CACHE, f'tex_explosion_{f:04d}.png') for f in range(0, 13)]
C.check('bake wrote the frames and the hold copy', all(os.path.exists(f) for f in files), f'{len(files)} files')
import OpenImageIO as oiio  # noqa: E402
f1 = np.asarray(oiio.ImageBuf(files[1]).get_pixels(oiio.FLOAT))
f12 = np.asarray(oiio.ImageBuf(files[12]).get_pixels(oiio.FLOAT))
C.check('the baked frames differ', float(np.abs(f1 - f12).mean()) > 0.02, f'mean change {np.abs(f1 - f12).mean():.3f}')
node = next(n for n in me.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE')
C.check('the screen plays the sequence', node.image.source == 'SEQUENCE' and node.image_user.frame_duration == 12,
        f'{node.image.name}: {node.image.source}, frames {node.image_user.frame_start}+{node.image_user.frame_duration}')
if RENDER:
    C.camera((1.3, -2.9, 1.25), (0.0, 0.0, 0.95), lens=40)
    shots = []
    for f in (1, 12):
        sc.frame_set(f)
        p = os.path.join(C.OUT, f'tex_explosion_screen_f{f:02d}.png')
        C.check(f'screen render, frame {f}', C.render(p), p)
        shots.append(p)
    a = np.asarray(oiio.ImageBuf(shots[0]).get_pixels(oiio.FLOAT))
    b = np.asarray(oiio.ImageBuf(shots[1]).get_pixels(oiio.FLOAT))
    C.check('the screen shows the sequence frame by frame', float(np.abs(a - b).mean()) > 0.005,
            f'mean change {np.abs(a - b).mean():.3f}')
    C.sheet(shots, os.path.join(C.OUT, 'tex_explosion_screen.png'), cols=2)
    for p in shots:
        os.remove(p)
C.summary()
