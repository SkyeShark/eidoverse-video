"""t_sheen.py: A/B of the grass's specular under a low backlight (the wide meadow shot into the sun, where flat blade
cards mirror the sun across their whole width): roughness multiplier and specular level. Writes
out/sheen_<tag>.png and out/sheen_sheet[_<mode>].png.
    bash run_blender.sh blender/tests/flora/t_sheen.py [--damp | --diag | --rough | --frost]
--frost: the blade roughness default (field.BLADE_ROUGH 1.6) against the WebGPU edition's 1.0 and 1.3, with curl 1.4
and damp on (the defaults), and 1.6 with curl 0.8: gust-bent blades mirrored the sun in white lines at 1.0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402

# (tag, rough multiplier, specular level, translucency, grazing damp[, curl])
VARIANTS = [('flat', 1.0, 0.5, 1.0, False, 0.0), ('curl0.8', 1.0, 0.5, 1.0, True, 0.8),
            ('curl1.4', 1.0, 0.5, 1.0, True, 1.4), ('curl0.8_nodamp', 1.0, 0.5, 1.0, False, 0.8)]
if '--damp' in S.args():      # view-grazing damping alone (no curl)
    VARIANTS = [('nodamp', 1.0, 0.5, 1.0, False, 0.0), ('damp', 1.0, 0.5, 1.0, True, 0.0),
                ('damp_r1.3', 1.3, 0.5, 1.0, True, 0.0), ('spec0', 1.0, 0.0, 1.0, False, 0.0)]
if '--diag' in S.args():      # which lobe makes the white streaks: specular off / translucency off
    VARIANTS = [('r1.0_s0.5', 1.0, 0.5, 1.0, False), ('spec0', 1.0, 0.0, 1.0, False), ('transl0', 1.0, 0.5, 0.0, False),
                ('spec0_transl0', 1.0, 0.0, 0.0, False)]
if '--rough' in S.args():     # roughness and specular level alone (no damping)
    VARIANTS = [('r1.0_s0.5', 1.0, 0.5, 1.0, False), ('r1.4_s0.5', 1.4, 0.5, 1.0, False), ('r1.4_s0.3', 1.4, 0.3, 1.0, False),
                ('r1.7_s0.5', 1.7, 0.5, 1.0, False)]
if '--frost' in S.args():     # the blade roughness default against the WebGPU value (curl 1.4 + damp on)
    VARIANTS = [('frost_r1.0', 1.0, 0.5, 1.0, True, 1.4), ('frost_r1.3', 1.3, 0.5, 1.0, True, 1.4),
                ('frost_r1.6_default', 1.6, 0.5, 1.0, True, 1.4), ('frost_r1.6_curl0.8', 1.6, 0.5, 1.0, True, 0.8)]
MODE = next((m[2:] for m in ('--damp', '--diag', '--rough', '--frost') if m in S.args()), '')
paths = []
for tag, rough, spec, transl, damp, *rest in VARIANTS:
    curl = rest[0] if rest else 0.0
    S.new_scene()
    S.lights(sun_elev_deg=34, sun_az_deg=150, strength=4.5, sky_strength=0.7, gradient=True)
    S.ground()
    reset_flora_occupancy()
    create_flora('grass', size=26, seed=3, height=0.42, blades='fine', rough=rough, specular=spec, translucency=transl,
                 grazing_damp=damp, curl=curl)
    create_flora('grass', size=18, seed=17, center=(1.5, 3.0), density=0.55, height=0.55, blades='fine', rough=rough,
                 specular=spec, translucency=transl, grazing_damp=damp, curl=curl)
    create_flora('daisy', size=13, seed=5, center=(0.4, 2.2), density=0.45, color='white')
    create_flora('daisy', size=10, seed=29, center=(-1.6, 3.6), density=0.35, color='orange')
    S.camera((6.5, -6.0, 1.7), (0.0, 2.0, 0.2), 40)
    p = os.path.join(S.OUT, f'sheen_{tag}.png')
    S.render(p, 1)
    paths.append((tag, p))
if '--no-render' not in S.args():
    import bpy
    import numpy as np
    W, H = 480, 270
    sheet = np.zeros((H * 2, W * 2, 4), np.float32)
    for i, (tag, p) in enumerate(paths):
        im = bpy.data.images.load(p)
        im.scale(W, H)
        px = np.array(im.pixels[:], np.float32).reshape(H, W, 4)
        r, c = 1 - i // 2, i % 2                         # Blender images are bottom-up
        sheet[r * H:(r + 1) * H, c * W:(c + 1) * W] = px
        bpy.data.images.remove(im)
    out = bpy.data.images.new('sheen_sheet', W * 2, H * 2)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = os.path.join(S.OUT, 'sheen_sheet' + ('_' + MODE if MODE else '') + '.png')
    out.file_format = 'PNG'
    out.save()
print('[sheen] done: top-left', VARIANTS[0][0], 'top-right', VARIANTS[1][0], 'bottom-left', VARIANTS[2][0], 'bottom-right', VARIANTS[3][0])
