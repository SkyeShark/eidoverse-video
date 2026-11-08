"""t_backlit.py: the two lookdev switches for plants against the sun (verifier, 11-07), as A/Bs:
- energy: hero white and orange daisies in a clear spot, facing the camera, back-lit and front-lit, with the
  Translucent lobe added to the full diffuse (nodes.TRANSL_ENERGY None, the default) and with the strict budget
  ('normalize': reflection + transmission <= 0.95). Also back-lit under the sky family's 16:30 sun numbers over
  Blender's physical sky. Writes out/backlit_hero_<light>_<energy>.png and out/backlit_hero_sheet.png.
- specular facing fade (nodes.SPEC_FACING, default on): backlit sunflower heads, whose light-gather normals face away
  from the camera on the petals' backs, with the fade off (white specks on the petal and bract edges) and on, and
  the fade with the strict energy. Writes out/backlit_sunflower_<tag>.png and out/backlit_sunflower_crops.png (the
  heads, 1:1).
    bash run_blender.sh blender/tests/flora/t_backlit.py [--no-render]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402
from eidoblend.flora import nodes as N  # noqa: E402

SUN16 = dict(strength=2.66, color=(1.0, 0.869, 0.732), physical=True)
defaults = (N.TRANSL_ENERGY, N.SPEC_FACING)


def relight(az, el=34.0, **kw):
    for ob in list(bpy.data.objects):
        if ob.type == 'LIGHT':
            bpy.data.objects.remove(ob)
    return S.lights(sun_elev_deg=el, sun_az_deg=az, **kw)


def sheet(paths, cols, out, crop=None):
    """a contact sheet of PNGs (optionally each cropped to x0, y0, x1, y1 in top-down pixels), via bpy images"""
    tiles = []
    for p in paths:
        im = bpy.data.images.load(p)
        w, h = im.size
        px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[::-1]           # top row first
        bpy.data.images.remove(im)
        if crop:
            x0, y0, x1, y1 = crop
            px = px[y0:y1, x0:x1]
        else:
            px = px[::2, ::2]
        tiles.append(px)
    th, tw = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    sh = np.zeros((rows * th, cols * tw, 4), np.float32)
    sh[..., 3] = 1
    for i, t in enumerate(tiles):
        r, c = i // cols, i % cols
        sh[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    img = bpy.data.images.new('sheet', cols * tw, rows * th)
    img.pixels.foreach_set(sh[::-1].ravel())
    img.filepath_raw = out
    img.file_format = 'PNG'
    img.save()
    print(f'[backlit] wrote {out}', flush=True)


# ── energy: hero daisies ──
S.new_scene()
S.ground()
cam = (0.62, 0.24, 0.47)
hero = []
for energy in (None, 'normalize'):
    N.TRANSL_ENERGY = energy
    reset_flora_occupancy()
    fs = [create_flora('grass', size=14, seed=3, height=0.42, blades='fine',
                       clip_fn=lambda x, y: x * x + (y - 0.6) ** 2 < 1.1 ** 2),
          create_flora('daisy', placements=[(0.0, 0.62, 1.15)], seed=77, color='white', heading={'toward': cam}),
          create_flora('daisy', placements=[(0.12, 0.9, 1.1)], seed=78, color='orange', heading={'toward': cam}),
          create_flora('daisy', placements=[(-0.2, 0.75, 1.0)], seed=79, color='white', heading={'toward': cam})]
    S.camera(cam, (0.0, 0.7, 0.45), 45, name='cam_hero')
    tag = 'add' if energy is None else energy
    for light, az, kw in (('back', 150.0, dict(strength=4.5, sky_strength=0.7, gradient=True)),
                          ('front', -30.0, dict(strength=4.5, sky_strength=0.7, gradient=True)),
                          ('back_sun16', 150.0, SUN16)):
        relight(az, **kw)
        p = os.path.join(S.OUT, f'backlit_hero_{light}_{tag}.png')
        S.render(p, 1)
        hero.append(p)
    for f in fs:
        f.remove()

# ── specular facing fade: backlit sunflower heads ──
S.new_scene()
S.ground()
S.camera((5.5, -1.6, 1.45), (4.0, 2.5, 1.5), 30, name='cam_sf')
sfp = []
for tag, energy, facing in (('nofade', None, False), ('fade', None, True), ('fade_normalize', 'normalize', True)):
    N.TRANSL_ENERGY, N.SPEC_FACING = energy, facing
    reset_flora_occupancy()
    sun, to_sun = relight(60.0, el=32.0, strength=5.0, sky_strength=0.7, gradient=True)
    f = create_flora('sunflower', width=7, depth=5, center=(4.0, 2.5), seed=3, rows={'spacing': 0.85, 'plant': 0.5},
                     heading=math.atan2(to_sun.y, to_sun.x))
    p = os.path.join(S.OUT, f'backlit_sunflower_{tag}.png')
    S.render(p, 1)
    sfp.append(p)
    f.remove()
N.TRANSL_ENERGY, N.SPEC_FACING = defaults
if '--no-render' not in S.args():
    # rows: add | normalize; columns: back (test light), front (test light), back (16:30 sun, physical sky)
    sheet(hero, 3, os.path.join(S.OUT, 'backlit_hero_sheet.png'))
    sheet(sfp, 3, os.path.join(S.OUT, 'backlit_sunflower_crops.png'), crop=(560, 0, 960, 240))
print('[backlit] done')
