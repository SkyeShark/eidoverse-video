"""eidoblend.sets.wake_another_one.hall.carton: the hall's two-part carton. Blender.

    from eidoblend.sets.wake_another_one.hall import carton
    sets = carton.build(layout['carton'], board, insert, parent_collection)
    # -> {'tray': Collection, 'hood': Collection, 'closed': Collection, 'meas': {...}}

A plain shipping carton of layout.json's measures, in the tray's frame (its floor's centre at the origin, +x the left of
whoever stands in it, -y its front, z up):
  the TRAY   the lower part: four walls of board to the seam with a floor, a collar inside them that stands up past the
             seam to the rim (the hood comes down over it), and a moulded insert: a ledge at the rim's height and a
             pocket down to the height of `body_mark`, where a body stands or kneels
  the HOOD   the upper part: four walls and a top, from the seam to the carton's full height
  CLOSED     the tray with its hood on
Each is a collection in the tray's frame, to instance (a collection instance or a Geometry Nodes Collection Info). The
board and the insert are two materials the caller gives (the look makes them layered). No print, no marks.
"""

import bmesh
import bpy


def _shell(name, lo, hi, t, open_side, mat_index=0):
    """an open box of board `t` thick (open on 'top' or 'bottom'), ONE closed shell: its outside, its inside and its rim"""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    bm = bmesh.new()
    o = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    if open_side == 'top':
        i = [bm.verts.new(p) for p in ((x0 + t, y0 + t, z0 + t), (x1 - t, y0 + t, z0 + t), (x1 - t, y1 - t, z0 + t),
                                       (x0 + t, y1 - t, z0 + t), (x0 + t, y0 + t, z1), (x1 - t, y0 + t, z1),
                                       (x1 - t, y1 - t, z1), (x0 + t, y1 - t, z1))]
        faces = [(o[0], o[3], o[2], o[1]), (i[0], i[1], i[2], i[3])]                     # the floor, out and in
        for k in range(4):
            j = (k + 1) % 4
            faces += [(o[k], o[j], o[4 + j], o[4 + k]),                                     # the wall outside
                      (i[k], i[4 + k], i[4 + j], i[j]),                                     # inside
                      (o[4 + k], o[4 + j], i[4 + j], i[4 + k])]                             # its rim
    else:
        i = [bm.verts.new(p) for p in ((x0 + t, y0 + t, z0), (x1 - t, y0 + t, z0), (x1 - t, y1 - t, z0),
                                       (x0 + t, y1 - t, z0), (x0 + t, y0 + t, z1 - t), (x1 - t, y0 + t, z1 - t),
                                       (x1 - t, y1 - t, z1 - t), (x0 + t, y1 - t, z1 - t))]
        faces = [(o[4], o[5], o[6], o[7]), (i[4], i[7], i[6], i[5])]                     # the top, out and in
        for k in range(4):
            j = (k + 1) % 4
            faces += [(o[k], o[j], o[4 + j], o[4 + k]),
                      (i[k], i[4 + k], i[4 + j], i[j]),
                      (o[k], i[k], i[j], o[j])]                                             # its rim at the bottom
    for f in faces:
        bm.faces.new(f).material_index = mat_index
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _insert(name, outer, inner, z_top, z_floor):
    """the moulded insert: a ledge ring at z_top between the outer and inner squares, the pocket's walls down to z_floor,
    its floor"""
    bm = bmesh.new()
    O = [bm.verts.new((sx * outer, sy * outer, z_top)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    I = [bm.verts.new((sx * inner, sy * inner, z_top)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    B = [bm.verts.new((sx * inner, sy * inner, z_floor)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for k in range(4):
        j = (k + 1) % 4
        bm.faces.new((O[k], O[j], I[j], I[k]))
        bm.faces.new((I[k], I[j], B[j], B[k]))
    bm.faces.new(B)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    return me


def build(C, board, insert_mat, parent):
    """the carton's three sets as collections under `parent` (C: layout.json's 'carton') -> {'tray', 'hood', 'closed',
    'meas'}"""
    sx, sy, sz = C['size']
    hx, hy = sx / 2.0, sy / 2.0
    t, seam, rim = C['wall'], C['seam_z'], C['rim_z']
    base = _shell('carton_base', (-hx, -hy, 0.0), (hx, hy, seam), t, 'top')
    cin = hx - t - 0.0005
    collar = _shell('carton_collar', (-cin, -cin, seam - 0.12), (cin, cin, rim), 0.004, 'top')
    hood = _shell('carton_hood', (-hx, -hy, seam), (hx, hy, sz), t, 'bottom')
    ins = _insert('carton_insert', C['insert']['outer'], C['insert']['inner'], rim - 0.004, C['body_mark'][2])
    for me in (base, collar, hood):
        me.materials.append(board)
    ins.materials.append(insert_mat)
    out = {}
    for key, parts in (('tray', (base, collar, ins)), ('hood', (hood,)), ('closed', (base, collar, hood))):
        col = bpy.data.collections.new('carton_' + key)
        parent.children.link(col)
        for me in parts:
            col.objects.link(bpy.data.objects.new(f'carton_{key}|{me.name}', me))
        out[key] = col
    out['meas'] = {'size': [sx, sy, sz], 'seam_z': seam, 'rim_z': rim, 'hood_height': round(sz - seam, 4),
                   'tray_floor_z': C['body_mark'][2]}
    return out
