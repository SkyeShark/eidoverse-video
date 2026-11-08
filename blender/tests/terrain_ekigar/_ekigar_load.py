"""Load eidoblend.terrain.ekigar under plain Python (no bpy) for the numeric tests.

eidoblend/terrain/__init__.py imports bpy (the round-one heightfield and surfaces), so importing the subpackage the
normal way only works inside Blender. The generator itself is plain numpy, so the tests load the package on its own
under the name 'ekigar' (its modules import each other relatively). Inside Blender, import it as usual:

    from eidoblend.terrain import ekigar
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..'))
PKG = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain', 'ekigar')
OUT = os.path.join(HERE, 'out')
# the Ekigar checkout the parity tests run (read only); EKIGAR_ROOT points them at another one
EKIGAR_ROOT = os.environ.get('EKIGAR_ROOT', 'C:/Users/sdn52/OneDrive/Desktop/Ekigar').replace('\\', '/')


def load():
    """The ekigar package: the real eidoblend.terrain.ekigar when bpy is importable, else a standalone copy."""
    try:
        import bpy  # noqa: F401
        if BLENDER_DIR not in sys.path:
            sys.path.insert(0, BLENDER_DIR)
        from eidoblend.terrain import ekigar
        return ekigar
    except ImportError:
        pass
    if 'ekigar' in sys.modules:
        return sys.modules['ekigar']
    spec = importlib.util.spec_from_file_location('ekigar', os.path.join(PKG, '__init__.py'),
                                                  submodule_search_locations=[PKG])
    mod = importlib.util.module_from_spec(spec)
    sys.modules['ekigar'] = mod
    spec.loader.exec_module(mod)
    return mod
