"""eidoblend.fx: the fx family of the Blender 5.2 EEVEE edition, ported from the WebGPU engine's own solvers.

    from eidoblend.fx.fire import create_volume_fire, create_fire_compose, configure_eevee_for_fire  # fluid_grid.js
    from eidoblend.fx.swe import create_water_swe, LIQUID_PRESETS                                   # fluid_swe.js
    from eidoblend.fx.particles import make_particles                                               # particles.js
    from eidoblend.fx.cloth import create_cloth_panel                                               # cloth_sim.js
    from eidoblend.fx.iso_field import make_iso_field                                               # iso_field.js
    from eidoblend.fx.water3d import create_water_sim, configure_eevee, DROP_SOLVER                 # fluid_water.js
    from eidoblend.fx.water_flat import create_water_mesh, create_sky_mesh, create_water_compute    # WaterMesh, SkyMesh, water_compute.js
    from eidoblend.fx.stable_fluids import create_fluid_sim                                         # fluid_sim.js (three-fluid-fx)
    from eidoblend.fx.particle_morph import make_particle_morph, ParticleMorph, ascii_panel         # particle_morph.js (+ ascii_panel.js)
    from eidoblend.fx.particle_targets import target, from_object, from_file, from_image, shapes, graph_colors  # morph targets from anything, in their own colours

Every stateful system has three phases: build (objects, materials, node groups), bake (the engine's kernels,
in the same order, stepped over the shot's frames into per-frame caches: .vdb, OpenEXR data images, .pc2,
.ply) and playback (Blender reads the caches: scrubbing, re-rendering and multi-pass need no replay, and the
.blend needs no Python at render time). Stateless systems (particles) are Geometry Nodes driven by Scene
Time. Coordinates are Blender's (Z-up, metres); the solvers run in three.js's Y-up frame internally so every
kernel reads like its source.

Private helpers: _noise (the engine's noise functions, numpy, parity-tested), _gpu (GLSL compute through
Blender's gpu module), _nodes (an expression layer for shader/geometry node graphs), _util (axes, colours,
caches), _swe_solver (the shallow-water kernels), _look (the engine's three.js ACESFilmic display matched
under the scene's own view through Blender's OCIO config: the fire's look under AgX).

Importing this package imports none of its modules: each loads on first use (fx.water3d, or `from eidoblend.fx import
particle_morph`). The subpackage imports nothing from other families, except particle_targets, which imports
harness.assets and characters (lazily) to load models, VRMs and their clips. Guides: tools-guides/liquids.md,
free-surface-water.md, volume-fire.md, particles-fx.md, sdf-volumes.md, cloth.md, destruction.md (each with its "Not
yet ported").
"""

import importlib

__all__ = ['fire', 'swe', 'particles', 'cloth', 'iso_field', 'water3d', 'water_flat', 'stable_fluids', 'particle_morph',
           'particle_targets']


def __getattr__(name):
    """fx.water3d, fx.particle_morph ...: the modules, imported on first use."""
    if name in __all__:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(__all__))
