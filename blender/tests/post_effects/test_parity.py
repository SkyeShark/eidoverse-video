"""tests/post_effects/test_parity.py: the post effects over the still life against their WebGPU shaders in numpy
(ref_effects.py, transcribed from eidoverse/effects_tsl independently of the port).

  --stage sources   render the still life once (EEVEE, 960 x 540): src/opaque (Combined, Depth, Normal) and
                    src/alpha (the same on a transparent film: the sky's alpha 0)
  --stage parity    every case below composited over the saved frame (scene-linear EXR, before the view
                    transform) and compared with numpy: exact effects per pixel (mean error and the share of pixels off
                    by more than 0.02), round one's y-dependent groups (rgb_shift, glitch_bars, radial_blur) among
                    them; the hash-noise effects (hash_blur, vhs_tape, rain_on_camera), whose fract(sin(x) * 43758)
                    detail differs between any two GPUs and float64, on the frame's mean colour and 64 px blocks.
                    Opacity 0 gives the plain frame for the newly ported groups. --only a,b runs some; --dump writes
                    blender | numpy | difference x 10 strips to out/parity/.
Run from the main checkout (GPU jobs; on a shared machine queue them with EIDO_GPU_WRAP: blender/tests/_where.py):
    bash run_blender.sh <worktree>/blender/tests/post_effects/test_parity.py --stage sources
    bash run_blender.sh <worktree>/blender/tests/post_effects/test_parity.py --stage parity
"""
import os
import sys
import time
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import still_life as SL                                          # noqa: E402
import ref_effects as REF                                        # noqa: E402

A = SL.args()
STAGE = SL.arg(A, '--stage', 'parity')
ONLY = SL.arg(A, '--only', None)
DUMP = '--dump' in A
CHK = SL.Checks('parity')
FRAME = 30                                                       # t = 30 / 24 = 1.25 s

