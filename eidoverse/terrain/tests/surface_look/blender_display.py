"""The Blender review's display transform, measured as a 3D table (PORT_PLAN.md 8.2 row P18): the look package
judges the port's frames through the same view transform as Blender's renders, so a difference on a board is the
ground's, not the tone curve's.

    EIDO_BLENDER_EDITION=<a checkout of the blender branch> bash <its run_blender.sh> \\
        eidoverse/terrain/tests/surface_look/blender_display.py -- [--n 97] [--lo -14] [--hi 12]
    (a Blender job: run it behind $EIDO_GPU_WRAP like every Blender run; it renders nothing)

The review's frames (blender/tests/terrain/surfacing/review_views.py: render_references.new_scene with
surfacing_judge/shots.EXPOSURE) are scene-linear Rec.709 light through Blender's colour management: the AgX view
transform, the look render_references.LOOK, the exposure, the sRGB display. A float image of n^3 scene-linear colours
(each channel on n steps of log2 from lo to hi stops, plus black) is saved with Image.save_render under that scene's
own settings (the same OCIO display processor a render's PNG passes through; dither off, 16 bits), and read back.
tests/surface_look/develop.py interpolates the table (trilinear in log2) on the port's scene-linear frames.

Writes tests/out/surface_look/display/blender_display.npz (lut (n+1, n+1, n+1, 3) display sRGB 0..1, axis: black
then 2^lo..2^hi; the settings) and blender_display.json (the settings and the edition's commit).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TESTS, 'parity'))
import _blender as B  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

OUT = os.path.join(TESTS, 'out', 'surface_look', 'display')


def main():
    a = B.script_args()

    def opt(k, d):
        return type(d)(a[a.index(k) + 1]) if k in a else d
    n, lo, hi = opt('--n', 97), opt('--lo', -14.0), opt('--hi', 12.0)
    root = B.import_blender_terrain()
    tn = os.path.join(root, 'blender', 'tests', 'terrain')
    for p in (os.path.join(tn, 'reference'), tn):
        if p not in sys.path:
            sys.path.insert(0, p)
    import render_references as RR
    from surfacing_judge import shots as SH
    RR.new_scene((SH.W, SH.H), 1, SH.EXPOSURE)          # the review's scene: AgX, its look, the exposure
    sc = bpy.context.scene
    sc.render.dither_intensity = 0.0
    im = sc.render.image_settings
    im.file_format, im.color_mode, im.color_depth = 'PNG', 'RGB', '16'
    axis = np.concatenate([[0.0], 2.0 ** np.linspace(lo, hi, n)])
    m = len(axis)
    # pixel (i, j) of an (m*m) x m image: r = axis[i % m], g = axis[i // m], b = axis[j]; rows are b
    r = np.tile(axis, m)
    g = np.repeat(axis, m)
    rgb = np.empty((m, m * m, 4), np.float32)
    rgb[..., 0] = r[None, :]
    rgb[..., 1] = g[None, :]
    rgb[..., 2] = axis[:, None]
    rgb[..., 3] = 1.0
    img = bpy.data.images.new('eido_display_table', width=m * m, height=m, float_buffer=True, alpha=False)
    img.colorspace_settings.name = 'Linear Rec.709'     # the scene-linear space the review's frames are in
    img.pixels.foreach_set(rgb.ravel())                 # Blender's rows run bottom up: row 0 is b = axis[0]
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, 'blender_display.png')
    img.save_render(png, scene=sc)
    back = bpy.data.images.load(png)
    back.colorspace_settings.name = 'Non-Color'         # its stored code values, not decoded again
    px = np.empty(m * m * m * 4, np.float32)
    back.pixels.foreach_get(px)
    px = px.reshape(m, m * m, 4)[..., :3]
    lut = np.empty((m, m, m, 3), np.float32)            # [b, g, r]
    for jb in range(m):
        lut[jb] = px[jb].reshape(m, m, 3)               # [g, r]
    lut = np.ascontiguousarray(lut.transpose(2, 1, 0, 3))   # [r, g, b]
    vs = sc.view_settings
    info = dict(n=n, lo=lo, hi=hi, view_transform=vs.view_transform, look=vs.look, exposure=vs.exposure,
                gamma=vs.gamma, display=sc.display_settings.display_device, depth=16,
                edition_commit=B.git(root, 'rev-parse', '--short', 'HEAD'), blender=bpy.app.version_string)
    # mid grey through the table, as a check of the reading: (0.18, 0.18, 0.18)
    k = int(np.argmin(np.abs(axis - 0.18)))
    info['grey_at_axis'] = dict(value=float(axis[k]), out=[float(x) for x in lut[k, k, k]])
    np.savez_compressed(os.path.join(OUT, 'blender_display.npz'), lut=lut, axis=axis.astype(np.float64),
                        info=json.dumps(info))
    with open(os.path.join(OUT, 'blender_display.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=1)
    print('[blender_display]', json.dumps(info), flush=True)


try:
    main()
except Exception:                                        # noqa: BLE001 - the job's log says why
    import traceback
    traceback.print_exc()
    os._exit(1)
os._exit(0)
