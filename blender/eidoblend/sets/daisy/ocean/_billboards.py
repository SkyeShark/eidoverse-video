"""ocean/_billboards.py: the WebGPU edition's vertex-stage billboards (echo glows, the porch halo, the human of light's
points) as Geometry Nodes that read the scene's active camera.

A billboard mesh is 4 vertices per light (as the JS geometry: every corner carries its light's centre), so the node
tree places each corner itself: centre + (camera right * corner.x + camera up * corner.y) * size, the camera taken
relative to the object (Object Info, Relative), the size never under `px_k` x the distance (a few pixels), as
`max(size, dist * k)` in the shaders.

    pts = quad_arrays(centres)                -> positions, triangles, corner per vertex, light index per vertex
    billboard_offset(nb, c, size, px_k, local_scale)   -> the corner's position (tuple of E), inside a GN tree
    additive_emission(name, color_fn)         -> an additive material (Emission + Transparent, BLENDED)
"""

from __future__ import annotations

import numpy as np

CORNERS = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], np.float32)


def quad_arrays(n):
    """4 vertices per light: (vertex -> light index), corners, triangles (0 1 2, 0 2 3 per quad, as the JS)."""
    idx = np.repeat(np.arange(n), 4)
    cor = np.tile(CORNERS, (n, 1))
    base = np.arange(n) * 4
    tris = np.stack([np.stack([base, base + 1, base + 2], 1), np.stack([base, base + 2, base + 3], 1)], 1).reshape(-1, 3)
    return idx, cor, tris


def camera_frame(nb):
    """the active camera in the modified object's space: (position, right, up) as tuples of E."""
    cam = nb.node('GeometryNodeInputActiveCamera')
    info = nb.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    nb.tree.links.new(cam.outputs[0], info.inputs['Object'])
    loc = nb.separate(info.outputs['Location'])
    axes = []
    for v in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        rv = nb.node('FunctionNodeRotateVector')
        rv.inputs['Vector'].default_value = v
        nb.tree.links.new(info.outputs['Rotation'], rv.inputs['Rotation'])
        axes.append(nb.separate(rv.outputs[0]))
    return loc, axes[0], axes[1]


def billboard_offset(nb, c, corner, size, px_k, local_scale=1.0, frame=None):
    """centre c (local, tuple of E) -> this corner's local position: camera-facing, size >= distance * px_k (world
    units; local_scale undoes a scaled parent)."""
    loc, R, U = frame or camera_frame(nb)
    d = nb.vlen(tuple(nb.s(c[i]) - loc[i] for i in range(3))) * local_scale
    s = nb.max(size, d * px_k) * (1.0 / local_scale)
    return tuple(nb.s(c[i]) + (R[i] * corner[0] + U[i] * corner[1]) * s for i in range(3))


def additive_emission(name, build_color):
    """An additive material: Add(Transparent, Emission(color)), BLENDED, never casting shadows. build_color(nb) ->
    the colour tuple (E)."""
    import bpy
    from ._nodes import NB, clear_material
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, out = clear_material(mat)
    nb = NB(nt, x0=-1600, y0=500, rows=30)
    col = build_color(nb)
    em = nb.node('ShaderNodeEmission')
    em.hide = False
    nb.link(tuple(col), em.inputs['Color'])
    tr = nb.node('ShaderNodeBsdfTransparent')
    add = nb.node('ShaderNodeAddShader')
    add.hide = False
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    if hasattr(mat, 'use_transparency_overlap'):
        mat.use_transparency_overlap = True
    return mat
