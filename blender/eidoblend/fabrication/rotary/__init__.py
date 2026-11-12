"""eidoblend.fabrication.rotary: all-around carving on the G430 XYZ + A assembly in Blender 5.2 EEVEE
(tools-guides/rotary-carving.md). Ports eidoverse/robotics/rotary.js, rotary_path.js, rotary_mesh.js,
rotary_removal.js, rotary_setup.js and rotary_stock.js (MIT), and the examples rotary.scene.js and
rotary_metal.scene.js.

    from eidoblend.characters.robotics import make_robot
    from eidoblend.fabrication.rotary import rotary_carve, sample_rotary
    machine = make_robot('cnc_rotary', primary='#b9c7c8', accent='#235b68')
    job = rotary_carve(machine, sample_rotary, material='wood', duration=28, cache_dir='//rotary_stock_cache')
    job.play()                                   # every frame keyed; the carved stock as a VDB file sequence

Modules (the planner modules compute with numpy alone and need no scene; this package imports a module only
when one of its names is first used, though eidoblend.fabrication itself loads bpy, so run them inside Blender):
    path      rotary_path.js: CENTRE_SEAT, rotary_blank_distance, sample_rotary, rotary_surface(_arrays),
              rotary_program, RotaryPath, sweep_distance
    mesh      rotary_mesh.js: mesh_envelope, rotary_mesh_program
    setup     rotary_setup.js: rotary_fixture_setup
    removal   rotary_removal.js: rotary_removal
    sweeps    rotary_stock.js's indexRotarySweeps (index_rotary_sweeps) and the numpy swept-cutter distances
    stock     rotary_stock.js's createRotaryStock (create_rotary_stock, RotaryStock, StockField; its finish is
              finish_stock with axes='rotary': the WebGPU rotary stock's (z, y, x) grain coordinates)
    carve     rotary.js: rotary_carve, RotaryJob (keyed with each frame's shutter bracketed: shutter_offsets; or at
              its program's events, key_events, with the stock written for a stretch, write_stock)
    examples  examples/robotics/rotary(_metal).scene.js: EXAMPLES['rotary'], EXAMPLES['rotary_metal']
Stock coordinates (Blender axes): X along the rotary axis, Y the blank's width, Z its height; the program's A angle
turns the stock about +X. Shared with the fabrication family: stock_profile, distance_time, finish_stock and
cutting_debris (eidoblend.fabrication.cutting), source_geometry (eidoblend.fabrication.source_geometry), and the
machine controls of the robotics kit (eidoblend.characters.robotics).
"""

import importlib

_EXPORTS = {
    'CENTRE_SEAT': 'path', 'RotaryPath': 'path', 'rotary_blank_distance': 'path', 'rotary_program': 'path',
    'rotary_surface': 'path', 'rotary_surface_arrays': 'path', 'sample_rotary': 'path', 'sweep_distance': 'path',
    'TAU': 'path',
    'mesh_envelope': 'mesh', 'rotary_mesh_program': 'mesh',
    'rotary_fixture_setup': 'setup',
    'rotary_removal': 'removal',
    'index_rotary_sweeps': 'sweeps', 'sweep_distance_np': 'sweeps',
    'create_rotary_stock': 'stock', 'RotaryStock': 'stock', 'StockField': 'stock',
    'rotary_carve': 'carve', 'RotaryJob': 'carve', 'shutter_offsets': 'carve', 'cut_offset': 'carve',
    'EXAMPLES': 'examples',
}
__all__ = sorted(_EXPORTS)


def __getattr__(name):
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value = getattr(importlib.import_module(f'{__name__}.{mod}'), name)
    globals()[name] = value
    return value


def __dir__():
    return __all__
