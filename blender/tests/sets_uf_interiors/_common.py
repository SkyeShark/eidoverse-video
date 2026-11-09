"""Shared helpers of the interiors' Blender tests: PASS / FAIL lines, the render setup the WebGPU probes used (their
bloom 0.55 / 0.5 / 0.7), the claudesona at the mark for scale (opt-in), image statistics, a contact sheet."""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..'))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

import numpy as np  # noqa: E402

OUT = os.path.join(HERE, 'out')
ART = os.path.join(OUT, 'art_cache')
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)
    return ok


def args(defaults):
    """--key value / --flag after Blender's '--' (common.script_args), over `defaults`."""
    from eidoblend import common
    a = common.script_args()
    out = dict(defaults)
    i = 0
    while i < len(a):
        k = a[i].lstrip('-').replace('-', '_')
        if i + 1 < len(a) and not a[i + 1].startswith('--'):
            v = a[i + 1]
            d = defaults.get(k)
            out[k] = type(d)(v) if isinstance(d, (int, float)) and not isinstance(d, bool) else v
            i += 2
        else:
            out[k] = True
            i += 1
    return out


PROBE_BLOOM = {'strength': 0.55, 'radius': 0.5, 'threshold': 0.7}     # the WebGPU set probes' bloom


def render_setup(scene, res=(960, 540), samples=16, bloom=True, look='None', exposure=0.0, bloom_opts=None):
    """EEVEE, AgX, the probes' bloom (bloom_opts: another); small probes (the GPU is shared)."""
    r = scene.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.fps = 30
    scene.eevee.taa_render_samples = samples
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = look
    scene.view_settings.exposure = exposure
    r.image_settings.file_format = 'PNG'
    r.film_transparent = False
    if bloom:
        from eidoblend.look.post import custom_effects as fx
        fx.apply_to(scene, 'bloom', {'bloom': dict(bloom_opts or PROBE_BLOOM)})


def load_singer(location, heading_deg=0.0, scale=0.87, parent=None, vrm='claude_suit', wear=None):
    """the claudesona (claude_suit.vrm) at the mark, at the scale the sets' cams are framed for, playing idle (a
    scale figure, as in the WebGPU probes). vrm='claude_suit_wardrobe', wear='tuta': the TuTa outfit
    (characters.claudesona.make_wardrobe)."""
    from eidoblend.characters.vrm import load_vrm
    from eidoblend.characters.vrma import play_vrma_default
    h = load_vrm(vrm, location=location, rotation=heading_deg)
    h.arm.scale = (scale, scale, scale)
    if wear:
        from eidoblend.characters.claudesona import make_wardrobe
        h.wardrobe = make_wardrobe(h, wear=wear)
    play_vrma_default(h, 'idle')
    if parent is not None:
        from mathutils import Matrix
        mw = h.arm.matrix_world.copy()
        h.arm.parent = parent
        h.arm.matrix_parent_inverse = parent.matrix_world.inverted() if parent else Matrix.Identity(4)
        h.arm.matrix_world = mw
    return h


def apply_look(scene, look='argue', palette=None):
    """An aeropittura look (look/post/aeropittura.py) under the HUD, as the WebGPU probes ran it; `palette`
    overrides the look's palette weight (on the white showroom 0.22 keeps the stage white: 'argue, cold'). Returns
    its uniforms."""
    from eidoblend.look.post import custom_effects as fx, aeropittura as AP
    e = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': 'under'}})
    U = e.uniforms['aeropittura']
    AP.apply_look(U, AP.LOOKS[look], 1.0)
    if palette is not None:
        U['palette'].default_value = float(palette)
    return U


def aim_look(scene, U, cam, focal_ob):
    """the look's focal (the set's idol) projected through the shot's camera; False when it is behind it."""
    from eidoblend.look.post import aeropittura as AP
    scene.camera = cam
    bpy_update()
    uv = AP.project_focal(scene, focal_ob.matrix_world.translation, cam)
    return uv is not None and AP.set_focal(U, *uv)


def bpy_update():
    import bpy
    bpy.context.view_layer.update()


def render_still(scene, cam, frame, path):
    import bpy
    scene.camera = cam
    scene.frame_set(frame)
    scene.render.filepath = path
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    dt = time.perf_counter() - t
    ok = os.path.isfile(path)
    check(f'render {os.path.basename(path)} written', ok, f'{dt:.1f} s')
    return dt


def stats(path):
    """(mean luma 0..1, share of clipped pixels, share of black pixels) of a PNG."""
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0
    luma = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return float(luma.mean()), float((a.max(2) > 0.995).mean()), float((a.max(2) < 0.004).mean())


def sheet(paths, out, cols=3, width=1440):
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert('RGB') for p in paths if os.path.isfile(p)]
    if not ims:
        return
    cw = width // cols
    ch = int(cw * ims[0].height / ims[0].width)
    rows = math.ceil(len(ims) / cols)
    s = Image.new('RGB', (cw * cols, (ch + 18) * rows), (20, 20, 20))
    d = ImageDraw.Draw(s)
    for i, (im, p) in enumerate(zip(ims, paths)):
        x, y = (i % cols) * cw, (i // cols) * (ch + 18)
        s.paste(im.resize((cw, ch)), (x, y + 18))
        d.text((x + 4, y + 3), os.path.splitext(os.path.basename(p))[0], fill=(230, 230, 230))
    s.save(out, quality=88)


def done():
    print('ALL PASS' if not FAILS else f'{len(FAILS)} FAILED: {FAILS}', flush=True)
    return 0 if not FAILS else 1
