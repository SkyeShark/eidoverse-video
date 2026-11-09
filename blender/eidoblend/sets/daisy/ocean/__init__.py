"""eidoblend.sets.daisy.ocean: the ocean of faces, a headland at night above a sea made of faces, in Blender 5.2 EEVEE
(port of eidoverse/sets/ocean.js and eidoverse/sets/ocean/*.js). Guide: tools-guides/_drafts/sets-daisy-ocean.md.

    from eidoblend.sets.daisy import ocean
    O = ocean.build({'scene': scene})                # land, grass, daisies, sea, echoes, pages, house, apparitions, lights
    O.update(t, {'reveal': 0.5, 'porch': 0.0})       # any control now (CONTROLS: values; keyed when a frame is given)
    O.animate({'reveal': lambda t: ocean.ease(t, 1.0, 3.5), 'porch_on': 6.0}, frames=(1, 240))   # keyed on your clock
    O.stand(figure, facing='sea')                    # a figure on the rise (the faces are laid out for its eye point)

Modules (the WebGPU file each one ports):
    staging      ocean.js          build(ctx) -> the set: update, animate, state, controls, stand, heading, wrap_world
    land         ocean/land.js     make_coast (the analytic shore), build_land (mesh, dune grass, her daisies)
    sea          ocean/sea.js      build_sea: the ocean of faces (Geometry Nodes swells + relief, the unlit material)
    faces_atlas  ocean/faces_atlas.js  draw_face_atlas: the 64 brush-line portraits, the same people stroke for stroke
    echoes       ocean/echoes.js   build_echoes: the older voices' lights and their streaks on the water
    pages        ocean/pages.js    build_pages / draw_page: the 2023 and 2026 constitution pages
    house        ocean/house.js    build_house: the cottage on the spit; window_level / porch_level switch its lights on
    apparitions  ocean/apparitions.js  build_apparitions: the movie robot and the human of light; robot_envelope /
                                   human_envelope give their rise and fall from any time
    perform      ocean/perform.js  make_performer: her gestures (hand to the flower, look at); key_gestures keys them
    daisies      ocean/daisies.js  build: a superbloom on the flora family's daisy (close, pulse, wind, palette);
                                   EXAMPLES['superbloom'] / build_example: daisies.js's own example, 14000 on 60 m
    util         ocean/util.js     rng, clamp01 / smooth / lerp / seg / ease, build_mips, images, fonts, asset roots
"""

from .staging import (SKY, PARTS, CONTROLS, EVENTS, SEA_LOOK, build, sky_moon_dir, sky_moon_dir_three,  # noqa: F401
                      night_world, wrap_world, render_settings, resolve_controls)
from .util import clamp01, smooth, lerp, seg, ease  # noqa: F401
from .land import COAST, make_coast  # noqa: F401
from .sea import SWELLS, FACE, MAIN_T  # noqa: F401
from .faces_atlas import LAYOUT, draw_face_atlas  # noqa: F401
from .house import window_level, porch_level  # noqa: F401
from .apparitions import robot_envelope, human_envelope, robot_pose, human_pose  # noqa: F401

__all__ = ['build', 'SKY', 'PARTS', 'CONTROLS', 'EVENTS', 'SEA_LOOK', 'sky_moon_dir', 'sky_moon_dir_three',
           'night_world', 'wrap_world', 'render_settings', 'resolve_controls', 'clamp01', 'smooth', 'lerp', 'seg',
           'ease', 'make_coast', 'COAST', 'SWELLS', 'FACE', 'MAIN_T', 'LAYOUT', 'draw_face_atlas', 'window_level',
           'porch_level', 'robot_envelope', 'human_envelope', 'robot_pose', 'human_pose']
