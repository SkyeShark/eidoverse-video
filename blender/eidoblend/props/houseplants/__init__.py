"""eidoblend.props.houseplants: four houseplants and a watering can, each built as it grows, with its look: a rubber
plant (Ficus elastica), a Monstera deliciosa on its coir pole, a corn plant (Dracaena fragrans 'Massangeana'), a pot of
sweet basil, and a watering can. They were made for the SAME SEED film's lab and kitchen (eidoblend.sets.same_seed),
which build them in place; here each is a prop of its own.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props import houseplants
    houseplants.SPECIES                                   # ('rubber_plant', 'monstera', 'corn_plant', 'basil', 'watering_can')
    plant = houseplants.build('monstera', location=(1.0, 2.0, 0.0), ctx=ctx)    # metres; its root Empty: plant.group
    plant.parts                                           # its meshes, each with its material
    group = houseplants.build_group([('rubber_plant', (-0.7, 0, 0)), ('monstera', (0, 0, 0)), ('corn_plant', (0.7, 0, 0))])
    plant.dispose()

build() makes the plant at the root's origin in a collection of its own (`<species>` under the scene's), parents its parts
to a root Empty set at `location` (metres) and turned by `rotation_z`, and gives it its look (look=False leaves it in
clay). A plant faces -y. build_group() grows several in one Garden, so each one's blades clear the others' (the lab's
three stand that way). The leaves are thin closed solids carrying their own data (leafdata, leafq) for their material;
nothing moves (no wind). Sizes, measured: the rubber plant 1.6 m tall in a 0.32 m pot, the Monstera 1.2 m on its pole in
a 0.3 m pot, the corn plant 1.85 m in a 0.4 m planter, the basil 0.25 m in a 9 cm pot, the watering can 0.41 m long and
0.26 m high. Known fault: a few blade edges of the rubber plant's leaves are open (as in the lab), so its leaves are not
quite closed solids.

Modules: kit (what grows and what is moulded: leaves as thin solids, limbs, soil, ties), plants (the rubber plant, the
Monstera, the corn plant, the watering can; the Garden), basil, look (their materials), cc0.json (the CC0 sets they
read). Guide: tools-guides/props-and-sets.md, "The houseplants".
"""

from __future__ import annotations

import importlib

SPECIES = ('rubber_plant', 'monstera', 'corn_plant', 'basil', 'watering_can')
MODULES = ('kit', 'plants', 'basil', 'look')


class Plant:
    """A built plant (or group): group (its root Empty), parts (its meshes), collection; dispose() removes them."""

    def __init__(self, name, group, parts, collection):
        self.name, self.group, self.parts, self.collection = name, group, parts, collection

    def dispose(self):
        import bpy
        for o in list(self.parts) + [self.group]:
            if o.name in bpy.data.objects:
                bpy.data.objects.remove(o, do_unlink=True)
        if self.collection.name in bpy.data.collections and not self.collection.objects:
            bpy.data.collections.remove(self.collection)


def build(species, location=(0.0, 0.0, 0.0), rotation_z=0.0, ctx=None, scene=None, look=True, seed=11, name=None):
    """One plant (or the watering can) at `location` (metres), turned by rotation_z (radians). seed: the basil's random
    stream (the other species are fixed by their own tables). -> Plant"""
    return build_group([(species, (0.0, 0.0, 0.0))], location, rotation_z, ctx, scene, look, seed, name or species)


def build_group(items, location=(0.0, 0.0, 0.0), rotation_z=0.0, ctx=None, scene=None, look=True, seed=11, name='houseplants'):
    """Several plants grown together, each at its own (x, y, z) in metres about the group's root: [(species, (x, y,
    z))]; every blade clears what was grown before it. -> Plant (the group)"""
    import random

    import bpy

    from ..hardsurface import masses as hs
    from . import basil as B
    from . import look as LK
    from . import plants as P
    sc = scene or (ctx.scene if ctx is not None and getattr(ctx, 'scene', None) is not None else bpy.context.scene)
    before = set(bpy.data.objects)
    hs.start(name, orient=False, scene=sc)
    clay = bpy.data.materials.get('houseplant_clay') or hs.mat('houseplant_clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    g = P.Garden()
    floors = []                                                  # (the objects each item made, the floor it stands on, mm)
    for sp, at in items:
        x, y, z = (v * 1000.0 for v in at)
        made_before = set(bpy.data.objects)
        if sp == 'rubber_plant':
            P.rubber_plant(g, x, y, clay, z0=z)
        elif sp == 'monstera':
            P.monstera(g, x, y, clay, z0=z)
        elif sp == 'corn_plant':
            P.corn_plant(g, x, y, clay, z0=z)
        elif sp == 'basil':
            B.build((x, y, z), random.Random(seed), clay)
        elif sp == 'watering_can':
            P.watering_can(x, y, z, clay)
        else:
            raise ValueError(f'houseplants: no species {sp!r} (have: {", ".join(SPECIES)})')
        floors.append((set(bpy.data.objects) - made_before, z))
    hs.sweep_tmp()
    bpy.data.collections.remove(hs.tmp)
    parts = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    root = bpy.data.objects.new(f'{name}_root', None)
    hs.col.objects.link(root)
    for o in parts:
        o.parent = root
    root.location = location
    root.rotation_euler = (0.0, 0.0, rotation_z)
    if look:
        made = {}
        for objs, z in floors:
            LK.apply([o for o in parts if o in objs], z0=z, made=made if z == 0.0 else None)
    return Plant(name, root, parts, hs.col)


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
