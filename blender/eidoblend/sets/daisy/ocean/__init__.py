"""eidoblend.sets.daisy.ocean: the DAISY film's verse 3, the ocean of faces, in Blender 5.2 EEVEE (port of
eidoverse/sets/ocean.js and eidoverse/sets/ocean/*.js). Guide: tools-guides/_drafts/sets-daisy-ocean.md.

    from eidoblend.sets.daisy import ocean
    O = ocean.build({'scene': scene})                      # the set: land, sea, echoes, pages, house, apparitions, lights
    O.key_verse(frame_start=1, vrm=me, camera_obj=cam)     # the whole verse keyed (update, cameras, mark, gestures, springs)

Modules (the WebGPU file each one ports):
    staging      ocean.js          build(ctx) -> the set's dict: mark_at, camera, perform, update, key_verse, wrap_world
    land         ocean/land.js     make_coast (the analytic shore), build_land (mesh, dune grass, her daisies)
    sea          ocean/sea.js      build_sea: the ocean of faces (Geometry Nodes swells + relief, the unlit material)
    faces_atlas  ocean/faces_atlas.js  draw_face_atlas: the 64 brush-line portraits, the same people stroke for stroke
    echoes       ocean/echoes.js   build_echoes: the older voices' lights and their streaks on the water
    pages        ocean/pages.js    build_pages / draw_page: the 2023 and 2026 constitution pages
    house        ocean/house.js    build_house: the cottage on the spit, its window and porch light
    apparitions  ocean/apparitions.js  build_apparitions: the movie robot and the human of light (the film's points)
    perform      ocean/perform.js  make_performer: her gestures (hand to the flower, look at) on the VRM
    daisies      ocean/daisies.js  build: a superbloom on the flora family's daisy (close, pulse, wind, palette);
                                   EXAMPLES['superbloom'] / build_example: daisies.js's own example, 14000 on 60 m
    util         ocean/util.js     rng, clamp01 / smooth / lerp / seg / ease, build_mips, images, fonts, asset roots
"""

from .staging import (BAR, SKY, PARTS, VERSE_SECONDS, build, sky_moon_dir, sky_moon_dir_three, night_world,  # noqa: F401
                      wrap_world, render_settings)
from .land import COAST, make_coast  # noqa: F401
from .sea import SWELLS, FACE, MAIN_T  # noqa: F401
from .faces_atlas import LAYOUT, draw_face_atlas  # noqa: F401

__all__ = ['build', 'BAR', 'SKY', 'PARTS', 'VERSE_SECONDS', 'sky_moon_dir', 'sky_moon_dir_three', 'night_world',
           'wrap_world', 'render_settings', 'make_coast', 'COAST', 'SWELLS', 'FACE', 'MAIN_T', 'LAYOUT',
           'draw_face_atlas']