# (effect, options, kind): kind 'exact' per pixel, 'lowpass' after the 8 x 8 box (hash noise), source 'alpha'/'opaque'
CASES = [
    ('melt', {}, 'exact', 'opaque'),
    ('melt', {'speed': 1.5, 'swirl': 0.6, 'opacity': 0.8}, 'exact', 'opaque'),
    ('crt', {}, 'exact', 'opaque'),
    ('crt', {'opacity': 0.85}, 'exact', 'opaque'),
    ('chromatic_aberration_alpha', {}, 'exact', 'alpha'),
    ('chromatic_aberration_alpha', {'amount': 0.012, 'angle': 0.6}, 'exact', 'alpha'),
    ('full_toon', {}, 'exact', 'opaque'),
    ('full_toon', {'near_levels': 5, 'hue_shift': 0.8, 'outline_threshold': 0.3, 'saturation': 1.1,
                   'outline_color': (0.2, 0.05, 0.02)}, 'exact', 'opaque'),
    ('blueprint', {'paper_grain': 0.0}, 'exact', 'opaque'),
    ('blueprint', {'paper_grain': 0.0, 'cell_px': 30, 'rim_weight': 0.5, 'shade_stripe_px': 3.0,
                   'paper_color': (0.03, 0.08, 0.2)}, 'exact', 'opaque'),
    ('cross_hatch', {}, 'exact', 'opaque'),
    ('cross_hatch', {'hatch_strength': 1.0, 'wiggle': 0.6, 'outline_strength': 1.8, 'flicker': 0.5}, 'exact',
     'opaque'),
    ('underwater', {'bubble_count': 0}, 'exact', 'opaque'),
    ('underwater', {'bubble_count': 0, 'fog_density': 0.12, 'caustic_scale': 1.0, 'godray_amt': 0.9}, 'exact',
     'opaque'),
    ('lensflare', {}, 'exact', 'opaque'),
    ('lensflare', {'threshold': 1.5, 'ghost_spacing': 0.3, 'ghost_tint': (1.0, 0.8, 0.6), 'ghost_samples': 6,
                   'ghost_attenuation': 12.0, 'strength': 0.8}, 'exact', 'opaque'),
    ('anamorphic_flare', {}, 'exact', 'opaque'),
    ('anamorphic_flare', {'threshold': 1.5, 'scale': 3.0, 'samples': 48, 'color': (1.0, 0.5, 0.1), 'strength': 0.4},
     'exact', 'opaque'),
    ('depth_fog', {'mode': 'screen', 'noise_amount': 0.0}, 'exact', 'opaque'),
    ('depth_fog', {'mode': 'screen', 'noise_amount': 0.0, 'density': 0.08, 'edge_radius': 3, 'edge_strength': 3.0,
                   'color': (0.7, 0.6, 0.5), 'opacity': 0.9}, 'exact', 'opaque'),
    ('rgb_shift', {'amount': 0.012, 'angle': 1.2}, 'exact', 'opaque'),
    ('glitch_bars', {'bar_freq': 40, 'shift': 0.05, 'scroll_speed': 2.0}, 'exact', 'opaque'),
    ('radial_blur', {'center_x': 0.3, 'center_y': 0.25, 'exposure': 3.0}, 'exact', 'opaque'),
    ('hash_blur', {}, 'lowpass', 'opaque'),
    ('hash_blur', {'amount': 0.02, 'repeats': 24}, 'lowpass', 'opaque'),
    ('vhs_tape', {}, 'lowpass', 'opaque'),
    ('vhs_tape', {'intensity': 2.0}, 'lowpass', 'opaque'),
    ('rain_on_camera', {}, 'lowpass', 'opaque'),
    ('rain_on_camera', {'amount': 1.5, 'drop_size': 0.3, 'speed': 2.0}, 'lowpass', 'opaque'),
    # the verifier's: the effects the suite had only looked at, three's real kernels, transparent film
    ('wavy', {}, 'exact', 'opaque'),
    ('wavy', {'amplitude': 18, 'frequency': 0.05, 'phase': 1.0, 'animate': 1.0, 'anim_speed': 2.0, 'opacity': 0.7},
     'exact', 'opaque'),
    ('kaleidoscope', {}, 'exact', 'opaque'),
    ('kaleidoscope', {'segments': 9, 'rotate': 0.4}, 'exact', 'opaque'),
    ('dithering', {}, 'exact', 'opaque'),
    ('dithering', {'levels': 3, 'opacity': 0.8}, 'exact', 'opaque'),
    ('bw_halftone', {}, 'exact', 'opaque'),
    ('bw_halftone', {'dot_size': 3.0, 'angle': 15, 'threshold': 0.3, 'ink_color': (0.05, 0.02, 0.12),
                     'paper_color': (0.9, 0.85, 0.7)}, 'exact', 'opaque'),
    ('bleach_bypass', {}, 'exact', 'opaque'),
    ('bleach_bypass', {'amount': 0.6, 'opacity': 0.9}, 'exact', 'alpha'),
    ('glitch_bars', {'bar_freq': 40, 'shift': 0.05, 'opacity': 0.8}, 'exact', 'alpha'),
    ('anamorphic_flare', {'threshold': 1.2, 'scale': 2.0}, 'exact', 'alpha'),
    ('focus_blur', {'mode': 'screen', 'focus_distance': 6.5, 'focal_length': 4.0, 'bokeh_scale': 8.0}, 'exact',
     'opaque'),
    ('focus_blur', {'mode': 'screen', 'focus_distance': 12.0, 'focal_length': 6.0, 'bokeh_scale': 5.0,
                    'opacity': 0.8}, 'exact', 'opaque'),
]


