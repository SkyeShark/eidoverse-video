"""Every make_red_giant option, rendered against the default (make_sky(world='shieldworld', redGiant={...})).

The star's options are seen at sunset (17.8 h) looking at the giant, the shield's at 01:24 looking 50 degrees up at
the lattice from 8 km off-centre (the shield is a sphere about the origin, so only there does its radius show); clear
sky so nothing covers them; frame 48 of a 48-frame scene (t = 1.96 s), so the plasma's speed shows. Each option must
change its view against the default, over the frame (mean |difference|) or locally (a prominence at the limb: the
99.9th percentile), or it fails. Without the GPU:
the shield can be left out of a red giant (the shieldworld itself always has it, as sky_worlds.js), and an empty flare
list means no prominences and a zero burst, as the JS's opts.flares ?? FLARES.

    bash run_blender.sh blender/tests/sky_worlds/redgiant_options.py [--res 480x270] [--only granScale,...]
Writes out/redgiant/<option>.png and sheet_star.png / sheet_shield.png (default first, then the options in order).
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
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky.redgiant import make_red_giant, FLARES  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='480x270')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--only', default='')
args = ap.parse_args(argv)
OUT = os.path.join(HERE, 'out', 'redgiant')
os.makedirs(OUT, exist_ok=True)
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)
    return ok


# ---- no GPU: the options the views cannot show ----
rg = make_red_giant({'shield': False})
check('shield=False leaves the lattice out of the shader (the shieldworld itself always has it)',
      'HAS_SHIELD' not in rg.shader_defines() and rg.shader_defines().get('HAS_GIANT') == 1)
rg = make_red_giant({'flares': []})
rg.update(30.0)
check('flares=[] means no prominences or sunspot events and a zero burst (opts.flares ?? FLARES)',
      rg.flares == () and rg.burst_k == 0.0 and 'flare slot' not in rg.celestial_glsl()
      and 'paired active region' not in rg.celestial_glsl())
check('the default keeps Eanpa\'s eight slots', len(make_red_giant().flares) == len(FLARES) == 8)

STAR = [('default', {}), ('angularRadius_0.18', dict(angularRadius=0.18)), ('granScale_20', dict(granScale=20)),
        ('plasmaSpeed_4', dict(plasmaSpeed=4.0)), ('flares_none', dict(flares=[])), ('flareBoost_1', dict(flareBoost=1.0)),
        ('starColor_rose', dict(starColor=(1.0, 0.55, 0.55))),
        ('paletteTint_earthlike', dict(paletteTint=dict(zen=(0.30, 0.45, 0.80), hor=(0.90, 0.80, 0.70),
                                                         sun=(1.0, 0.90, 0.80))))]
SHIELD = [('default', {}), ('hexScale_10', dict(hexScale=10)), ('shieldRadius_12000', dict(shieldRadius=12000)),
          ('shieldColor_ember', dict(shieldColor=(1.6, 0.4, 0.2)))]
only = set(filter(None, args.only.split(',')))
FR = 48


def render(name, opts, hours, view):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, H = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, FR
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.mesh.primitive_plane_add(size=2000, location=(0, 0, 0))
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.13, 0.10, 1)
    bpy.context.object.data.materials.append(gm)
    cd = bpy.data.cameras.new('cam')
    cd.lens_unit = 'FOV'
    cd.angle = math.radians(62.0)
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    # the shield is a sphere about the world origin: from the origin every radius projects alike, so the shield
    # view stands 8 km off-centre, where shieldRadius sets the lattice's parallax
    cam.location = (0.0, 0.0, 1.7) if view == 'star' else (8000.0, 0.0, 1.7)
    cam.rotation_mode = 'XYZ'
    sky = make_sky(sc, camera=cam, world='shieldworld', hours=hours, clouds='clear', quality='draft',
                   cache_dir=os.path.join(OUT, 'cache_%s_%s' % (view, name)), redGiant=opts)
    sky.update(0.0)
    if view == 'star':
        d = sky.sun_dir
        yaw, pitch = math.degrees(math.atan2(d[0], d[1])), max(math.degrees(math.asin(d[2])), 4.0)
    else:
        yaw, pitch = 30.0, 50.0
    cam.rotation_euler = (math.radians(90 + pitch), 0.0, math.radians(-yaw))
    sky.bake(frame_start=FR, frame_end=FR, log=lambda *a: None)
    sc.frame_set(FR)
    sc.render.filepath = os.path.join(OUT, '%s_%s.png' % (view, name))
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return px


def sheet(path, tiles, cols=4):
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    out = np.zeros((rows * h, cols * w, 4), np.float32)
    out[..., 3] = 1
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        out[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w, :3] = t       # Blender rows run bottom-up
    im = bpy.data.images.new(os.path.basename(path), out.shape[1], out.shape[0], alpha=True)
    im.pixels.foreach_set(out.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


for view, hours, variants in (('star', 17.8, STAR), ('shield', 1.4, SHIELD)):
    base = None
    tiles = []
    for name, opts in variants:
        if only and name != 'default' and name not in only:
            continue
        px = render(name, opts, hours, view)
        tiles.append(px)
        if name == 'default':
            base = px
            print('[redgiant_options] %s default mean %.3f' % (view, float(px.mean())), flush=True)
            continue
        d = np.abs(px - base).sum(-1)
        dlt, loc = float(d.mean()), float(np.percentile(d, 99.9))
        # a whole-frame change (disc size, granulation, tint) or a local one (a prominence at the limb)
        check('%s: %s changes the frame against the default' % (view, name), dlt > 0.004 or loc > 0.2,
              'mean |delta| %.4f, 99.9th percentile %.3f' % (dlt, loc))
    sheet(os.path.join(OUT, 'sheet_%s.png' % view), tiles)
print('PASS redgiant_options all' if ok_all else 'FAIL redgiant_options some')
