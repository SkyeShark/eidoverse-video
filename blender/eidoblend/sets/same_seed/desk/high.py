"""eidoblend.sets.same_seed.desk.high: the desk room's build step (Blender), every built part as a high and every Poly
Haven piece placed as it ships: the shell (shell.py), the desk (furniture.py), the computer (computer.py), the guitar
(guitar.py), the person's things (things.py), the Poly Haven pieces (models.py), the books (books.py). In that order:
each group reads what the ones before it added to the namespace (kit.begin()).

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py desk high --dir <out>        -> <out>/desk_high.blend
"""

import os
import time

import bpy

from .. import look as L
from . import books, computer, furniture, guitar, kit, models, shell, things

GROUPS = (('shell', shell), ('desk', furniture), ('computer', computer), ('guitar', guitar), ('things', things), ('models', models),
          ('books', books))


def build(lib=None, parts=()):
    """the room built into a new file (lib: its CC0 library, default its cc0.json; parts: only these groups) -> the
    open-edged parts"""
    lib = lib or L.Library(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cc0.json'))
    ns = kit.begin(lib)
    hs = ns['hs']
    for name, mod in GROUPS:
        if parts and name not in parts:
            continue
        t0, n0 = time.time(), len(hs.REPORT)
        mod.build(ns)
        L.log('desk high', f'{name}: {len(hs.REPORT) - n0} built parts in {time.time() - t0:.1f} s')
    hs.sweep_tmp()
    bpy.data.collections.remove(hs.tmp)
    opened = [r[0] for r in hs.REPORT if r[1]]
    meshes = [o for o in hs.col.all_objects if o.type == 'MESH']
    L.log('desk high', f'{len(hs.REPORT)} built parts, {len(meshes)} meshes in all; open-edged: {opened or "none"}')
    return opened


def main(out_dir):
    build()
    return L.save(os.path.join(out_dir, 'desk_high.blend'))
