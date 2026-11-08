"""Every landform of Ekigar's library (all four waves): standing alone, on a varied terrain, every named mask output and
every enum arm, evaluated by Ekigar's own code and by the port, compared to float tolerance.

    python blender/tests/terrain_ekigar/test_parity_landforms.py [grid] [wave]
"""
import importlib
import sys

import parity_lib as L
from parity_lib import gen, filt


def probes(waves=(1, 2, 3, 4)):
    ek = L._ekigar_load.load()
    ps = []
    for w in waves:
        mod = importlib.import_module(f'{ek.__name__}.landforms_wave{w}')
        lib = getattr(mod, f'WAVE{w}_LANDFORMS')
        for op, o in lib.items():
            ps.append(gen(op))
            ps.append(filt(op, {}, 'on_terrain'))
            for out in o.get('outputs') or []:
                ps.append(gen(op, {}, '', out['name']))
            for k, schema in o['params'].items():
                if schema['type'] == 'enum':
                    for v in schema['values']:
                        if v != schema['default']:
                            ps.append(gen(op, {k: v}, f'{k}_{v}'))
                if schema['type'] == 'bool':
                    ps.append(gen(op, {k: not schema['default']}, f'{k}_flip'))
            # counted landforms: also the scattered (count > 1) path
            if 'count' in o['params']:
                ps.append(gen(op, {'count': 6, 'seed': 17}, 'count6'))
            if 'seed' in o['params']:
                ps.append(gen(op, {'seed': 4242}, 'seed4242'))
    return ps


if __name__ == '__main__':
    grid = int(sys.argv[1]) if len(sys.argv) > 1 else 48
    waves = tuple(int(c) for c in sys.argv[2]) if len(sys.argv) > 2 else (1, 2, 3, 4)
    ok = L.report(L.run(probes(waves), grid=grid, out_dir=None), 'landforms')
    sys.exit(0 if ok else 1)
