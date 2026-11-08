"""CPU-written scalar fields as isosurfaces in Blender 5.2: the port of eidoverse/iso_field.js (makeIsoField).

The engine raymarched a CPU-owned voxel field per pixel (to dodge three's per-frame JS polygoniser). In
Blender the field becomes a real mesh through OpenVDB's volumeToMesh, so shadows, depth, motion blur and
the scene's lights all come for free (the raymarched surface could cast no shadow and needed a proxy box).

Same field contract as the engine: `field[idx(x, y, z)] = value` with idx = x + y*res + z*res^2 in the
engine's axes (y up), a node-centred grid spanning x, z in [-half, half] and y in [0, 2*half] around the
object's location, the surface where field > iso (high inside).

    iso = make_iso_field(resolution=64, half=0.5, iso=50, color='#9aa2ac', metalness=0.85, roughness=0.35)
    iso.field[iso.idx(x, y, z)] = 100
    iso.upload()                                          # a static surface, meshed now
    iso.bake(1, 120, update=lambda frame, t, iso: ...)    # or a field per frame -> a PLY sequence
"""

from __future__ import annotations

import os
import struct

import numpy as np

from ._util import abspath, color, frame_file


class IsoField:
    """What make_iso_field returns: field (flat numpy, the engine's layout), res, idx(), upload(), bake(),
    object (the surface mesh object) and material."""

    def __init__(self, scene, res, half, iso, material, name, location, cache_dir):
        import bpy
        self.scene = scene
        self.res, self.half, self.iso = int(res), float(half), float(iso)
        self.field = np.zeros(self.res ** 3, dtype=np.float32)
        self.name = name
        self.cache_dir = abspath(cache_dir)
        self.material = material
        me = bpy.data.meshes.new(name)
        self.object = bpy.data.objects.new(name, me)
        scene.collection.objects.link(self.object)
        self.object.location = tuple(location)
        if material is not None:
            me.materials.append(material)

    def idx(self, x, y, z):
        return x + y * self.res + z * self.res * self.res

    def _polygonize(self):
        """(verts (N, 3) in Blender object space, faces list) of the field's iso surface."""
        import openvdb as vdb
        r, h = self.res, self.half
        a = self.field.reshape(r, r, r)                         # [z3][y3][x3]
        b = np.ascontiguousarray(a.transpose(2, 0, 1)[:, ::-1, :])   # Blender [x][y = -z3][z = y3]
        g = vdb.FloatGrid(float(self.iso))                      # background: outside (iso - 0 below)
        # level-set orientation: negative inside, so normals face out
        g.copyFromArray((self.iso - b).astype(np.float32))
        vs = 2 * h / (r - 1)
        g.transform = vdb.createLinearTransform([[vs, 0, 0, 0], [0, vs, 0, 0], [0, 0, vs, 0], [-h, -h, 0, 1]])
        pts, tris, quads = g.convertToPolygons(isovalue=0.0, adaptivity=0.0)
        faces = [tuple(t) for t in tris] + [tuple(q) for q in quads]
        return np.asarray(pts, dtype=np.float32), faces

    def upload(self):
        """Mesh the current field into the object (the engine's upload())."""
        import bpy
        pts, faces = self._polygonize()
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(pts.tolist(), [], faces)
        for p in me.polygons:
            p.use_smooth = True
        if self.material is not None:
            me.materials.append(self.material)
        old = self.object.data
        self.object.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        return self

    def bake(self, frame_start=None, frame_end=None, update=None, log=print):
        """Mesh a changing field once per frame into <cache>/<name>_####.ply and play the sequence with a
        Geometry Nodes Import PLY on the object (the topology changes, so no point cache can hold it)."""
        import bpy
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        os.makedirs(self.cache_dir, exist_ok=True)
        for f in range(fs, fe + 1):
            if update:
                update(f, (f - fs) / fps, self)
            pts, faces = self._polygonize()
            _write_ply(frame_file(self.cache_dir, self.name, f, 'ply'), pts, faces)
        self._player(bpy)
        log(f'[fx.iso_field] baked frames {fs}..{fe} -> {self.cache_dir}')
        return self

    def _player(self, bpy):
        from ._nodes import new_group
        tree, gi, go = new_group(self.name + '.player', 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                                 [('Geometry', 'NodeSocketGeometry')])
        N, L = tree.nodes, tree.links
        tm = N.new('GeometryNodeInputSceneTime')
        vts = N.new('FunctionNodeValueToString')
        vts.data_type = 'INT'                       # only the integer mode zero-pads (0001)
        vts.inputs['Padding'].default_value = 4
        L.new(tm.outputs['Frame'], vts.inputs['Value'])
        join = N.new('GeometryNodeStringJoin')
        a = N.new('FunctionNodeInputString')
        a.string = os.path.join(self.cache_dir, self.name + '_')
        b = N.new('FunctionNodeInputString')
        b.string = '.ply'
        # Join Strings concatenates its multi-input links in REVERSE creation order (5.2, checked): link the
        # suffix first so the path reads <dir>/<name>_0001.ply
        L.new(b.outputs[0], join.inputs['Strings'])
        L.new(vts.outputs[0], join.inputs['Strings'])
        L.new(a.outputs[0], join.inputs['Strings'])
        imp = N.new('GeometryNodeImportPLY')
        L.new(join.outputs[0], imp.inputs['Path'])
        sm = N.new('GeometryNodeSetShadeSmooth')
        L.new(imp.outputs[0], sm.inputs['Geometry'])
        geo = sm.outputs[0]
        if self.material is not None:
            setm = N.new('GeometryNodeSetMaterial')
            L.new(geo, setm.inputs['Geometry'])
            setm.inputs['Material'].default_value = self.material
            geo = setm.outputs[0]
        L.new(geo, go.inputs[0])
        mod = self.object.modifiers.get('iso_player') or self.object.modifiers.new('iso_player', 'NODES')
        mod.node_group = tree


