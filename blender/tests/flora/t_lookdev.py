"""t_lookdev.py: A/B lookdev of the meadow at a person's feet: shading-normal modes and blade habits under a backlit
and a front-lit TEST sun, same seeds, same low camera. Writes out/look_<variant>_<light>.png and a contact sheet.
    bash run_blender.sh blender/tests/flora/t_lookdev.py [--variants A,B,C,D] [--lights back,front]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402

VARIANTS = {
    'A': {'normals': None, 'blades': None},          # parity: light-gather (up) normals, upstream blade habit
    'B': {'normals': 'true', 'blades': None},
    'C': {'normals': 'true', 'blades': 'fine'},
    'D': {'normals': 0.4, 'blades': 'fine'},
    'E': {'normals': None, 'blades': 'fine'},
}
LIGHTS = {'back': 150.0, 'front': -40.0}     # sun azimuth (deg); the camera looks toward about 130 deg

out = []
for light in S.arg('--lights', 'back,front').split(','):
    for v in S.arg('--variants', 'A,C,E').split(','):
        cfg = VARIANTS[v]
        S.new_scene()
        S.lights(sun_elev_deg=30, sun_az_deg=LIGHTS[light], strength=4.5, sky_strength=float(S.arg('--sky', '0.7')),
                 gradient=True)
        S.ground()
        reset_flora_occupancy()
        create_flora('grass', size=12, seed=3, height=0.42, normals=cfg['normals'], blades=cfg['blades'])
        create_flora('daisy', size=7, seed=5, center=(0.2, 1.4), density=0.45, color='white')
        create_flora('daisy', size=6, seed=29, center=(-1.0, 2.2), density=0.35, color='orange')
        S.camera((1.9, -1.3, 0.5), (0.0, 1.0, 0.22), 30)
        p = os.path.join(S.OUT, f'look_{v}_{light}.png')
        S.render(p, 1)
        out.append(p)
print('[lookdev] wrote', len(out))
