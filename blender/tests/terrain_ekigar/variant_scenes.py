"""Every option arm of every operator as its own scene: each enum value other than the default (mountain and
mountain-range styles and bulks, volcano profiles and surfaces, the seven dune types, the spit modes, the moraine
components, the playa styles, every Combine mode, every Math operation ...) and each bool flipped, on the fixture
Ekigar's suite judges that operator on (examples.operator_example). The defaults are the gallery's.

    python blender/tests/terrain_ekigar/variant_scenes.py [op,op,...]     # generates out/variants/cache/<name>.npz

render_variants.py renders them in Blender (grey clay, the gallery's camera and light); a cache that is missing is
generated there.
"""
import os
import sys
import time

FIELD_RES = 256
WORLD = 100.0


def arms(ek):
    """[(scene name, op, params override)] for every non-default enum value and every flipped bool."""
    out = []
    for op in ek.gallery_ids():
        o = ek.OPERATORS[op]
        for k, s in o['params'].items():
            if s['type'] == 'enum':
                for v in s['values']:
                    if v != s['default']:
                        out.append((f'{op}__{k}_{v}', op, {k: v}))
            elif s['type'] == 'bool':
                out.append((f'{op}__{k}_{str(not s["default"]).lower()}', op, {k: not s['default']}))
    return out + EXTRA


# arms whose default partner hides them: a guyot at the default full subsidence (1) is a flat sea floor (Ekigar's
# own result: the cone subsides to 0 and the drowned reef is switched off), so it is also shown part-subsided
EXTRA = [('reefRing__guyot_true_subsidence_0.4', 'reefRing', {'guyot': True, 'subsidence': 0.4})]


def cache_path(out_dir, name):
    return os.path.join(out_dir, 'cache', f'{name}.npz')


def example(ek, op, params):
    """The scene for one arm: Ekigar's gallery fixture, except Combine, whose gallery wires the same fixture into both
    inputs (so its 24 modes would all blend a field with itself): here its second input is a ridged field, so every
    mode shows what it does."""
    if op != 'combine':
        return ek.operator_example(op, params)
    g = ek.create_graph()
    a = ek.examples.add_base_fixture(g)
    b = ek.add_node(g, 'ridged', {'x': 0, 'y': 2}, dict(ek.default_params('ridged'), frequency=6, amplitude=0.6))
    c = ek.add_node(g, 'combine', {'x': 3, 'y': 0}, dict(ek.default_params('combine'), **params))
    ek.connect(g, {'node': a, 'port': 'out'}, {'node': c, 'port': 'in'}, ek.graph_ports)
    ek.connect(g, {'node': b, 'port': 'out'}, {'node': c, 'port': 'in2'}, ek.graph_ports)
    return g, c, 'detailed-base + ridged'


def generate(ek, op, params):
    g, t, fixture = example(ek, op, params)
    hf = ek.generate(g, target=t, resolution=FIELD_RES, world_size=WORLD,
                     vertical_scale=ek.GALLERY_VIEW['vertical_scale'], z_base='mid')
    hf.meta['fixture'] = fixture
    return hf


if __name__ == '__main__':
    import _ekigar_load
    ek = _ekigar_load.load()
    out = os.path.join(_ekigar_load.OUT, 'variants')
    os.makedirs(os.path.join(out, 'cache'), exist_ok=True)
    only = sys.argv[1].split(',') if len(sys.argv) > 1 else None
    t_all = time.time()
    lst = arms(ek)
    for name, op, params in lst:
        if only and op not in only:
            continue
        t0 = time.time()
        hf = generate(ek, op, params)
        hf.meta.pop('graph', None)
        hf.save(cache_path(out, name))
        st = hf.stats()
        print(f'{name:48s} h {st["min"]:.3f}..{st["max"]:.3f} nonFinite {st["nonFinite"]} {time.time() - t0:.1f}s',
              flush=True)
    print(f'{len(lst)} variants in {time.time() - t_all:.0f}s')