def reference(eff, o, src, dep, nrm, cam, t, m):
    W, H = m['res']
    if eff == 'melt':
        return REF.melt(src, t, o.get('speed', 0.7), o.get('swirl', 0.2), o.get('opacity', 1.0))
    if eff == 'crt':
        return REF.crt(src, t, o.get('opacity', 1.0))
    if eff == 'chromatic_aberration_alpha':
        return REF.chromatic_aberration_alpha(src, o.get('amount', 0.005), o.get('angle', 0.0), o.get('opacity', 1.0))
    if eff == 'full_toon':
        return REF.full_toon(src, dep, nrm, cam, o)
    if eff == 'blueprint':
        return REF.blueprint(src, dep, nrm, cam, o)
    if eff == 'cross_hatch':
        return REF.cross_hatch(src, dep, nrm, cam, t, o)
    if eff == 'underwater':
        return REF.underwater(src, dep, nrm, cam, t, o, W / H)
    if eff == 'lensflare':
        return REF.lensflare(src, o)
    if eff == 'anamorphic_flare':
        return REF.anamorphic_flare(src, o)
    if eff == 'depth_fog':
        return REF.depth_fog(src, dep, cam, o)
    if eff == 'rgb_shift':
        return REF.rgb_shift(src, o.get('amount', 0.005), o.get('angle', 0.0), o.get('opacity', 1.0))
    if eff == 'glitch_bars':
        return REF.glitch_bars(src, t, o.get('bar_freq', 20.0), o.get('scroll_speed', 3.0), o.get('shift', 0.025),
                               o.get('opacity', 1.0))
    if eff == 'radial_blur':
        return REF.radial_blur(src, o.get('center_x', 0.5), o.get('center_y', 0.5), o.get('weight', 0.9),
                               o.get('decay', 0.95), o.get('exposure', 1.5), o.get('count', 32), o.get('opacity', 1.0))
    if eff == 'hash_blur':
        return REF.hash_blur(src, o.get('amount', 0.05), o.get('repeats', 45), o.get('opacity', 1.0))
    if eff == 'vhs_tape':
        return REF.vhs_tape(src, t, o.get('intensity', 1.0), o.get('opacity', 1.0))
    if eff == 'rain_on_camera':
        return REF.rain_on_camera(src, t, o.get('amount', 1.0), o.get('speed', 1.0), o.get('drop_size', 0.2))
    if eff == 'wavy':
        return REF.wavy(src, t, **o)
    if eff == 'kaleidoscope':
        return REF.kaleidoscope(src, **o)
    if eff == 'dithering':
        return REF.dithering(src, **o)
    if eff == 'bw_halftone':
        return REF.bw_halftone(src, **o)
    if eff == 'bleach_bypass':
        return REF.bleach_bypass(src, **o)
    if eff == 'focus_blur':                    # the port's structure (all passes at full size); three's half size below
        return REF.focus_blur(src, dep, cam, {k: v for k, v in o.items() if k != 'mode'}, half=False)
    raise KeyError(eff)


def sources():
    for name, transp in (('opaque', False), ('alpha', True)):
        t0 = time.time()
        m = SL.render_sources(name, transparent=transp)
        CHK(all(os.path.exists(p) for p in m['paths'].values()),
            f'source {name}: Combined, Depth, Normal written ({time.time() - t0:.1f} s)')


