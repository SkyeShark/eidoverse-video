"""eidoblend.fabrication.cutter_nodes: the Geometry Nodes counterpart of the analytic vertical cutter-envelope
intersection (cutter_nodes.js, MIT; cutter_sweep.swept_cutter_height is the same function in Python).

    group = cutter_height_node(radius, kind)    # a node group 'eido.cutter_height.<kind>.<radius>':
                                                #   inputs XY (vector, z ignored), A, B (vectors, Blender (x, y, height))
                                                #   output Height: the swept envelope above XY, 1e6 where it never covers

The stock's nodes call it once per candidate sweep. As in the TSL, the radial distance comes from a 2D cross product
(no cancellation near a tangent), a ball nose is minimised along the full 3D centre trajectory, and a flat end takes
the entry (rising move) or exit (falling move) of its footprint.
"""

from __future__ import annotations

import bpy

from ._nodes import Builder, new_tree


def cutter_height_node(radius, kind):
    name = f'eido.cutter_height.{kind}.{radius:.6g}'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, inputs=[('XY', 'NodeSocketVector'), ('A', 'NodeSocketVector'), ('B', 'NodeSocketVector')],
                            outputs=[('Height', 'NodeSocketFloat')])
    b = Builder(tree)
    x, y, _ = b.sep(gi.outputs['XY'])
    ax, ay, az = b.sep(gi.outputs['A'])
    bx, by, bz = b.sep(gi.outputs['B'])
    qx, qy = x - ax, y - ay
    vx, vy = bx - ax, by - ay
    dy = bz - az
    h2 = vx * vx + vy * vy
    r2 = radius * radius
    ball = kind == 'ball'
    # a vertical move: the footprint disc at its lower end
    d2 = qx * qx + qy * qy
    point = b.min(az, bz) + ((radius - b.sqrt(b.max(r2 - d2, 0.0))) if ball else 0.0)
    point = b.switch(b.le(d2, r2), 1e6, point)
    # a move with XY travel
    hh = b.sqrt(b.max(h2, 1e-30))
    projected = (qx * vx + qy * vy) / hh
    cross = qx * vy - qy * vx
    perpendicular2 = cross * cross / b.max(h2, 1e-30)
    section = b.sqrt(b.max(r2 - perpendicular2, 0.0))
    lo = b.max((projected - section) / hh, 0.0)
    hi = b.min((projected + section) / hh, 1.0)
    if ball:
        t = b.clamp((projected - dy * section / b.sqrt(h2 + dy * dy)) / hh, lo, hi)
    else:
        t = b.switch(b.ge(dy, 0.0), hi, lo)
    ex, ey = qx - vx * t, qy - vy * t
    line = az + dy * t + ((radius - b.sqrt(b.max(r2 - (ex * ex + ey * ey), 0.0))) if ball else 0.0)
    line = b.switch(b.le(perpendicular2, r2) & b.le(lo, hi), 1e6, line)
    answer = b.switch(b.lt(h2, 1e-18), line, point)
    b.link(answer, go.inputs['Height'])
    return tree
