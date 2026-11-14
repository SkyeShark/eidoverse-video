"""The Blender judge on a saved terrain, numbers only (PORT_PLAN.md 6.3): one judge for both editions, so a
difference in a number is a difference in the ground. tests/judge/judge.mjs runs this with Blender's own Python.

    <Blender's python> -I eidoverse/terrain/tests/judge/judge_field.py --field <save> [--field <save> ...]
        (--reference <name> | --recipe <recipe>) [--no-source-chain] --out <verdicts.json>

    --field      a Terrain.save (<path>.npz with its .json: the port's or Blender's; the main level is judged), or
                 an .npz of a heightfield (h, cell, ...) as judge/run.py --field takes; repeatable
    --reference  a reference of blender/tests/terrain/reference/data (mount_fuji ...)
    --recipe     the recipe the terrain was made by: its first reference in judge/refs.RECIPE_REFERENCES, and for
                 real_place its dem and no source chain (its field is the reference's own data), as judge/run.py
    --out        the verdicts: a list of judging.Verdict.to_dict() (every number, band and verdict), as
                 judge/run.py writes verdicts.json, with the versions that made it

It calls judge.judging.judge exactly as judge/run.py does for a field (its numbers and bands), and nothing else of
run.py: no renders and no sheet, which need Blender and Pillow (run.py imports its sheet module, so it does not start
in Blender's bundled Python, which has no Pillow). The one case the judge cannot take as it is, a lake mask on a
terrain coarser than a softened reference's pixel, goes through tests/parity/_blender.py judge_dict (the verdict
then says so in 'judge_note').
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
import _blender as B  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--field', action='append', default=[])
    ap.add_argument('--reference')
    ap.add_argument('--recipe')
    ap.add_argument('--label', action='append', default=[])
    ap.add_argument('--no-source-chain', action='store_true')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(B.script_args())
    if not a.field:
        ap.error('give --field')
    edition = B.bare_terrain_package()
    source_chain = not a.no_source_chain
    ref_name = a.reference
    if a.recipe:
        r, _size, _params, chain = B.reference_for(a.recipe)
        ref_name = ref_name or r
        source_chain = source_chain and chain
    if not ref_name:
        ap.error('--reference is needed (no default reference for this recipe)')
    verdicts = []
    for i, f in enumerate(a.field):
        path = os.path.abspath(f)
        base = os.path.splitext(path)[0]
        label = a.label[i] if i < len(a.label) else os.path.basename(base)
        v = B.judge_dict(base if os.path.exists(base + '.json') else path, ref_name, label=label,
                         source_chain=source_chain)
        v['field'] = path
        v['source_chain'] = source_chain
        verdicts.append(v)
        judged = [r for r in v['rows'] if r['passed'] is not None]
        print(f"[judge] {label} vs {ref_name}: {'PASS' if v['passed'] else 'FAIL'} "
              f"({sum(1 for r in judged if r['passed'])}/{len(judged)} bands)", flush=True)
    B.write_json(a.out, dict(verdicts=verdicts, reference=ref_name, versions=B.versions(),
                             key=B.source_key(edition)))


if __name__ == '__main__':
    main()
