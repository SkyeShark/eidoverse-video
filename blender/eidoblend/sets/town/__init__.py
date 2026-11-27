"""eidoblend.sets.town: a concrete-frame town on a street grid, its edge thinning out into the plain. Blender-native (no
WebGPU original). Registered as 'places.town'.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.sets import town
    T = town.build(extent=(840, 300), seed=7)              # an intact town: 4,400 objects, about 10 M placed faces
    T = town.build(extent=(260, 160), things=False)        # a small one (a test, a background)
    T = town.build(damage=True)                            # struck round strikes placed by the seed
    T = town.build(signs=['BAKERY', 'TAILOR', 'my_sign.png'], sign_font='Anton-Regular.ttf')
    sky = town.light(scene, camera)                        # its sun and the sky family's sky; sky.bake(f, f) before a render
    town.eevee(scene)                                      # the EEVEE settings it is lit for
    for name, pos, target, lens in T.views(): ...          # lenses on it (views.py)

build(collection=None, parent=None, seed=7, extent=(840, 300), damage=False, signs=None, sign_font=None,
      yard_trees='auto', things=True, masks=True, air=True, edge=170, ystreets=None, mosque='auto') -> Town
    (group, collection, parts {'buildings', 'dishes', 'trees', 'palms', 'cars', 'poles', 'lamps', 'stalls', 'other',
    'ground', 'streets', 'air'}, strikes, ystreets, xstreets, mosque, paved, extent, seed, stats, views()). Read
    layout.build for every option.

What it is made of:
    layout.py     the plan: streets, blocks and lots, the mosque's square, poles and wires, cars, the edge
    house.py      one building: a concrete frame on a grid of bays, designed, struck (with damage), then built
    kit.py        what stands on a roof, what a room held, what a strike leaves on the ground
    street.py     cars, palms, the built yard tree, dishes, poles, lamps, the mosque, a stall, a child's bicycle
    signs.py      the shop boards, and the words or pictures you give them (none ship)
    materials.py  its materials by name, each a CC0 photograph at real scale with its layers by cause
    masks.py      the per-face masks the materials read, from the geometry
    things.py     CC0 models people leave about (chairs, gas cylinders, jerrycans, drums, tyres, a covered car)
    world.py      its sun, the sky family's sky (or a photo sky by name), the dust in the air, the EEVEE settings
    views.py      lenses on it
    mb.py         the mesh builder every mesh is written with
    cli.py        build, save and shoot from the command line
    cc0_sets.json the CC0 sets it reads, by ID, with their real sizes and measured means

Every material reads the CC0 library (eidoverse/assets/cache/textures, fetched by ID on first use; EIDO_ASSET_CACHE
reads another checkout's, EIDO_NO_FETCH=1 forbids downloads). The town is built in its own metres with every texture
in object space, so it can be carried by an animated parent. Guide: tools-guides/props-and-sets.md ("A town and the
desert round it").
"""
from .layout import Town, build, plan_strikes  # noqa: F401
from .world import air, eevee, light, sun  # noqa: F401

__all__ = ['build', 'Town', 'plan_strikes', 'light', 'sun', 'air', 'eevee']
