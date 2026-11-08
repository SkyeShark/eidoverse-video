"""make_seed_tree: SeedThree's procedural trees and plants in a Blender film scene.

A thin bridge over the SeedThree Blender add-on (SeedThree's `blender` branch,
blender/seedthree/): the same species presets, seeds and dials as the SeedThree
web app, grown by the Python port of its generators and rendered with EEVEE
materials. Presets round-trip with the app's Save/Load panel.

    from eidoblend.trees import make_seed_tree
    oak = make_seed_tree(species='whiteOak', seed=1737, location=(0, 0, 0),
                         dials={'crownShape': 2, 'branchAngle': 72, 'trunks': 1})
    oak['stats']['summary']   # heightMeters, widthMeters, lod0Triangles, ...
    oak['preset']             # 'seedthree-preset/1' JSON for the app's Load panel

Design the tree for the shot: pick the species, roll the seed for the individual,
then set its dials (describe() opens them folder by folder):

    print(make_seed_tree.describe())                    # species menu
    print(make_seed_tree.describe('whiteOak'))          # one species, its folders
    print(make_seed_tree.describe('whiteOak', 'shape')) # one folder of dials

Hero trees use LOD0. Many trees are a few grown individuals placed with
make_seed_tree.duplicate(tree, location=..., rotation=...). A far tree line can use
the app's own cheap levels: grow with level='ALL' (or 'AUTO') and billboard=True, then
make_seed_tree.auto_lod(tree) switches LOD0 / LOD1 / LOD2 (baked branch cards) / the
billboard by camera distance, and make_seed_tree.forest_ring(tree) plants the app's
64-tree grove around it. After the sky and sun are final: make_seed_tree.set_sun(sun_lamp)
(the leaf backlight's sun, and the sun the billboards cast-only from) and
make_seed_tree.light_probe(trees) (EEVEE's occluded sky inside the crowns).

The app's scenes: make_seed_tree.demo_scene('joshuaTree', seed=7) builds its whole
demo (biome terrain, sky, rocks, grass / scrub, clouds, haze, grove, soundscape);
make_seed_tree.example('reference_turntable', species='paperBirch') its reference
turntable. make_seed_tree.export_glb(tree, path) writes its .glb (MSFT_lod +
KHR_materials_diffuse_transmission). make_seed_tree.tools() is its asset tooling
(scripts/texture and scripts/audio; run those in system Python).

Source resolution: SEEDTHREE_DIR, then ../SeedThree-blender, ../SeedThree and
./SeedThree next to this checkout (the first that holds blender/seedthree).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..', '..'))
_api = None
_dir = None


def find_seedthree():
    cands = [os.environ.get('SEEDTHREE_DIR'),
             os.path.join(_ROOT, '..', 'SeedThree-blender'),
             os.path.join(_ROOT, '..', 'SeedThree'),
             os.path.join(_ROOT, 'SeedThree')]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'blender', 'seedthree', 'api.py')):
            return os.path.abspath(c)
    raise RuntimeError('[trees] no SeedThree checkout with blender/seedthree found: set SEEDTHREE_DIR '
                       '(git clone -b blender https://github.com/SkyeShark/SeedThree)')


def raw():
    """The seedthree.api module itself."""
    global _api, _dir
    if _api is None:
        _dir = find_seedthree()
        p = os.path.join(_dir, 'blender')
        if p not in sys.path:
            sys.path.insert(0, p)
        from seedthree import api
        _api = api
    return _api


def make_seed_tree(species='whiteOak', seed=1, dials=None, location=(0.0, 0.0, 0.0), rotation=0.0,
                   level='LOD0', lod=None, collection=None, name=None, wind=True, fruit=True,
                   sun_light=None, controls=None, cards=True, billboard=False):
    """Grow one plant into the open scene.

    species   a key from describe() ('whiteOak', 'joshuaTree', ...)
    seed      the individual (1..9999)
    dials     the app's controls: shape dials by key ({'height': 15, 'crownShape': 2}),
              per-level ones as {'paramOverrides': {'downAngle': {1: 70}}}, material
              ones ({'leafColorize': 0xc0d080, 'leafTintAmount': 0.3})
    location  Blender world metres (Z up); the trunk base sinks by the species' plantSink
    rotation  about Z, radians
    level     'LOD0' for hero plants. 'LOD1', 'LOD2' (baked branch cards over the kept twig
              skeleton), with lod={'mobileTarget': True} also 'LOD3' / 'LOD4' (the app's mobile
              card rungs); 'ALL' builds every level (the first visible), 'AUTO' every level
              switched by camera distance (drivers: make_seed_tree.auto_lod).
    lod       LOD options (describe(species, 'lod')), plus the bake settings cardRes (512),
              cardVariants (3), billboardRes (1024)
    cards     bake (or reuse) the branch-card set when a wanted level places cards (renders:
              run through heavy.sh); False keeps the cluster-spray fallback
    billboard also bake the far billboard impostor (level 'BB': two crossed cards)
    sun_light the sun lamp the leaf/frond/spine backlight follows (the JS sunLight). None
              keeps the current binding, or binds the scene's strongest sun lamp.
              The binding is shared by every SeedThree plant in the file.
    -> {'object': root Empty, 'objects': {level: [meshes]}, 'stats', 'preset', 'sun', 'api'}
       stats['boundingBox'] is Z-up in the root's frame; stats['boundingBoxWorld'] is the world box.
    """
    api = raw()
    d = dict(controls or {})
    d.update(dials or {})
    out = api.create_tree(species=species, seed=seed, controls=d, lod=lod, level=level, location=location,
                          rotation_z=rotation, collection=collection, name=name, wind=wind, fruit=fruit,
                          sun_light=sun_light, cards=cards, billboard=billboard)
    out['object']['allow_intersect'] = True   # trees are intentionally overlapping geometry
    out['api'] = api
    return out


def _duplicate(tree, location=None, rotation=None, collection=None, name=None, linked=True):
    """A copy of a grown plant (the dict make_seed_tree returned, or its root Empty):
    a new root with linked part meshes, placed at `location` / `rotation` (about Z)."""
    out = raw().duplicate_tree(tree, location=location, rotation_z=rotation, collection=collection, name=name,
                               linked=linked)
    out['object']['allow_intersect'] = True
    return out


def _describe(species=None, folder=None):
    return raw().describe(species, folder, call='make_seed_tree')


make_seed_tree.describe = _describe
make_seed_tree.list_species = lambda: raw().list_species()
make_seed_tree.get_schema = lambda species: raw().get_schema(species)
make_seed_tree.default_controls = lambda species: raw().default_controls(species)
make_seed_tree.set_wind = lambda strength=None, speed=None: raw().set_wind(strength=strength, speed=speed)
make_seed_tree.set_sun = lambda sun: raw().set_sun(sun)
make_seed_tree.duplicate = _duplicate
make_seed_tree.light_probe = lambda trees, spacing=1.5, margin=0.1, bake=True, name=None, spread=0.5: raw().light_probe(
    trees, spacing=spacing, margin=margin, bake=bake, name=name, spread=spread)
make_seed_tree.to_preset = lambda species, seed=1, dials=None: raw().to_preset(species, seed, dials)
make_seed_tree.from_preset = lambda preset: raw().from_preset(preset)
make_seed_tree.save_preset = lambda path, species, seed=1, dials=None: raw().save_preset(path, species, seed, dials)
make_seed_tree.load_preset = lambda path: raw().load_preset(path)
make_seed_tree.skeleton = lambda species, seed=1, dials=None: raw().skeleton(species, seed, dials)
make_seed_tree.raw = raw


def _forest_ring(tree, count=64, seed=None, near_level='LOD2', billboard=True, billboard_dist=None,
                 height_at=None, meadow_at=None, collection=None, name=None, wind=True):
    """The app's grove around a grown plant (grow it with level='ALL', billboard=True): `count`
    instanced copies, its card LOD2 near the active camera and its billboard beyond
    billboard_dist, each slot swaying with its own phase. height_at(x, y) / meadow_at(x, y)
    place the slots on a terrain (Blender world X/Y)."""
    return raw().make_forest_ring(tree, count=count, seed=seed, near_level=near_level, billboard=billboard,
                                  billboard_dist=billboard_dist, height_at=height_at, meadow_at=meadow_at,
                                  collection=collection, name=name, wind=wind)


make_seed_tree.forest_ring = _forest_ring
make_seed_tree.bake_impostor = lambda tree, size=1024, source_level='LOD0', centered='axis', cast_shadow=True: \
    raw().bake_impostor(tree, size=size, source_level=source_level, centered=centered, cast_shadow=cast_shadow)
make_seed_tree.ensure_cards = lambda species, seed=1, dials=None, lod=None: raw().ensure_branch_cards(
    species, seed, dials, lod)
make_seed_tree.export_glb = lambda tree, path, materials='full', billboard_dist=None, level=None: raw().export_glb(
    tree, path, materials=materials, billboard_dist=billboard_dist, level=level)
make_seed_tree.auto_lod = lambda tree, camera=None, **d: raw().auto_lod(tree, camera, **d)
make_seed_tree.preview_level = lambda tree, which='AUTO', camera=None, **d: raw().preview_level(tree, which, camera, **d)
make_seed_tree.frame_camera = lambda tree, camera=None, elevation_deg=18.0: raw().frame_camera_to_tree(
    tree, camera, elevation_deg=elevation_deg)
make_seed_tree.tree_from_root = lambda root: raw().tree_from_root(root)
make_seed_tree.remove = lambda tree: raw().remove_tree(tree)


def _demo_scene(species='whiteOak', seed=1, dials=None, **kwargs):
    """The app's demo scene around one plant (seedthree.scene.demo.build_demo_scene): the biome
    terrain and sky, rocks, fallen limbs, grass or scrub, clouds, the tree with every level and
    its billboard switched by camera distance, the 64-tree grove, the ring haze, the soundscape
    and the camera framed as the app frames a species. kwargs: sun_az, sun_el, forest_count,
    haze, clouds, decoration, audio, scale_ref, autorotate, frames, wind, resolution, samples."""
    return raw().build_demo_scene(species, seed, controls=dials, **kwargs)


def _example(name, **kwargs):
    """The app's example scenes: 'reference_turntable' (species, seed: the neutral three-probe
    turntable) or 'example_scene' (the white oak film hookup)."""
    return raw().example(name, **kwargs)


def _tools():
    """The seedthree.tools package: the app's scripts/texture and scripts/audio (texture,
    audio, codex submodules; numpy + Pillow, so run them in system Python)."""
    raw()
    import seedthree.tools as tools
    return tools


def _set_billboard_distance(forest, dist):
    """Move a forest ring's near-trees / billboards switch (both of its objects)."""
    raw()
    from seedthree.bl.forest import set_billboard_distance
    return set_billboard_distance(forest, dist)


make_seed_tree.set_backlight = lambda mode: raw().set_backlight(mode)
make_seed_tree.demo_scene = _demo_scene
make_seed_tree.example = _example
make_seed_tree.tools = _tools
make_seed_tree.set_billboard_distance = _set_billboard_distance
