"""eidoblend.fabrication: G430 FDM printing, pocket milling and 3-axis relief carving in Blender
(tools-guides/fabrication.md; the WebGPU eidoverse/robotics/fabrication.js and its modules, MIT).

    from eidoblend.characters.robotics import make_robot
    from eidoblend import fabrication as fab
    printer = make_robot('fdm')
    job = fab.print(printer, fab.manufacturing_sample('bracket', as_parts=True), size=.04, duration=18)
    job.play()                                   # keys the scene's frames: the saved .blend plays on its own

Modules (each mirrors its WebGPU file): processes (fabrication.js: slice_geometry, print, pocket_program, mill, carve,
chords, Job), feed_path (FeedPath), filament_path (FilamentPath), cutter_sweep, cutter_nodes, mesh_slices,
polygon_union (the slicer's union), source_geometry, relief, cutting, filament, manufacturing_samples, fab_sim
(FabSim / PrintSim / CNCSim), machine (the G430 controls a job drives), three_geometry (three's primitives, exact),
examples (EXAMPLES: the manufacturing, relief and mesh_fabrication scenes; scenes/*.json run them as films).
The stock-rotating machine is the separate subpackage eidoblend.fabrication.rotary; its names are forwarded here when
it is present.
"""

from .cutter_nodes import cutter_height_node  # noqa: F401
from .cutter_sweep import index_cutter_sweeps, swept_cutter_height, swept_cutter_height_np  # noqa: F401
from .cutting import (STOCK_MATERIALS, cutting_debris, distance_time, finish_stock, sample_removal,  # noqa: F401
                      stock_materials, stock_profile)
from .fab_sim import CNCSim, FabSim, PrintSim  # noqa: F401
from .feed_path import FeedPath  # noqa: F401
from .filament import (PTFETube, bezier_length, bezier_point, create_ptfe_tube, direct_feed_route,  # noqa: F401
                       ensure_filament, install_filament, service_loop)
from .filament_path import FilamentPath  # noqa: F401
from .machine import g430, world_matrix  # noqa: F401
from .manufacturing_samples import SAMPLES, manufacturing_sample  # noqa: F401
from .mesh_slices import mesh_slicer  # noqa: F401
from .processes import Job, carve, chords, mill, pocket_program, print, slice_geometry, validate_machine  # noqa: F401,A004
from .relief import relief_from_mesh, relief_program, sample_relief  # noqa: F401
from .source_geometry import SourceGeometry, fit_source_geometry, source_geometry  # noqa: F401
from .filament import register_with_kit as _register_with_kit

_register_with_kit()            # robots loaded from now on get their live filament at load (the kit's INSTALLERS hook)


def __getattr__(name):
    """rotary_carve, rotary_program, rotary_mesh_program, sample_rotary, rotary_surface: fabrication.js re-exports
    them from rotary.js; here they come from eidoblend.fabrication.rotary (its own step), on first use."""
    if name in ('rotary_carve', 'rotary_program', 'rotary_mesh_program', 'sample_rotary', 'rotary_surface'):
        from . import rotary
        return getattr(rotary, name)
    raise AttributeError(name)
