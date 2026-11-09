"""eidoblend.sdf.vehicles: the SDF engine's four vehicles, built for EEVEE.

The examples themselves (their GLSL map, shade and baked surface) are registered by eidoblend/sdf/examples_vehicles.py
as EXAMPLES['stylized_modern_sedan'], ['stylized_cyberpunk_sedan'], ['stylized_sci_fi_sleek_car'] and
['stylized_fighter_jet']. This package is what their make() builds with:

    vehicle.py   make_vehicle / VehicleSdf: the mesh, the part materials, the live uniforms, the lamps
    shading.py   the part materials (every shade() pattern per pixel, EEVEE's own reflections)
    badge.py     the badge decal: BADGE_GLYPH_ATLAS, build_badge_decal(text), badge_image(text)
    livery.py    the cyberpunk racing stripes as decal images of stripeMaskFn; eval_glsl(extra, expr, points)
    lamps.py     the real lights: headlights, tail lamps, underglow, afterburners
    parts.py     what each part is made of, the colour parsing, the presets (METAL_PRESETS, ACCENT_PRESETS, camo)

    from eidoblend.sdf import EXAMPLES
    jet = EXAMPLES['stylized_fighter_jet'].make(camo='desert')
    jet.place_on_ground(0.0)
    jet.object.location.z += 1.0                 # the engine's check scene flew it a metre up

Guide: tools-guides/sdf-vehicles.md.
"""

from .parts import (METAL_PRESETS, ACCENT_PRESETS, CAMO_MODES, CAMO_COLORS, DEFAULT_DECAL_TEXT, PARTS, IDS,
                    linear_color, camo_id)
from .badge import (BADGE_GLYPH_ATLAS, build_badge_decal, get_default_badge_decal, decal_texture_array,
                    badge_image)
from .livery import eval_glsl, stripe_masks, stripe_livery_images
from .lamps import LAMPS, add_lamps
from .vehicle import (make_vehicle, VehicleSdf, LiveUniforms, VEHICLE_VOXEL, KIND_OF, make_modern_sedan,
                      make_cyberpunk_sedan, make_sci_fi_sleek_car, make_fighter_jet)


def part_materials(car):
    """The part materials of a VehicleSdf (vehicles/shading.py; imported on use, it needs bpy)."""
    from .shading import part_materials as _pm
    return _pm(car)


VEHICLES = tuple(KIND_OF)
