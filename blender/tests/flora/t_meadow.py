"""t_meadow.py: the first-priority probe: green meadow grass with white and Claude-orange daisies, dense at a
person's feet. Builds the scene, checks the evaluated geometry (instances realized, attributes through), renders
probe stills, and saves the .blend (frame-pure: render any frame of it in a fresh Blender).
    bash run_blender.sh blender/tests/flora/t_meadow.py [--no-render] [--shots low,pov,wide] [--frame 1] [--light sun16]
--light sun16: the sky family's 16:30 sun (2.66, warm) over Blender's physical clear sky instead of the test gradient
(the same sun direction); writes meadow_<shot>_sun16_f<frame>.png.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402

t0 = time.time()
sc = S.new_scene()
LIGHT = S.arg('--light', 'test')
if LIGHT == 'sun16':
    sun, to_sun = S.lights(sun_elev_deg=34, sun_az_deg=150, strength=2.66, color=(1.0, 0.869, 0.732), physical=True)
else:
    sun, to_sun = S.lights(sun_elev_deg=34, sun_az_deg=150, strength=4.5, sky_strength=0.7, gradient=True)
TAG = '' if LIGHT == 'test' else '_' + LIGHT
S.ground()
reset_flora_occupancy()
# the guide's MEADOW recipe: fine-habit grass (true shading, the Blender default for blades) under the daisies
fields = [
    create_flora('grass', size=26, seed=3, height=0.42, blades='fine'),
    create_flora('grass', size=18, seed=17, center=(1.5, 3.0), density=0.55, height=0.55, blades='fine'),
    create_flora('daisy', size=13, seed=5, center=(0.4, 2.2), density=0.45, color='white'),
    create_flora('daisy', size=10, seed=29, center=(-1.6, 3.6), density=0.35, color='orange'),
    create_flora('daisy', size=8, seed=41, center=(1.8, 0.8), density=0.3, color={'white': 1, 'orange': 1}),
]
print(f'[meadow] built {len(fields)} strokes in {time.time() - t0:.1f} s')
dg = bpy.context.evaluated_depsgraph_get()
tot = 0
for f in fields:
    ev = f.object.evaluated_get(dg)
    me = ev.to_mesh()
    names = sorted(a.name for a in me.attributes)
    print(f'[meadow] {f.object.name}: {f.count} plants, evaluated {len(me.vertices)} verts '
          f'(expect {f.stats["verts_total"]}), materials {[m.name for m in me.materials]}, attrs {names}')
    tot += len(me.vertices)
    ev.to_mesh_clear()
print(f'[meadow] total evaluated verts {tot}, eval in {time.time() - t0:.1f} s')

SHOTS = {
    # a low third-person look at where a person stands (origin), 2.4 m off
    'low': ((2.3, -1.6, 0.55), (0.0, 1.0, 0.25), 32),
    # standing POV looking down at your own feet
    'pov': ((0.0, -0.35, 1.62), (0.0, 0.9, 0.0), 24),
    # the stand from further, the daisies through the grass
    'wide': ((6.5, -6.0, 1.7), (0.0, 2.0, 0.2), 40),
}
blend = os.path.join(S.OUT, f'meadow{TAG}.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend)
if '--no-render' not in S.args():
    frame = int(S.arg('--frame', '1'))
    for name in (S.arg('--shots', 'low,pov,wide')).split(','):
        loc, tgt, lens = SHOTS[name]
        S.camera(loc, tgt, lens, name='cam_' + name)
        t1 = time.time()
        S.render(os.path.join(S.OUT, f'meadow_{name}{TAG}_f{frame}.png'), frame)
        print(f'[meadow] {name}: {time.time() - t1:.1f} s')
print(f'[meadow] done in {time.time() - t0:.1f} s')
