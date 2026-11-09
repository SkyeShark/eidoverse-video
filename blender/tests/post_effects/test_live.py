"""tests/post_effects/test_live.py: the scene-side effects on a live render of the still life (EEVEE), where a saved
frame cannot stand in: retro_wireframe (a material override and a world override: the still life's sky is a LINKED
gradient), underwater's rising bubbles, godrays (the fog volume and the light's volume factor from strength and
opacity), depth_fog's two modes side by side, focus_blur's WebGPU knobs (focal_length, bokeh_scale -> an f-stop), and a
saved .blend of the wireframe reopened in a fresh Blender. Sheets to look at, PASS/FAIL lines for what is measured.

Run from the main checkout (the GPU slot), after test_parity.py --stage sources:
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_effects/test_live.py
    (--stage reopen runs inside the fresh Blender the main stage starts for the saved .blend)
"""
import math
import os
import subprocess
import sys
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import still_life as SL                                          # noqa: E402

from eidoblend.look import frame_stats as FS                     # noqa: E402

A = SL.args()
STAGE = SL.arg(A, '--stage', 'live')
CHK = SL.Checks('live')
OUT = os.path.join(SL.OUT, 'live')
os.makedirs(OUT, exist_ok=True)


def png(sc, name, frame=1):
    sc.frame_set(frame)
    s = sc.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.color_mode = 'IMAGE', 'PNG', '8', 'RGB'
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath


def rgb(p):
    return FS.read_rgb(p).astype(float)