def _write_ply(path, pts, faces):
    tmp = path + '.tmp'
    with open(tmp, 'wb') as fh:
        hdr = ('ply\nformat binary_little_endian 1.0\n'
               f'element vertex {len(pts)}\nproperty float x\nproperty float y\nproperty float z\n'
               f'element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n')
        fh.write(hdr.encode('ascii'))
        fh.write(np.ascontiguousarray(pts, dtype='<f4').tobytes())
        for fc in faces:
            fh.write(struct.pack('<B', len(fc)) + struct.pack('<%di' % len(fc), *fc))
    os.replace(tmp, path)


def make_iso_field(resolution=64, half=0.5, iso=50.0, color_hex='#9aa2ac', metalness=0.85, roughness=0.35,
                   location=(0.0, 0.0, 0.0), material=None, color_node=None, emissive=None, scene=None,
                   name='iso_field', cache_dir='//iso_cache'):
    """The engine's makeIsoField. color_node(builder, position, normal) and emissive(builder, position, normal)
    are the hooks (they receive the shading point and normal as eidoblend.fx._nodes values, the way the
    engine's TSL hooks received the hit point and normal) and return an RGB Vec."""
    import bpy
    from ._nodes import Builder
    if material is None:
        material = bpy.data.materials.new(name + '_material')
        material.use_nodes = True
        bsdf = material.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (*color(color_hex), 1)
        bsdf.inputs['Metallic'].default_value = metalness
        bsdf.inputs['Roughness'].default_value = roughness
        if color_node or emissive:
            b = Builder(material.node_tree)
            geo = b.node('ShaderNodeNewGeometry')
            pos, nrm = b.vec(geo.outputs['Position']), b.vec(geo.outputs['Normal'])
            if color_node:
                b.link(color_node(b, pos, nrm), bsdf.inputs['Base Color'])
            if emissive:
                b.link(emissive(b, pos, nrm), bsdf.inputs['Emission Color'])
                bsdf.inputs['Emission Strength'].default_value = 1.0
    sc = scene or bpy.context.scene
    return IsoField(sc, resolution, half, iso, material, name, location, cache_dir)
