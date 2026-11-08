"""Compile every sky-world variant of sky.glsl and render its layers small: the shader-level check.

For each world (earth, the ringworld's ring deck and analytic band in the environment, the shieldworld's red giant,
shield and moon dust) it renders the camera layers and the environment at 192x108 / 256x128, prints their
statistics and one PASS/FAIL line per world, and writes previews to out/variants/.

    bash run_blender.sh blender/tests/sky_worlds/shader_variants.py [--hours 12] [--res 192x108]
"""
import argparse
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import palette as P  # noqa: E402
from eidoblend.sky.sky_system import SkySystem  # noqa: E402
from eidoblend.sky.weather_system import WeatherSystem  # noqa: E402
from eidoblend.sky.worlds import WORLDS, ring_constants  # noqa: E402
from eidoblend.sky.redgiant import make_red_giant  # noqa: E402
from eidoblend.sky.bake.baker import SkyBaker  # noqa: E402
from eidoblend.sky.bake.celestial import dust_glsl  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--hours', type=float, default=14.0)
ap.add_argument('--res', default='192x108')
args = ap.parse_args(argv)
W, H = (int(v) for v in args.res.split('x'))
OUT = os.path.join(HERE, 'out', 'variants')
os.makedirs(OUT, exist_ok=True)
A = os.path.join(REPO, 'eidoverse', 'assets', 'sky')


def save_png(path, img, exposure=1.0):
    import bpy
    h, w = img.shape[:2]
    rgb = np.clip(img[..., :3] * exposure, 0, None)
    rgb = rgb / (1.0 + rgb)                     # a plain Reinhard preview, not a grade
    rgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def camera_basis(yaw_deg, pitch_deg):
    """(right, up, back) Blender world vectors of a camera looking along yaw (from +Y) and pitch."""
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    fwd = (math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch))
    right = P.norm3(P.cross3(fwd, (0, 0, 1)))
    up = P.norm3(P.cross3(right, fwd))
    return right, up, (-fwd[0], -fwd[1], -fwd[2])