def wireframe():
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import screen_effects as SE
    sc = SL.build()
    plain = png(sc, 'plain')
    paths, labels = [plain], ['still life (plain)']
    e = CFX.apply_to(sc, 'retro_wireframe', {'retro_wireframe': {'color': 'green', 'bgColor': (0.0, 0.02, 0.0)}})
    vl = bpy.context.view_layer
    CHK(vl.material_override is not None and vl.world_override is not None and sc.world.name == 'still_life_sky',
        'retro_wireframe: a material override and a world override; the scene keeps its own world')
    for name in ('green', 'amber', 'blue', 'multicolor'):
        SE.set_wire_color(sc, e.uniforms, name)
        p = png(sc, f'wire_{name}')
        paths.append(p)
        labels.append(f'retro_wireframe {name}' + (' (per triangle)' if name == 'multicolor' else ''))
        im = rgb(p)
        if name == 'green':
            sky = im[:60].reshape(-1, 3)                          # the top rows: nothing but sky in the plain frame
            CHK(sky[:, 0].max() < 20 and sky[:, 2].max() < 20 and sky[:, 1].mean() < 60,
                f'retro_wireframe: the linked sky gradient is replaced by bgColor (0, 0.02, 0) (top rows mean '
                f'{np.round(sky.mean(axis=0), 1).tolist()} in sRGB; the plain sky is '
                f'{np.round(rgb(plain)[:60].reshape(-1, 3).mean(axis=0), 1).tolist()})')
            lit = (im[..., 1] > 60) & (im[..., 0] < im[..., 1] * 0.5)
            CHK(0.01 < lit.mean() < 0.5, f'retro_wireframe green: {lit.mean() * 100:.1f}% of pixels are green lines')
            # line width: across the floor's long edges, a lit run is about line_width (1.5) px
            runs = []
            for row in range(300, 520, 20):
                r = lit[row].astype(int)
                d = np.diff(np.concatenate([[0], r, [0]]))
                st, en = np.where(d == 1)[0], np.where(d == -1)[0]
                runs += list(en - st)
            med = float(np.median(runs)) if runs else 0.0
            CHK(1.0 <= med <= 3.0, f'retro_wireframe: the lines are {med:.1f} px wide (median lit run across rows; '
                                   f'line_width 1.5, anti-aliased)')
        if name == 'multicolor':
            hues = im.reshape(-1, 3)[(im.reshape(-1, 3).max(axis=1) > 60)]
            spread = len({tuple((h // 64).astype(int)) for h in hues[::7]})
            CHK(spread >= 5, f'retro_wireframe multicolor: {spread} distinct colour classes in the lines')
    e.uniforms['line_width'].default_value = 3.0
    p = png(sc, 'wire_width3')
    paths.append(p)
    labels.append('line_width 3 (multicolor)')
    # a saved .blend of the wireframe reopened in a fresh Blender renders the same picture (no Python needed)
    blend = os.path.join(OUT, 'wire.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    SE.retro_wireframe_cleanup(sc)
    p = png(sc, 'wire_cleanup')
    paths.append(p)
    labels.append('after retro_wireframe_cleanup()')
    d = float(np.abs(rgb(p) - rgb(plain)).mean())
    CHK(vl.material_override is None and vl.world_override is None and 'retro_wireframe_bg' not in bpy.data.worlds
        and d < 1.5, f'retro_wireframe cleanup: overrides gone, the world back (mean diff to the plain frame {d:.2f} '
                     f'levels)')
    FS.sheet(paths, os.path.join(OUT, 'sheet_wireframe.jpg'), cols=4, tile=440, labels=labels)
    return blend


def reopen(blend):
    exe = bpy.app.binary_path
    out = os.path.join(OUT, 'wire_reopened.png')
    r = subprocess.run([exe, '-b', '--factory-startup', blend, '-o', out.replace('.png', '_#'), '-F', 'PNG', '-f', '1'],
                       capture_output=True, text=True, timeout=600)
    got = os.path.join(OUT, 'wire_reopened_1.png')
    ok = os.path.exists(got)
    if ok:
        d = float(np.abs(rgb(got) - rgb(os.path.join(OUT, 'wire_width3.png'))).mean())
        CHK(d < 1.0, f'retro_wireframe saved .blend, rendered in a fresh Blender: the same picture (mean diff {d:.2f})')
    else:
        CHK(False, f'retro_wireframe saved .blend did not render: {r.stderr[-400:]}')


def water():
    from eidoblend.look.post import custom_effects as CFX
    sc = SL.build()
    CFX.apply_to(sc, 'underwater', {'underwater': {'bubble_count': 600}})
    CHK('uw_bubbles' in bpy.data.objects, 'underwater: the bubbles object rises round the camera (Geometry Nodes)')
    ps = [png(sc, f'underwater_f{f:02d}', f) for f in (1, 36)]
    a, b = rgb(ps[0]), rgb(ps[1])
    moved = float((np.abs(a - b).max(axis=2) > 6).mean())
    CHK(moved > 0.02, f'underwater live: caustics, rays and bubbles move between frames 1 and 36 ({moved * 100:.1f}%)')
    return ps


def fogs():
    from eidoblend.look.post import custom_effects as CFX
    out = []
    sc = SL.build()
    plain = png(sc, 'fog_plain')
    out.append((plain, 'plain'))
    e = CFX.apply_to(sc, 'depth_fog', {'depth_fog': {'density': 0.04, 'color': (0.55, 0.62, 0.72),
                                                     'noise_amount': 0.4, 'size': (80.0, 80.0, 12.0), 'far': 120.0}})
    CHK('look_depth_fog' in bpy.data.objects, "depth_fog mode 'volume' (the default): a fog volume, lit by the sun")
    out.append((png(sc, 'fog_volume'), "depth_fog 'volume' (density 0.04 / m, WebGPU's colour and noise)"))
    CFX.clear(sc)
    CHK('look_depth_fog' not in bpy.data.objects, 'clear(): the fog volume is gone')
    e = CFX.apply_to(sc, 'depth_fog', {'depth_fog': {'mode': 'screen'}})
    from eidoblend.look.post import chain
    CHK([n for _s, n, _x in chain.stages(sc)] == ['depth_fog'] and CFX.applied(sc) == [('under', 'depth_fog',
                                                                                         e.nodes['depth_fog'])],
        "depth_fog mode 'screen': one chain stage under the overlay, listed once by applied()")
    out.append((png(sc, 'fog_screen'), "depth_fog 'screen' (WebGPU's pass, its defaults)"))
    CFX.clear(sc)
    # godrays: the fog volume with volumetric shadows, the sun's volume factor = strength / 0.5 x opacity
    sun = next(o for o in sc.objects if o.type == 'LIGHT')
    f0 = sun.data.volume_factor
    CFX.apply_to(sc, 'godrays', {'godrays': {'density': 0.03, 'size': (80.0, 80.0, 12.0), 'far': 120.0,
                                             'strength': 1.5, 'opacity': 0.8}})
    CHK(abs(sun.data.volume_factor - 1.5 / 0.5 * 0.8) < 1e-6 and sc.eevee.use_volumetric_shadows,
        f'godrays: the sun (found as the first sun light) scatters at volume factor {sun.data.volume_factor:.2f} '
        f'(strength 1.5 / 0.5 x opacity 0.8); volumetric shadows on')
    out.append((png(sc, 'godrays_strong'), 'godrays strength 1.5, opacity 0.8 (volume factor 2.4)'))
    CFX.clear(sc)
    CHK(abs(sun.data.volume_factor - f0) < 1e-6, f'clear(): the sun scatters as before ({sun.data.volume_factor})')
    CFX.apply_to(sc, 'godrays', {'godrays': {'density': 0.03, 'size': (80.0, 80.0, 12.0), 'far': 120.0,
                                             'light': sun.name}})
    out.append((png(sc, 'godrays_default'), 'godrays strength 0.5 (volume factor 1, physical), light by name'))
    CFX.clear(sc)
    FS.sheet([p for p, _l in out], os.path.join(OUT, 'sheet_fogs.jpg'), cols=3, tile=560, labels=[l for _p, l in out])


def focus():
    from eidoblend.look.post import custom_effects as CFX
    sc = SL.build()
    suz = bpy.data.objects['suzanne']
    cam = sc.camera
    e = CFX.apply_to(sc, 'focus_blur', {'focus_blur': {'focus_objects': [suz], 'focal_length': 1.0,
                                                       'bokeh_scale': 2.0}})
    d = cam.data.dof
    from eidoblend.look import camera as C
    sc.frame_set(sc.frame_start)
    fwd = cam.matrix_world.to_3x3() @ __import__('mathutils').Vector((0.0, 0.0, -1.0))
    s = (C.focus_point(suz) - cam.matrix_world.translation).dot(fwd)        # its focus point: the bounds' centre
    want = CFX.fstop_for_blur(sc, cam, s, 1.0, 2.0)
    # the blur radius it gives a point 1 m behind the focus plane, in pixels: f^2 dz / (2 N z (s - f)) / sensor * W
    f, z = cam.data.lens, (s + 1.0) * 1000.0
    rad = f * f * 1000.0 / (2 * d.aperture_fstop * z * (s * 1000.0 - f)) / cam.data.sensor_width * SL.RES[0]
    CHK(d.use_dof and abs(d.aperture_fstop - want) < 1e-4 and abs(rad - 3.0) < 0.01,
        f'focus_blur focal_length 1 m, bokeh_scale 2 -> f/{d.aperture_fstop:.3f} on the {f:.1f} mm lens: a point '
        f'1 m behind the focus ({s:.2f} m) blurs to a {rad:.2f} px radius (1.5 x bokeh_scale: three\'s 64-tap disc '
        f'and its max pass)')
    p1 = png(sc, 'focus_suzanne')
    CFX.clear(sc)
    CHK(not cam.data.dof.use_dof, 'clear(): the lens as it was')
    FS.sheet([os.path.join(OUT, 'fog_plain.png'), p1], os.path.join(OUT, 'sheet_focus.jpg'), cols=2, tile=640,
             labels=['plain', f'focus_blur on Suzanne, focal_length 1, bokeh_scale 2 (f/{want:.3f})'])


try:
    if STAGE == 'live':
        blend = wireframe()
        water_ps = water()
        fogs()
        focus()
        reopen(blend)
        FS.sheet(water_ps, os.path.join(OUT, 'sheet_underwater.jpg'), cols=2, tile=640,
                 labels=['underwater live, frame 1', 'frame 36: the bubbles have risen'])
    else:
        raise SystemExit(f'--stage live, not {STAGE!r}')
except Exception:                                                # noqa: BLE001
    traceback.print_exc()
    CHK.fail.append('exception: ' + traceback.format_exc().splitlines()[-1])
CHK.save('live')
