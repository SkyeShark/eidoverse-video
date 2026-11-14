"""The surfacing judge (SURFACING_DESIGN.md section 6): the terrain's surface and its plants beside the photographs
of each recipe's place, as boards to look at and as numbers that support the look.

    python blender/tests/terrain/surfacing_judge/test_measures.py       # the measures on inputs with known answers
    bash run_blender.sh blender/tests/terrain/surfacing_judge/make_terrains.py
                                                                        # every recipe's terrain of today, saved for
                                                                        # the view check and the tile measures (GPU)
    python blender/tests/terrain/surfacing_judge/check_views.py --sheet # every judge view on its saved terrain:
                                                                        # does the camera see its subject?
    python blender/tests/terrain/surfacing_judge/make_views.py          # the review's cameras checked, the failing
                                                                        # ones moved, views added -> views.json
    bash run_blender.sh blender/tests/terrain/surfacing/review_views.py --recipe canyon --layers --tag <tag>
                                                                        # the renders the boards and frame measures
                                                                        # read, with layer maps (GPU; its doc)
    python blender/tests/terrain/surfacing_judge/states.py freeze <name> --from <tag>
                                                                        # a state kept as it is (a before)
    python blender/tests/terrain/surfacing_judge/baseline.py --state <s> [--audit <folder>]
                                                                        # the measures on a state's renders and saved
                                                                        # terrains -> baseline_<state>.json, .md
    python blender/tests/terrain/surfacing_judge/board.py canyon --before <s> --after <s>
                                                                        # photograph | before | after | layer map,
                                                                        # with 2x crops where a defect would show

Modules (numpy and Pillow; none needs Blender):
    measures      one-material share, height-line index, repetition, within-layer variation, colour against a
                  photograph, seams, plant density and spacing; the targets of section 6
    terrain_data  a saved terrain (cache entry, Terrain.save snapshot, a generator's levels file) with its masks
    layers        a palette's layer weights on a level's masks, composited as the material does; the layer-map
                  render decoded back into weights per pixel; the layers a camera sees without a render
    views         the judge's views (views.json): the review's matched cameras with the fixes, plus an establishing
                  aerial and a low oblique where a recipe had none; the view check, the clay preview and
                  Terrain.viewpoint's rule on a saved terrain; photographs and their ground (photos.json)
    states        where a state's renders, layer maps and records are; frozen states
    plants        the plant spots format (eidoverse-terrain-plants/1) read on its own, density and spacing
    cost          render seconds and compile seconds read from the render records, against section 7's budgets
    board         the board maker
    baseline      every measure on one state, and the audit's numbers measured again

Data: views.json (the views; make_views.py writes it), photos.json (each photograph's ground, marked by eye).
Outputs go to blender/tests/terrain/out/surfacing_judge/ (git-ignored). Every measure is a number that supports a
look at the picture; the boards are what is judged.

To measure the palettes of another commit beside this checkout's (a before and an after), export that commit's
package (git archive <commit> blender/eidoblend | tar -x -C <dir>) and set EIDO_JUDGE_BLENDER_DIR=<dir>/blender: the
judge then reads eidoblend (palettes, masks, the layer colours) from there, and everything else from this checkout.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))                      # blender/tests/terrain
REPO = os.path.normpath(os.path.join(TN, '..', '..', '..'))          # this checkout
BLENDER_DIR = os.path.normpath(os.environ.get('EIDO_JUDGE_BLENDER_DIR') or os.path.join(REPO, 'blender'))
OUT_ROOT = os.path.join(TN, 'out')
OUT = os.path.join(OUT_ROOT, 'surfacing_judge')
RENDERS = os.path.join(OUT_ROOT, 'surfacing', 'review')              # surfacing/review_views.py writes here
if 'eidoblend' not in sys.modules:
    sys.path.insert(0, BLENDER_DIR)
    import eidoblend  # noqa: F401,E402  (imports nothing; from here on the package loads from BLENDER_DIR, whatever
    #                                     other test helpers put on sys.path later)


def terrain_cache_root():
    """The terrain cache's folder (EIDO_TERRAIN_CACHE, or eidoverse/assets/cache/terrain of this checkout)."""
    return os.environ.get('EIDO_TERRAIN_CACHE') or os.path.join(REPO, 'eidoverse', 'assets', 'cache', 'terrain')


def rel(path):
    """A path as text for a report: relative to the checkout when it lies inside it."""
    p = os.path.abspath(str(path))
    try:
        r = os.path.relpath(p, REPO)
    except ValueError:
        return p.replace('\\', '/')
    return (p if r.startswith('..') else r).replace('\\', '/')
