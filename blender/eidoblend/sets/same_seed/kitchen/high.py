"""eidoblend.sets.same_seed.kitchen.high: the kitchen's build step (Blender), every part as built (the highs): the shell
(shell.py), the cupboards with the worktop, sink, dishwasher, cooker and hood (cabinets.py), the refrigerator
(fridge.py), the table and its four chairs (table.py), and the things: the homework, the school bag, what stands on the
worktop and the sill, the basil (eidoblend.props.houseplants.basil) (things.py). In that order: each group reads what
the ones before it added to the namespace (kit.begin()).

    bash run_blender.sh blender/eidoblend/sets/same_seed/cli.py kitchen high --dir <out>     -> <out>/kitchen_high.blend
"""

import os
import time

import bpy

from .. import look as L
from . import cabinets, fridge, kit, shell, table, things

GROUPS = (('shell', shell), ('cabinets', cabinets), ('fridge', fridge), ('table', table), ('things', things))


def build(parts=()):
    """the room built into a new file (parts: only these groups, for a quick look at one) -> the open-edged parts"""
    ns = kit.begin()
    hs = ns['hs']
    for name, mod in GROUPS:
        if parts and name not in parts:
            continue
        t0, n0 = time.time(), len(hs.REPORT)
        mod.build(ns)
        L.log('kitchen high', f'{name}: {len(hs.REPORT) - n0} parts in {time.time() - t0:.1f} s')
    hs.sweep_tmp()
    bpy.data.collections.remove(hs.tmp)
    opened = [r[0] for r in hs.REPORT if r[1]]
    L.log('kitchen high', f'{len(hs.col.objects)} parts, {sum(r[3] for r in hs.REPORT)} faces as built; open-edged: {opened or "none"}')
    return opened


def main(out_dir):
    build()
    return L.save(os.path.join(out_dir, 'kitchen_high.blend'))
