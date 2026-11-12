"""eidoblend: the Blender 5.2 EEVEE edition of the Eidoverse toolkit.

Each family of systems owns one subpackage. A scene script imports the ones it uses:

    from eidoblend.harness import assets
    from eidoblend import sdf, weather                   # or eidoblend.sdf after `import eidoblend`: loaded on first use

    harness      the runner (eido_blender.py's build and render), ctx, keying, the audits, assets, the post stack
    placement    seat things on things (place_on, scatter_on, seat_on) and the placement audits
    characters   VRM characters: load_vrm, clips, walks, faces; its subpackages controller, emotes, maneuvers, robot,
                 claudesona, robotics
    course       the locomotion courses and their template (terrain_base.js), three-bvh-csg's booleans
    look         cameras, lights, the EEVEE look presets, exposure, the review tools; look.post: the compositor chain
                 and every WebGPU post effect by name
    sky          make_sky: the Earth sky, the ringworld and the shieldworld, clouds, celestial bodies
    weather      rain, wet ground and puddles, lightning, the weather audio (attached to a sky)
    terrain      make_terrain: landforms by process, judged against real elevation data
    flora        createFlora, the vegetation brush: grass, daisies, corn, sunflowers, shrubs
    trees        SeedThree trees and plants (make_seed_tree)
    fx           liquids, fire, particles and the particle morph, cloth, iso fields, free-surface and flat water
    sdf          the SDF engine: solids meshed for EEVEE, volumes as OpenVDB, screens, its vehicles and explosions
    materials    procedural textures and PBR material factories (procedural_materials.js)
    media        screens, type, overlays, subtitles, lyrics, books and the sound side
    fabrication  FDM printing, pocket milling and relief carving; fabrication.rotary: all-around carving
    props        the DAISY props by name: eight historical voice machines and the 1896 tandem
    sets         the DAISY and UNKNOWN FORCE sets, each a free reusable world on its own clock
    xr           a Blender scene exported for a headset browser (WebXR, on the kit)

Importing eidoblend imports nothing: a family loads when it is first imported or reached as an attribute, so
importing one never pulls in another and the families stay independent. The harness
(blender/eidoblend/harness/run_scene.py) puts <repo>/blender on sys.path before it runs a scene; a script run on its
own adds it itself:

    sys.path.insert(0, '<repo>/blender')
"""

import importlib

__version__ = '0.1.0'

FAMILIES = ('harness', 'placement', 'characters', 'course', 'look', 'sky', 'weather', 'terrain', 'flora', 'trees', 'fx',
            'sdf', 'materials', 'media', 'fabrication', 'props', 'sets', 'xr')


def __getattr__(name):
    """eidoblend.sdf, eidoblend.weather ...: each family imported on first access."""
    if name in FAMILIES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(FAMILIES))
