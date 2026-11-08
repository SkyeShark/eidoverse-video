"""Probe: extruded type and title cards in Blender 5.2 EEVEE (eidoblend.media.text3d).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/media/test_text3d.py

- the size conversion: an 'H' at three's size 1 must stand the font's cap height (OS/2) tall, for three fonts;
- centring: the ink box symmetric about the origin;
- hero: EIDO (Audiowide, enamel), VOICE (brushed metal), 1939 (gold), a neon tube word, standing on a plank floor
  with their contact shadows, and a line typing itself on (Geometry Nodes reveal) -> text3d_hero_f040.png
- a title card in front of the camera, mid fade-in and at full -> text3d_title_f008.png, text3d_title_f030.png
"""
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import raster, text3d  # noqa: E402

OUT = S.OUT
sc = S.fresh_scene(frames=(1, 60))

# ---- measures
for fname in ('Audiowide', 'Michroma', 'Anton'):
    h = text3d.create_text_3d('H', font=fname, size=1.0, depth=0.1, bevel=False, name='measure', stand_up=False)
    w, hh, d = text3d.ink_size(h)
    a, b = text3d._ink_box(h)
    m = text3d.font_metrics(str(raster.font_path(fname)))
    want = m['cap_height'] / m['units_per_em']
    print(f'[measure] {fname}: H cap {hh:.4f} m at size 1 (three em), OS/2 cap/em {want:.4f} -> '
          f'{"OK" if abs(hh - want) < 0.01 else "MISMATCH"}; depth {d:.4f} (want 0.1); '
          f'centre ({(a.x + b.x) / 2:+.4f}, {(a.y + b.y) / 2:+.4f}, {(a.z + b.z) / 2:+.4f})')
    bpy.data.objects.remove(h)

# ---- the set: a plank floor, a dark backdrop
S.box(sc, 'floor', (6, 6, 0.04), (0, 1.5, -0.02), S.pbr_material('planks', S.cached('textures', 'Planks039_2k'), 0.6))
S.box(sc, 'backdrop', (6, 0.05, 3), (0, 1.6, 1.5), S.plain_material('backdrop', (0.05, 0.055, 0.06), 0.7))


def stand(obj, x, y):
    """Stand type on the floor: its geometric box bottom at z = 0."""
    w, h, d = text3d.ink_size(obj)
    obj.location = (x, y, h / 2)
    return obj


eido = text3d.create_text_3d('EIDO', font='Audiowide', size=0.4, depth=0.06, bevel_size=0.004, bevel_thickness=0.004,
                             material=text3d.material('enamel', color='#b6d8d5'), name='eido')
stand(eido, -0.35, 0.55)
voice = text3d.create_text_3d('VOICE', font='Michroma', size=0.16, depth=0.03, bevel_size=0.002,
                              bevel_thickness=0.002, material=text3d.material('brushed'), name='voice')
stand(voice, 0.62, 0.25)
year = text3d.create_text_3d('1939', font='Anton', size=0.22, depth=0.035, bevel_size=0.003, bevel_thickness=0.003,
                             material=text3d.material('gold'), name='year')
stand(year, -1.0, 0.05)
year.rotation_euler.z = 0.3
neon = text3d.create_text_3d('live', font='Kalam-Regular', size=0.18, depth=0.012, bevel_size=0.006,
                             bevel_thickness=0.006, material=text3d.material('neon', emission=8.0), name='neon')
neon.location = (0.95, 1.5, 0.42)
typed = text3d.create_text_3d('make_screen(...)', font='Share Tech Mono', size=0.11, depth=0.016, bevel_size=0.0012,
                              bevel_thickness=0.0012, material=text3d.material('plastic', color='#20262c'),
                              name='typed', reveal=(10, 12.0))
stand(typed, -0.15, -0.2)

S.area_light(sc, (-1.6, -1.6, 2.0), (0, 0.4, 0.2), 180.0, size=1.2, color=(1.0, 0.92, 0.82), name='key')
S.area_light(sc, (1.8, 1.2, 1.6), (0, 0.4, 0.2), 120.0, size=0.8, color=(0.7, 0.8, 1.0), name='rim')
cam = S.camera(sc, (0.15, -2.3, 0.75), (0.0, 0.5, 0.2), lens=40)
sc.view_settings.exposure = 0.0
print('[hero] ink sizes', {o.name: tuple(round(v, 3) for v in text3d.ink_size(o)) for o in (eido, voice, year, neon)})
S.render_still(sc, 40, OUT / 'text3d_hero_f040.png')

# ---- a title card over the same shot
title = text3d.make_title_card('CLAUDE COMES HOME', cam, frames=(1, 60), fade=12, font='Michroma', height_frac=0.05,
                               y=0.3, preset='neon', emission=2.0, color='#f4efe2', name='title')
fac = title.data.materials[0].node_tree.nodes['fade'].inputs['Fac']
from eidoblend.media.screens import action_fcurves  # noqa: E402
nt = title.data.materials[0].node_tree
fc = next(c for c in action_fcurves(nt.animation_data.action) if 'fade' in c.data_path)
tops = {}
for f in (4, 8, 30):
    p = S.render_still(sc, f, OUT / f'text3d_title_f{f:03d}.png')
    import numpy as np
    from PIL import Image
    reg = np.asarray(Image.open(p).convert('L').crop((180, 85, 600, 130)))   # the title's band, left of the neon
    vals = np.sort(reg.ravel())
    tops[f] = float(vals[-300:].mean())
    print(f'[title] frame {f}: keyed fade {fc.evaluate(f):.3f}, brightest-300 mean in the title band {tops[f]:.1f}')
print('[text3d] done')
