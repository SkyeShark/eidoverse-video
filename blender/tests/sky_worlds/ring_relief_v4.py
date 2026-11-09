"""Eanpa's newest ringworld band: src/ring_relief.js (decodeRingRelief, loadRingRelief) and the v4 band it feeds.

The v4 set (ring_relief_v4.bin.gz: eroded heights with their own normals and AO, ring_albedo_v4.png, and
ring_relief_v3.bin.gz for the water normals) lives in Eanpa Engine's assets/ringworld/ and is not in this repo: the test
reads it there (read only) through make_sky(world='ringworld', ring={'reliefDir': ...}), and renders the same views
with the repo's v1 band beside it.

Checks (no GPU for the first group): the ERLF decoder round-trips a synthetic buffer and refuses truncated and foreign
ones as the JS does; the real v4 decodes at 4344 x 1448 with its heights in the repo height map's orientation once
flipped to top-down rows; the written normal + AO map keeps the AO in alpha and the convention of the repo's band
normal map; the band built from it displaces the v4 heights (peak under 85 m x 0.894) and wears the v4 albedo.

    bash run_blender.sh blender/tests/sky_worlds/ring_relief_v4.py [--hours 11,23] [--views horizon,up] [--no-render]
"""
import argparse
import math
import os
import struct
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky.ringworld import decode_ring_relief, load_ring_relief, RELIEF_MAGIC  # noqa: E402
from eidoblend.sky.bake.baker import load_image_rgba  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--hours', default='11,23')
ap.add_argument('--views', default='horizon,up')
ap.add_argument('--res', default='960x540')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--quality', default='film')
ap.add_argument('--no-render', action='store_true')
args = ap.parse_args(argv)
EANPA = 'C:/Users/sdn52/OneDrive/Desktop/Eanpa Engine/assets/ringworld'
OUT = os.path.join(HERE, 'out', 'ring_v4')
os.makedirs(OUT, exist_ok=True)
CEL = os.path.join(REPO, 'eidoverse', 'assets', 'sky', 'celestial')
ok_all = True


def check(name, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  (' + detail + ')') if detail else ''), flush=True)
    return ok


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / math.sqrt(float((a * a).sum() * (b * b).sum())))


def raises(buf):
    try:
        decode_ring_relief(buf)
    except ValueError as e:
        return str(e)
    return None


# ---- the decoder ----
w, h = 5, 3
hs = np.arange(w * h, dtype=np.float16).reshape(h, w) / 16
nao = (np.arange(w * h * 4) % 251).astype(np.uint8).reshape(h, w, 4)
buf = struct.pack('<4I', RELIEF_MAGIC, 1, w, h) + hs.tobytes() + nao.tobytes()
d = decode_ring_relief(buf)
check('decode_ring_relief round-trips the ERLF v1 container', d['width'] == w and d['height'] == h
      and np.array_equal(d['height_data'], hs.astype(np.float32)) and np.array_equal(d['normal_ao_data'], nao))
check('a truncated header raises', raises(buf[:12]) == 'Truncated ring relief header')
check('a foreign magic or version raises', raises(struct.pack('<4I', 0x12345678, 1, w, h) + buf[16:])
      == 'Unsupported ring relief format' and raises(struct.pack('<4I', RELIEF_MAGIC, 2, w, h) + buf[16:])
      == 'Unsupported ring relief format')
check('a short payload raises', raises(buf[:-1]) == 'Invalid ring relief dimensions or payload length')

if not os.path.exists(os.path.join(EANPA, 'ring_relief_v4.bin.gz')):
    print('SKIP the v4 set is not at %s' % EANPA)
    print('PASS ring_relief_v4 decoder' if ok_all else 'FAIL ring_relief_v4 decoder')
    raise SystemExit(0)

# ---- the real set ----
cache = os.path.join(OUT, 'cache_relief')
t0 = time.time()
rel = load_ring_relief(EANPA, cache)
H4 = rel['bandHeight']
check('load_ring_relief decodes the v4 relief at 4344 x 1448', H4.shape == (1448, 4344),
      '%s in %.1fs, heights %.3f..%.3f' % (H4.shape, time.time() - t0, H4.min(), H4.max()))
png = load_image_rgba(os.path.join(CEL, 'ring_band_height.png'), srgb=False)[::-1, :, 0]     # top-down
d4 = H4.reshape(724, 2, 2172, 2).mean((1, 3))
c_ok, c_flip = corr(d4, png), corr(d4[::-1], png)
check('the v4 heights, rows top-down, lie on the repo height map they were eroded from', c_ok > 0.7 and c_ok > c_flip + 0.3,
      'correlation %.3f, flipped %.3f' % (c_ok, c_flip))