def parity():
    from eidoblend.look.post import custom_effects as CFX
    ms = {k: SL.meta(k) for k in ('opaque', 'alpha')}
    arrays = {k: SL.source_arrays(m) for k, m in ms.items()}
    cam = REF.Cam(ms['opaque'])
    t = FRAME / ms['opaque']['fps']
    for eff, o, kind, sname in CASES:
        if ONLY and eff not in ONLY.split(','):
            continue
        tag = f"{eff} {o if o else '(WebGPU defaults)'}"
        try:
            m = ms[sname]
            src, dep, nrm = arrays[sname]
            src = src.astype(np.float64)
            bpy.ops.wm.read_factory_settings(use_empty=True)
            sc = SL.post_scene(m, name=f'post_{eff}')
            t0 = time.time()
            e = CFX.apply_to(sc, eff, {eff: dict(o)})
            build = time.time() - t0
            t0 = time.time()
            got = SL.render_exr(sc, FRAME).astype(np.float64)
            comp = time.time() - t0
            want = reference(eff, o, src, dep.astype(np.float64), nrm.astype(np.float64), cam, t, m)
            if kind == 'lowpass':
                # the hash detail (which rows crease, where a drop runs, each pixel's grain) differs by float detail;
                # the effect's light, blur, tint and spread must not: the frame's mean colour and 32 px blocks
                g8, w8 = REF.box8(got[..., :3]), REF.box8(want[..., :3])
                err = np.abs(g8 - w8)
                big = float((err.max(axis=2) > 0.03).mean())
                g64, w64 = REF.box8(g8), REF.box8(w8)
                e32 = float(np.abs(g64 - w64).mean())
                dmean = np.abs(got[..., :3].mean(axis=(0, 1)) - want[..., :3].mean(axis=(0, 1))).max()
                ok = dmean < 0.01 and e32 < 0.012
                CHK(ok, f'{tag}: hash-noise effect, frame mean colour off by {dmean:.4f}, 64 px blocks by {e32:.2e} '
                        f'(8 px blocks {err.mean():.2e}, {big * 100:.1f}% off by > 0.03: the hash detail) '
                        f'(build {build:.1f} s, composite {comp:.2f} s)')
            else:
                err = np.abs(got[..., :3] - want[..., :3])
                big = float((err.max(axis=2) > 0.02).mean())
                aerr = float(np.abs(got[..., 3] - want[..., 3]).mean())
                ok = err.mean() < 2e-3 and big < 0.005 and aerr < 2e-3
                CHK(ok, f'{tag}: parity, mean |blender - numpy| {err.mean():.2e}, {big * 100:.3f}% of pixels off by '
                        f'> 0.02, alpha {aerr:.1e} (build {build:.1f} s, composite {comp:.2f} s)')
                if not ok:
                    heat = np.clip(err.max(axis=2) / 0.1, 0, 1)
                    _save_png(heat, os.path.join(SL.OUT, 'parity', f'err_{eff}_{len(CHK.report)}.png'))
            CHK.report[tag] = {'mean': float(err.mean()), 'off': big, 'build_s': round(build, 2),
                               'composite_s': round(comp, 3)}
            if eff == 'focus_blur':                              # three runs its blur passes at half size
                half = REF.focus_blur(src, dep.astype(np.float64), cam, {k: v for k, v in o.items() if k != 'mode'})
                eh = np.abs(got[..., :3] - half[..., :3])
                hb = float((eh.max(axis=2) > 0.05).mean())
                CHK(eh.mean() < 0.01 and hb < 0.02,
                    f'{tag}: against three run at half size (its blur targets): mean {eh.mean():.2e}, {hb * 100:.2f}% '
                    f'off by > 0.05 (the port runs every pass at full size: about a pixel sharper)')
                CHK.report[tag]['vs_half_size'] = float(eh.mean())
            if DUMP:                                             # blender | numpy | |difference| x 10, sRGB-encoded
                k = len(CHK.report)
                enc = lambda x: np.clip(x, 0, 1) ** (1 / 2.2)          # noqa: E731
                row = np.concatenate([enc(got[..., :3]), enc(want[..., :3]),
                                      np.clip(np.abs(got[..., :3] - want[..., :3]) * 10, 0, 1)], axis=1)
                _save_png(row, os.path.join(SL.OUT, 'parity', f'dump_{k:02d}_{eff}.png'))
            if eff in ('lensflare', 'anamorphic_flare', 'depth_fog', 'focus_blur', 'wavy', 'kaleidoscope', 'dithering',
                       'bw_halftone', 'bleach_bypass') and 'opacity' in e.uniforms and sname == 'opaque':
                e.uniforms['opacity'].default_value = 0.0
                z = SL.render_exr(sc, FRAME)
                d0 = float(np.abs(z[..., :3] - src[..., :3]).max())
                CHK(d0 < 1e-4, f'{tag}: opacity 0 is the plain frame (max diff {d0:.1e})')
        except Exception as ex:                                  # noqa: BLE001
            traceback.print_exc()
            CHK(False, f'{tag}: {ex!r}')


def _save_png(img, path):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)


try:
    if STAGE == 'sources':
        sources()
    elif STAGE == 'parity':
        parity()
    else:
        raise SystemExit(f'--stage sources | parity, not {STAGE!r}')
except Exception:                                                # noqa: BLE001
    traceback.print_exc()
    CHK.fail.append('exception: ' + traceback.format_exc().splitlines()[-1])
CHK.save(STAGE + (f'_{ONLY}' if ONLY else ''))