ok_all = True
for world in ('earth', 'ringworld', 'shieldworld'):
    Wd = WORLDS[world]
    opts = dict(Wd['sky'])
    opts.update(hours=args.hours, clouds='cumulus')
    defines, celestial, dust, ring_map, ring_mask = {}, '', '', None, None
    rg = None
    if world == 'shieldworld':
        rg = make_red_giant({'shield': True})
        opts['paletteTint'] = rg.palette_tint
        defines.update(rg.shader_defines())
        celestial = rg.celestial_glsl()
        # a stand-in cluster geometry (the real numbers come from the GLB in asteroid_moon.py)
        pr = [0.55] + [0.2] * 5 + [0.08] * 10
        dust = dust_glsl(rc=2.6, cent=(0.1, 0.0, 0.0), arc_x=2.2, hero_r=0.55, piece_r=pr,
                         big=[0, 1, 2, 3, 4, 5, 6], streams=[1, 2, 3, 4, 5, 6])
        defines['HAS_DUST'] = 1
    if Wd['sky'].get('ringCurve'):
        defines.update(ring_constants(Wd['sky']['ringCurve']))
        defines.update(HAS_RING_ENV=1, RING_CENTER_Y=4921.6, RING_BAND_R=5000.0, RING_HALF_W=483.0, RING_REPEAT=8.0)
        # the band's colour map lives inside the GLB: a ringworld build extracts it into its cache
        import glob
        found = sorted(glob.glob(os.path.join(HERE, 'out', '**', 'ring_band_albedo.png'), recursive=True))
        ring_map = found[0] if found else None
        print('[ringworld] band map for the environment trace: %s' % (ring_map or
              'none yet (run world_views.py --world ringworld first): the trace samples black'))
        ring_mask = os.path.join(A, Wd['band']['landmask'])
    if opts.get('moonLightColor') is None and Wd.get('planetShine'):
        opts['moonLightColor'] = Wd['planetShine']
    sky = SkySystem(opts)
    wx = WeatherSystem(sky)
    if rg:
        rg.attach(sky)
    sky.update(1.0)
    wx.update(1.0)
    if rg:
        rg.update(1.0)
        U = sky.U
        U['dustOrigin'] = P.norm3((0.3, 0.5, -1.0))
        U['dustOrigin'] = tuple(c * 30000 for c in U['dustOrigin'])
        s = 1.0 / 1400
        U['dustM0'], U['dustM1'], U['dustM2'] = (s, 0, 0), (0, s, 0), (0, 0, s)
        U['dustSunL'] = P.norm3(sky.sun_dir)
        U['dustT'] = 1.0
        U['dustSunCol'] = (1.0, 0.62, 0.35)
        U['dustGain'] = 2.0
        U['dustFade'] = 1.0
        U['plumes'] = [(-1.3, 0.0, 0.05, 0), (0.9, 0.2, 0.2, 0), (1.5, 0.0, 0.1, 0)]
        U['pieces'] = [(-1.5 + i * 0.25, 0.05 * math.sin(i), 0.05 * math.cos(i), 0) for i in range(16)]
    stars = os.path.join(A, Wd['starmap'])
    moon = os.path.join(A, Wd['moonmap']) if Wd.get('moonmap') else None
    bk = SkyBaker(stars=stars, moon=moon, n_march=60, n_light=20, m_pass=3, defines=defines, celestial=celestial,
                  dust=dust, phase_soften=opts.get('cloudPhaseSoften', 0.0), ring_map=ring_map, ring_mask=ring_mask)
    t0 = time.time()
    try:
        views = {}
        # look at the sun (the red giant, or the sun) and along the ring (+Y in Blender = three -Z)
        sd = P.three_to_blender(sky.sun_dir)
        yaw = math.degrees(math.atan2(sd[0], sd[1]))
        pitch = math.degrees(math.asin(max(-1, min(1, sd[2]))))
        views['sun'] = camera_basis(yaw, max(pitch, 8))
        views['ring'] = camera_basis(0.0, 25.0)
        tx = math.tan(math.radians(30))
        for vname, basis in views.items():
            L = bk.camera_layers(sky.U, basis, (tx, tx * H / W), (0.0, 2.0, 0.0), W, H)
            for k, img in L.items():
                save_png(os.path.join(OUT, '%s_%s_%s.png' % (world, vname, k)), img)
            print('[%s/%s] cloud a mean %.3f  back mean %.4f  cam mean %.4f%s' % (
                world, vname, L['cloud'][..., 3].mean(), L['back'][..., :3].mean(), L['cam'][..., :3].mean(),
                ('  shield a mean %.4f max %.3f' % (L['shield'][..., 3].mean(), L['shield'][..., 3].max()))
                if 'shield' in L else ''))
            single = bk.camera_layer(sky.U, basis, (tx, tx * H / W), (0.0, 2.0, 0.0), W, H, output=0)
            d = np.abs(single[..., :3] - L['cam'][..., :3]).mean() / max(1e-6, single[..., :3].mean())
            print('   layered composite vs single pass: %.5f relative' % d)
            ok_all &= d < 0.01 and np.isfinite(L['cam']).all()
        env = bk.environment(sky.U, 256, 128)
        save_png(os.path.join(OUT, '%s_env.png' % world), env)
        print('[%s] env mean %.4f finite %s  (%.2fs total)' % (world, env[..., :3].mean(), np.isfinite(env).all(),
                                                                time.time() - t0))
        ok = np.isfinite(env).all()
        print('%s %s: compiled and rendered' % ('PASS' if ok else 'FAIL', world))
        ok_all &= ok
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('FAIL %s: %s' % (world, str(e).splitlines()[0] if str(e) else e))
        ok_all = False
print('PASS all variants' if ok_all else 'FAIL some variant')
