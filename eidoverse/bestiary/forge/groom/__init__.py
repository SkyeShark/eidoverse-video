"""GROOM: the coat as a species-agnostic generator part (HAIR_STUDY §9: one groom, many emitters; WOLF_PLAN §5).

A coat is a STYLE (data: styles/<name>.json) grown on a BASE (any forge glb). The forge grows strands from a flow field
on the base's own low, and from those strands emits what the runtime draws:

  base.py     the base: skin triangles (the low roots key on), welded topology, skeleton, sockets, chains, maps
  fields.py   the expression language styles write masks and maps in (maps, joint weights, sockets, chains, normals)
  roots.py    STABLE roots: (triangle, barycentrics) from per-triangle hashed slots, never a global draw
  flow.py     the flow field (sources, whorls, parallel-transport smoothing) and its gates
  strands.py  guides, strands and operators as Warp kernels (growth follows the surface)
  groom.py    style + base -> roots, flow, guides, strands, the strand gates; groom.npz
  render.py   review renders (Warp): base, strands, alpha-tested cards
  (cards, atlas tiles, coat maps, LODs, the clip table and the GLB coat writer follow in their own modules)

A second base needs only its own style: nothing here names a species.
"""
import json
import os

STYLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'styles')
REQUIRED = ('name', 'flow', 'length_mm', 'strands', 'clumps')


def load_style(name_or_path):
    """a style dict from styles/<name>.json or a path; checks the required blocks"""
    p = name_or_path if os.path.exists(name_or_path) else os.path.join(STYLES, name_or_path + '.json')
    with open(p, encoding='utf-8') as f:
        st = json.load(f)
    missing = [k for k in REQUIRED if k not in st]
    if missing:
        raise ValueError(f'style {p} lacks {missing}')
    st['_path'] = os.path.abspath(p)
    return st
