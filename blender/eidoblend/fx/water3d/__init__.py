"""eidoblend.fx.water3d: eidoverse/fluid_water.js (Eulerian free-surface water) for Blender 5.2 EEVEE.

    from eidoblend.fx.water3d import create_water_sim, DEFAULTS, configure_eevee

The engine's solver, kernel for kernel, as GLSL compute on Blender's `gpu` module (rgba16float 3D textures, the
same dispatch order, the same multigrid, volume sensor and PI controller): Chentanez & Mueller's base method on a
uniform MAC grid. The defaults are the engine's solver exactly (ENGINE_SOLVER names them); DROP_SOLVER adds the two
measured changes that keep water dropped onto water falling (Godunov redistancing every substep, breadth-first velocity
extrapolation), which erode thin water and so stay opt-in. Each baked frame the level set's zero contour is meshed
(OpenVDB) with the engine's render-side field operations and written as a PLY with the shading inputs as attributes;
Geometry Nodes plays the sequence, so a saved .blend renders any frame with no Python.

Modules: water (the API), solver (the GPU state and the substep), _kernels (the GLSL), surface (phi -> mesh,
attributes), material (the look). Guide: tools-guides/free-surface-water.md.
"""

from .water import (DEFAULTS, DROP_SOLVER, ENGINE_SOLVER, WaterSim, Uniforms, configure_eevee,  # noqa: F401
                    create_water_sim)
from .material import key_look, set_inside_domain  # noqa: F401

__all__ = ['create_water_sim', 'WaterSim', 'Uniforms', 'DEFAULTS', 'ENGINE_SOLVER', 'DROP_SOLVER', 'configure_eevee',
           'key_look', 'set_inside_domain']
