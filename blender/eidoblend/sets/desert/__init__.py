"""eidoblend.sets.desert: the desert round a town, out to 32.8 km: a basin floor rising out of the town's plane, a
braided wadi and its tributaries, star dunes, an escarpment with its outliers, inselbergs and ranges drowned in their
own alluvium, tracks going on from the town's, low scrub on the sand it caught. Blender-native (no WebGPU original),
composed from the terrain family's simulations. Registered as 'places.desert'.

It is made by a chain of steps into a work folder (make.py runs them all), the Blender ones and the plain-Python ones
apart (Blender's Python has no scipy or Pillow):

    sources.py  Blender      three eidoblend.terrain recipes (star dunes, mesas and buttes, a fluvial range), their
                             fields kept in <work>/sources/; and the town's footprint and track ends (town_mask)
    land.py     plain Python the land composed from them: three nested rasters and two images of the marks finer than
                             the mesh (<work>/build/land_*.npz, *_marks.png); where each part stands is land.PLAN
    mesh.py     plain Python a crack-free quadtree mesh, dense where the land needs it, and the scrub's places
    look.py     Blender      the collection 'desert' (desert_ground with its masks, desert_scrub) and its one material,
                             which goes on from the town's own ground (eidoblend.sets.town.materials) without a seam
    cli.py      Blender      the Blender steps from the command line; make.py the whole chain (stdlib)

    python blender/eidoblend/sets/desert/make.py --work work/desert [--quality draft] [--town 840x300 | --plain 840x300]
    from eidoblend.sets import desert
    D = desert.build('work/desert')                  # in Blender, from a made work folder: the collection 'desert'

Guide: tools-guides/props-and-sets.md ("A town and the desert round it"); the recipes: tools-guides/terrain-surfaces.md.
"""


def build(work, collection=None, log=print):
    """the collection 'desert' from a work folder the chain has made (look.build) -> look.Desert"""
    from .look import build as _build
    return _build(work, collection, log)


__all__ = ['build']
