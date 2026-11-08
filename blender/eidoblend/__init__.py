"""eidoblend: the Blender 5.2 EEVEE edition of the Eidoverse toolkit.

Each family of systems owns one subpackage (eidoblend.harness, and the sky, terrain, vegetation, characters ...
families' own). A scene script imports the ones it uses:

    from eidoblend.harness import assets

This file imports nothing, so importing one subpackage never pulls in another and the families stay independent.
The harness (blender/eidoblend/harness/run_scene.py) puts <repo>/blender on sys.path before it runs a scene; a script
run on its own adds it itself:

    sys.path.insert(0, '<repo>/blender')
"""

__version__ = '0.1.0'
