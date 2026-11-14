"""What a state's renders cost, read from what the render scripts record (system Python; no render):

    from surfacing_judge import cost as C
    C.render_cost(record)            # one view: build, first frame (shader compile included), a frame once compiled
    C.bench(path)                    # the material bench's json (surfacing/bench_material.py): seconds per frame
    C.budget(kind, seconds)          # against SURFACING_DESIGN.md section 7: 'pass' | 'fail' | None

review_views.py records per view build_s, first_render_s, second_render_s (the same frame again: the material
compiled) and, with --time, timing (textured, clay and their difference, material_s). Video memory is not recorded
by the renders; the shared GPU queue's ledger holds what each job held.
"""
from __future__ import annotations

import json
import os

# section 7's budgets, seconds (None: no bound in this direction)
BUDGET = {
    'aerial_frame': 3.0,             # a review frame, 960 x 540, 16 samples, aerial
    'eye_frame': 8.0,                # an eye-level frame with plants
    'material_frame': 2.0,           # the material's own cost per frame on the bench scene
    'far_compile': 10.0,             # the far material's compile
    'near_compile': 120.0,           # never over 120 s cold (and at most 1.5 x the palette's today)
    'material_build': 30.0,          # Python creating the nodes
}


def render_cost(rec, kind=None):
    """dict(build_s, first_s, frame_s, compile_s (first minus a compiled frame: about the shader compile), material_s
    (with --time), nodes, verdict of the frame against its budget) of one record, or {} when it holds none."""
    if not rec or 'first_render_s' not in rec:
        return {}
    frame = rec.get('second_render_s')
    first = rec.get('first_render_s')
    timing = rec.get('timing') or {}
    out = dict(build_s=rec.get('build_s'), first_s=first, frame_s=frame,
               compile_s=(round(first - frame, 1) if first is not None and frame is not None else None),
               material_s=timing.get('material_s'), nodes=rec.get('nodes'))
    if kind in ('eye', 'aerial') and frame is not None:
        out['verdict'] = budget('eye_frame' if kind == 'eye' else 'aerial_frame', frame)
    return out


def budget(kind, seconds):
    lim = BUDGET.get(kind)
    if lim is None or seconds is None:
        return None
    return 'pass' if seconds <= lim else 'fail'


def bench(path):
    """The material bench's numbers: {palette: dict(material_s, ...)} as bench_material.py wrote them, or {}."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)
