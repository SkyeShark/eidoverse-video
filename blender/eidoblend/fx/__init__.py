"""eidoblend.fx: the fx family of the Blender 5.2 EEVEE edition, ported from the WebGPU engine's own solvers.

    from eidoblend.fx.fire import create_volume_fire, create_fire_compose, configure_eevee_for_fire  # fluid_grid.js
    from eidoblend.fx.swe import create_water_swe, LIQUID_PRESETS                                   # fluid_swe.js
    from eidoblend.fx.particles import make_particles                                               # particles.js
    from eidoblend.fx.cloth import create_cloth_panel                                               # cloth_sim.js
    from eidoblend.fx.iso_field import make_iso_field                                               # iso_field.js

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

The subpackage imports nothing from other families. Guides: tools-guides/liquids.md, free-surface-water.md,
volume-fire.md, particles-fx.md, sdf-volumes.md, cloth.md, destruction.md (each with its "Not yet ported").
"""

__all__ = ['fire', 'swe', 'particles', 'cloth', 'iso_field']
