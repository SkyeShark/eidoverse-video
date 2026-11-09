"""eidoblend.placement: seat things on things, and audit the result (the port of eidoverse/scene_placement.js and
model_kit.js). Guide: tools-guides/placement.md.

    from eidoblend.placement import place_on, snap_to_ground, scatter_on, run_placement_audits
    place_on(crate, terrain)                       # bounds bottom on the highest support under it
    scatter_on(rocks, terrain, rng_seed=7, sink=(0.15, 0.35), tilt_max=0.3)
    seat_on(me, chair)                             # a VRM (eidoblend.characters) sat IN a chair, on its seat pan
    run_placement_audits()                         # what the render harness calls on every build

Blender axes: front = -Y, behind = +Y, left = -X, right = +X, above = +Z, below = -Z.

The runner (eidoblend.harness) imports this family and runs its audits on every build, whether or not a scene
imports it. Collection instances (an Empty instancing a collection, such as a part from harness.assets.load_kit) are
seated, ray-cast and audited through the real geometry they show. check_hovering verifies an object on its recorded
support against the support's real load-bearing surface under its footprint (surface_top_in_footprint: faces within
60 degrees of level; a post or a backrest beside it holds nothing up), not the support's box.
The seating helpers (seating.py) work on the characters family's VRM handles and import that family when called.
"""
from .helpers import (place_on, place_against, place_touching, surface_point, mount_on, snap_to_ground,
                      align_to_surface, scatter_on, find_clear_spot, place_inside, face_toward,
                      station_beside, hinge, support_under_footprint, SIDE_DIR)
from .audits import (check_clipping, check_hovering, check_z_fighting, check_facing, check_density,
                     check_line_intrusion, run_placement_audits, SEATED_GAP)
from .motion import drive_along
from .model_kit import load_kit, Kit
from .seating import (seat_on, sit_on_ground, unseat, emote, face_camera, find_seat_surface, chair_facing,
                      heading_toward, check_seated_facing)
from ._world import clear_cache, tight_box, placed_roots, surface_top_in_footprint, InstanceProxy

__all__ = ['place_on', 'place_against', 'place_touching', 'surface_point', 'mount_on', 'snap_to_ground',
           'align_to_surface', 'scatter_on', 'find_clear_spot', 'place_inside', 'face_toward',
           'station_beside', 'hinge', 'drive_along', 'load_kit', 'Kit', 'check_clipping', 'check_hovering',
           'check_z_fighting', 'check_facing', 'check_density', 'check_line_intrusion', 'run_placement_audits',
           'clear_cache', 'tight_box', 'placed_roots', 'support_under_footprint', 'SIDE_DIR', 'SEATED_GAP',
           'surface_top_in_footprint', 'InstanceProxy', 'seat_on', 'sit_on_ground', 'unseat', 'emote',
           'face_camera', 'find_seat_surface', 'chair_facing', 'heading_toward', 'check_seated_facing']
