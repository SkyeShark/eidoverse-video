"""eidoblend.sdf: the SDF engine (eidoverse/sdf_raymarch_loader.js) for Blender 5.2 EEVEE.

The engine raymarched each SDF per pixel inside a proxy box. Here an SDF becomes real scene content: a solid is
its GLSL map() evaluated on the GPU and dual-contoured into a quad mesh, with its surface() baked to textures; a
volume is its sample() / medium() evaluated into OpenVDB grids played by a Volume object; a screen is the SDF
raymarched into an image (make_sdf_texture, make_explosion_texture). Guides: tools-guides/sdf-volumes.md,
tools-guides/sdf-explosions.md.

    from eidoblend.sdf import create_sdf_object, create_sdf_volume, make_sdf_texture, EXAMPLES, SDF_NP
    from eidoblend.sdf import light_from_emission, fit_volume_range, nuclear_explosion   # the volumes' tools

The examples_<family>.py files (solids, vehicles, volumes) register their EXAMPLES on import; the vehicles' builders
are the subpackage eidoblend.sdf.vehicles (tools-guides/sdf-vehicles.md), the mushroom cloud is nuclear_explosion
(NuclearExplosionFX, and look.post's registry effect 'nuclear_explosion').
"""

from .glsl_lib import SDF_PRIMITIVES
from .np_lib import SDF_NP
from .spec import QUALITY_PRESETS, EXAMPLES, SdfSpec, SdfExample, register_example, sdf_collection
from .gpu_eval import SdfProgram
from .mesher import dual_contour
from .solid import create_sdf_object, SdfObject, three_to_blender
from .volume import create_sdf_volume, SdfVolume, SdfVolumeSpec, volume_render_settings, VOLUME_QUALITY
from .texture import (make_sdf_texture, SdfTexture, SDF_TEX_RECIPES, make_explosion_texture, ExplosionTexture,
                      EXPLOSION_FRAGMENT_SHADER)
from .helper import register_sdf_helper, help  # noqa: A004 - the engine's name
from .rhombic_dodecahedron import (create_rhombic_dodecahedron, fill_volume_rd, fill_sphere_rd, voxelize_mesh_rd,
                                   RdVoxels)

# the engine's name for its primitive library object; in Python it is the numpy mirror
SDF_TSL = SDF_NP

# examples_<family>.py files that failed to import: {module name: traceback}
EXAMPLE_IMPORT_ERRORS = {}


def _register_examples():
    """Import every examples_*.py of this package (solids, vehicles, volumes ...): each registers its EXAMPLES
    with register_example, so a new family's file needs no edit here. A family file that fails to import is
    reported loudly with its traceback (its examples are then missing from EXAMPLES, and listed in
    EXAMPLE_IMPORT_ERRORS) and the engine still loads."""
    import importlib
    import pkgutil
    import traceback
    for name in sorted(m.name for m in pkgutil.iter_modules(__path__) if m.name.startswith('examples_')):
        try:
            importlib.import_module('.' + name, __name__)
        except Exception:  # noqa: BLE001 - one family's broken file must not take the engine down
            EXAMPLE_IMPORT_ERRORS[name] = traceback.format_exc()
            print(f'[sdf] WARNING: {name}.py did not load; its EXAMPLES are missing:\n{EXAMPLE_IMPORT_ERRORS[name]}',
                  flush=True)


_register_examples()

# the volumes family's tools (examples_volumes.py: the lamps from emission, the froxel range, the stills) and the
# mushroom cloud; left out (with the warning above) when examples_volumes.py did not load
if 'examples_volumes' not in EXAMPLE_IMPORT_ERRORS:
    from .examples_volumes import (light_from_emission, light_from_surface, fit_volume_range, build_still,  # noqa: E402
                                   escape_transmittance, escape_fraction, emission_stats, EmissionLights, LiveUniforms,
                                   GRID_BOUNDS, LIGHT_COUNT, VOLUME_EXAMPLES)
    from . import nuclear_explosion  # noqa: E402
    from .nuclear_explosion import NuclearExplosionFX  # noqa: E402
