"""The film-scale probe scenes (render_heroes.py), shared by the CPU step that generates them and the Blender step
that renders them, so generation never holds the GPU slot.

    python blender/tests/terrain_ekigar/hero_scenes.py        # generates out/heroes/cache/<name>.npz (plain Python)
"""
import os
import sys
import time

# (name, how to build, resolution, world metres, vertical scale, camera, look-at, sun azimuth, sun elevation, copies)
SCENES = [
    ('tile_strip_mountainRange_phacelle', ('chain', [('mountainRange', {'style': 'eroded', 'frequency': 3}),
                                                     ('phacelle', {'strength': 0.3})]), 384, 600, 0.3,
     (0, -1100, 520), (0, 0, 40), 210, 18, 3),
    ('tile_strip_default_project', ('default', None), 256, 400, 1.5, (0, -700, 300), (0, 0, 0), 200, 20, 3),
    ('hero_mountainRange_alpine', ('op', 'mountainRange', {'style': 'alpine', 'relief': 0.7}), 1024, 4000, 0.3,
     (-2600, -2900, 1500), (300, 300, 300), 215, 14, 1),
    ('hero_volcano', ('op', 'volcano', {'scale': 0.6, 'erosion': 0.6}), 1024, 3000, 0.3,
     (-1700, -2200, 900), (0, 0, 250), 230, 16, 1),
    ('hero_canyon', ('op', 'canyon', {'scale': 0.25, 'direction': 0}), 1024, 2000, 0.3,
     (-200, -900, 260), (100, 300, 40), 160, 20, 1),
    ('hero_caldera', ('op', 'caldera', {'radius': 0.3, 'terraces': 4, 'domeRadius': 0.25}), 1024, 3000, 0.3,
     (-1600, -1900, 1100), (0, 0, 100), 230, 18, 1),
    ('hero_duneField_star', ('op', 'duneField', {'type': 'star', 'frequency': 4, 'height': 0.18}), 1024, 3000, 0.3,
     (-1000, -1500, 420), (200, 200, 0), 250, 12, 1),
    ('hero_duneField_barchan', ('op', 'duneField', {'type': 'barchan', 'frequency': 6, 'height': 0.12}), 1024, 1500,
     0.3, (-500, -700, 160), (100, 100, 0), 240, 12, 1),
    ('hero_badlands', ('op', 'badlands', {}), 1024, 1500, 0.3, (-500, -800, 300), (100, 100, 40), 200, 16, 1),
    ('hero_glacialTrough', ('op', 'glacialTrough', {'depth': 0.4}), 1024, 3000, 0.3,
     (-1600, -1500, 700), (0, 300, -100), 210, 20, 1),
    ('hero_impactCrater', ('op', 'impactCrater', {'radius': 0.35, 'nRays': 8}), 1024, 3000, 0.3,
     (-1500, -2000, 900), (0, 0, 0), 235, 15, 1),
    ('hero_cinderConeField', ('op', 'cinderConeField', {'frequency': 3, 'radius': 0.12}), 1024, 3000, 0.3,
     (-1300, -1800, 500), (100, 100, 0), 220, 14, 1),
    # a composite the way a film terrain is built: an alpine range, a glacial trough cut through it, erosion, snow
    ('hero_alpine_valley_composite', ('chain', [('mountainRange', {'style': 'alpine', 'relief': 0.8}),
                                                ('glacialTrough', {'depth': 0.25}), ('phacelle', {'strength': 0.2}),
                                                ('snow', {})]), 1024, 4000, 0.3,
     (-1900, -1100, 950), (400, 100, 250), 205, 18, 1),
    ('preview_modes', ('chain', [('volcano', {'scale': 0.55}), ('snow', {'line': 0.55})]), 512, 2000, 0.3,
     (-1500, -1700, 1300), (0, 0, 150), 220, 25, 1),
]


def build(ek, how):
    if how[0] == 'chain':
        g, ids = ek.chain_graph(how[1])
        return g, ids[-1]
    if how[0] == 'default':
        return ek.examples.default_project_graph()
    g, t, _fx = ek.operator_example(how[1], how[2])
    return g, t


def cache_path(out_dir, name):
    return os.path.join(out_dir, 'cache', f'{name}.npz')


if __name__ == '__main__':
    import _ekigar_load
    ek = _ekigar_load.load()
    out = os.path.join(_ekigar_load.OUT, 'heroes')
    os.makedirs(os.path.join(out, 'cache'), exist_ok=True)
    only = sys.argv[1].split(',') if len(sys.argv) > 1 else None
    for name, how, res, world, vs, *_rest in SCENES:
        if only and name not in only:
            continue
        g, t = build(ek, how)
        t0 = time.time()
        hf = ek.generate(g, target=t, resolution=res, world_size=world, vertical_scale=vs, z_base='min')
        hf.save(cache_path(out, name))
        print(f'{name}: {res}^2 in {time.time() - t0:.1f}s, relief {hf.heights_m.max():.0f} m, '
              f'{len(hf.warnings)} warnings', flush=True)
