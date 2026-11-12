"""Load the new terrain core without the rest of the terrain package, in plain Python or in Blender.

eidoblend/terrain/__init__.py imports bpy (the old make_terrain, surface_layers), and while the packages are being
built it may import modules that are half-written. The core needs neither: install() puts a bare package object in
sys.modules for `eidoblend.terrain` (its __path__ is the real folder), so

    import plain_import; plain_import.install()
    from eidoblend.terrain.core import twins, levels, metrics       # numpy only

imports exactly the modules named, in system Python (numpy) or in Blender. Other packages' plain-Python tests can
use it the same way:

    sys.path.insert(0, '<worktree>/blender/tests/terrain/core'); import plain_import; plain_import.install()
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
BLENDER_DIR = os.path.join(WORKTREE, 'blender')
TERRAIN_DIR = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain')
OUT = os.path.join(WORKTREE, 'blender', 'tests', 'terrain', 'out', 'core')
REFERENCE_DIR = os.path.join(WORKTREE, 'blender', 'tests', 'terrain', 'reference')


def install():
    """Make `eidoblend.terrain.core` importable without running eidoblend/terrain/__init__.py. Idempotent; if the
    real package is already imported (a scene loaded it), that one is kept."""
    if BLENDER_DIR not in sys.path:
        sys.path.insert(0, BLENDER_DIR)
    import eidoblend                                         # imports nothing (its own docstring says so)
    name = 'eidoblend.terrain'
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = [TERRAIN_DIR]
        pkg.__package__ = name
        pkg.__file__ = os.path.join(TERRAIN_DIR, '__init__.py')
        sys.modules[name] = pkg
        eidoblend.terrain = pkg
    os.makedirs(OUT, exist_ok=True)
    return OUT


def script_args():
    """Arguments after Blender's `--` (or after the script in plain Python)."""
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else a[1:]
