"""eidoblend.fx.water3d: eidoverse/fluid_water.js (Eulerian free-surface water) for Blender 5.2 EEVEE.

    from eidoblend.fx.water3d import create_water_sim, DEFAULTS, configure_eevee

The engine's solver, kernel for kernel, as GLSL compute on Blender's `gpu` module (rgba16float 3D textures, the
same dispatch order, the same multigrid, volume sensor and PI controller): Chentanez & Mueller's base method on a
uniform MAC grid. Two measured additions are on by default so falling water keeps falling (Godunov redistancing every
substep, breadth-first velocity extrapolation); ENGINE_SOLVER turns the solver back into the engine's exactly. Each
baked frame the level set's zero contour is meshed (OpenVDB) with the engine's render-side field operations and
written as a PLY with the shading inputs as attributes; Geometry Nodes plays the sequence, so a saved .blend renders
any frame with no Python.

Modules: water (the API), solver (the GPU state and the substep), _kernels (the GLSL), surface (phi -> mesh,
attributes), material (the look). Guide: tools-guides/free-surface-water.md.
"""

from .water import DEFAULTS, ENGINE_SOLVER, WaterSim, Uniforms, configure_eevee, create_water_sim  # noqa: F401
from .material import key_look  # noqa: F401

__all__ = ['create_water_sim', 'WaterSim', 'Uniforms', 'DEFAULTS', 'ENGINE_SOLVER', 'configure_eevee', 'key_look']
