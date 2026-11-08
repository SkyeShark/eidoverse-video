"""The operator gallery's scenes (render_gallery.py), shared by the CPU step that generates them and the Blender step
that renders them, so generation never holds the GPU slot: Ekigar's reference fixture, the default project, and every
operator on the fixture Ekigar's own visual suite judges it on (examples.operator_example), at the suite's field
resolution (256) on a 100 m tile.

    python blender/tests/terrain_ekigar/gallery_scenes.py [op,op,...]   # generates out/gallery/cache/<name>.npz
"""
import os
import sys
import time

WORLD = 100.0                  # metres per tile; the gallery camera's distance scales with it, so any W frames alike


def scenes(ek):
    """[(name, graph, target, fixture)]: 00_reference, 01_default_project, then NN_<op> for every gallery operator."""
    out = [('00_reference', *ek.fixture_graph())]
    g, t = ek.examples.default_project_graph()
    out.append(('01_default_project', g, t, 'fbm under erosion'))
    for k, op in enumerate(ek.gallery_ids()):
        g, t, fx = ek.operator_example(op)
        out.append((f'{k + 2:02d}_{op}', g, t, fx))
    return out


def cache_path(out_dir, name):
    return os.path.join(out_dir, 'cache', f'{name}.npz')


def generate(ek, graph, target, fixture):
    V = ek.GALLERY_VIEW
    hf = ek.generate(graph, target=target, resolution=V['field_resolution'], world_size=WORLD,
                     vertical_scale=V['vertical_scale'], z_base='mid')
    hf.meta['fixture'] = fixture
    hf.meta.pop('graph', None)
    return hf


if __name__ == '__main__':
    import _ekigar_load
    ek = _ekigar_load.load()
    out = os.path.join(_ekigar_load.OUT, 'gallery')
    os.makedirs(os.path.join(out, 'cache'), exist_ok=True)
    only = sys.argv[1].split(',') if len(sys.argv) > 1 else None
    t_all = time.time()
    n = 0
    for name, graph, target, fixture in scenes(ek):
        if only and name.split('_', 1)[1] not in only:
            continue
        t0 = time.time()
        hf = generate(ek, graph, target, fixture)
        hf.meta['generate_s'] = round(time.time() - t0, 2)
        hf.save(cache_path(out, name))
        n += 1
        print(f'{name:28s} {fixture:14s} {time.time() - t0:.1f}s', flush=True)
    print(f'{n} gallery scenes in {time.time() - t_all:.0f}s')
