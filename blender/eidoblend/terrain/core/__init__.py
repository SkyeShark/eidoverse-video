"""eidoblend.terrain.core: the new make_terrain's core (blender/tests/terrain_new/DESIGN.md, sections 2 and 10).

Import the module you need; this file imports nothing, so plain-Python tests load only what they name.

    grid         frames and units (row 0 south, metres / years / degrees), x2 upsampling, box resampling to a
                 reference's pixel, the border ramp, slope and aspect
    levels       Level, plan_levels (context / main / hero windows), select_levels (a stage's `levels`), QUALITY
    fields       Fields: a level's named float32 arrays, and inherit() into a child level
    recipe       Stage, Knob, Recipe (resolve, to_dict / from_dict, describe), register_op / get_op
    expr         the mask expression language of `where` and the surfacing weights
    world_noise  world-space noise in metres (Ekigar's lattice, moved); field specs as data; field_gpu on a level
    compose      world-space shapes, stamp modes, uplift shapes, start surfaces, flatten areas
    gpu          the GLSL compute runner: init, texture / empty / read, kernel (terrain/kernels/<name>.glsl with
                 common.glsl prefixed, cached per source hash), run, PingPong
    twins        the numpy-twin harness: the common.glsl mirrors, the twin registry, parity()
    cache        cache keys and entries under eidoverse/assets/cache/terrain/
    io           heightmaps and masks in and out (PNG16 / R32 with a sidecar), a numpy PNG codec, hillshade
    metrics      the judge's generic numbers (section 10, item 2)

Nothing here imports bpy at module level; gpu.py imports it when init() runs. Tests that load the core without the
rest of the terrain package use blender/tests/terrain_new/core/plain_import.py.
"""