nm = load_image_rgba(rel['bandNormal'], srgb=False)[::-1]                                   # top-down
nx = nm[..., 0] * 2 - 1
ny = nm[..., 1] * 2 - 1
dhdu = np.roll(H4, -1, 1) - np.roll(H4, 1, 1)
dhdr = np.roll(H4, -1, 0) - np.roll(H4, 1, 0)
check('the written normal map keeps the repo band maps\' convention (x = -dH/du, y = +dH/drow)',
      corr(nx, dhdu) < -0.95 and corr(ny, dhdr) > 0.95, 'x %.3f y %.3f' % (corr(nx, dhdu), corr(ny, dhdr)))
check('the AO stays data in the alpha channel', 0.55 < nm[..., 3].min() < 0.65 and 0.95 < nm[..., 3].mean() < 1.0,
      'AO min %.3f mean %.3f' % (nm[..., 3].min(), nm[..., 3].mean()))
check('the v3 water normals are kept for the waves', bool(rel['waterWaveNormal'])
      and os.path.exists(rel['waterWaveNormal']))


# ---- the band built on it, and renders beside the v1 band ----
def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    W, Hh = (int(v) for v in args.res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, Hh, 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = args.samples
    sc.eevee.use_raytracing = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.6
    sc.render.fps = 24
    sc.frame_start = sc.frame_end = 1
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=600, fill_type='NGON', location=(0, 0, 0))
    g = bpy.context.object
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.20, 0.17, 0.12, 1)
    g.data.materials.append(gm)
    for i, (col, rough, metal) in enumerate((((0.8,) * 3, 0.5, 0.0), ((0.18,) * 3, 0.5, 0.0), ((0.95,) * 3, 0.03, 1.0))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.5, location=(-1.4 + i * 1.4, 7.0, 0.5))
        s = bpy.context.object
        bpy.ops.object.shade_smooth()
        m = bpy.data.materials.new('ref%d' % i)
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*col, 1)
        b.inputs['Roughness'].default_value = rough
        b.inputs['Metallic'].default_value = metal
        s.data.materials.append(m)
    cd = bpy.data.cameras.new('cam')
    cd.lens_unit = 'FOV'
    cd.angle = math.radians(62.0)
    cd.clip_start = 0.1
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0.0, 0.0, 1.7)
    cam.rotation_mode = 'XYZ'
    return sc, cam


AIM = dict(horizon=6.0, up=60.0)
for hours in [float(x) for x in args.hours.split(',')]:
    for band in ('v4', 'v1'):
        sc, cam = setup_scene()
        ring = dict(reliefDir=EANPA) if band == 'v4' else dict(reliefDir=False)
        t0 = time.time()
        sky = make_sky(sc, camera=cam, world='ringworld', hours=hours, clouds='cumulus', quality=args.quality,
                       cache_dir=os.path.join(OUT, 'cache_%s_%05.2f' % (band, hours)), ring=ring)
        r = sky.ring
        built = time.time() - t0
        if band == 'v4' and hours == float(args.hours.split(',')[0]):
            gi = r.info['geometryRelief']
            check('v4 band: the ring reports Eanpa\'s v4 relief', r.info['relief'] == 'v4')
            check('v4 band: the relief peaks under 85 m x the v4 maximum, eased out under the stage',
                  0.8 * 85 * H4.max() < gi['max_height'] <= 85 * H4.max() + 1e-3,
                  'max relief %.1f m (85 x %.3f = %.1f)' % (gi['max_height'], H4.max(), 85 * H4.max()))
            labels = {n.label for n in r.band.data.materials[0].node_tree.nodes}
            check('v4 band: the material wears the v4 albedo and reads AO from the normal map\'s alpha',
                  'band_albedo_v4' in labels and r.opts.get('bandAOPackedNormal') is True
                  and r.opts.get('bandNormalScale') == 1.0)
            print('[ring_relief_v4] v4 band built in %.1fs: %d vertices' % (built, gi['vertices']), flush=True)
        if band == 'v1' and hours == float(args.hours.split(',')[0]):
            check('v1 band: reliefDir=False keeps the repo maps', r.info['relief'] == 'v1')
        if args.no_render:
            continue
        for view in args.views.split(','):
            cam.rotation_euler = (math.radians(90 + AIM[view]), 0.0, 0.0)
            sky.bake(log=lambda *a: None)
            sc.render.filepath = os.path.join(OUT, 'ring_%s_%05.2f_%s.png' % (band, hours, view))
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            print('[ring_relief_v4] %s %05.2f %s rendered in %.1fs' % (band, hours, view, time.time() - t1), flush=True)
print('PASS ring_relief_v4 all' if ok_all else 'FAIL ring_relief_v4 some')
