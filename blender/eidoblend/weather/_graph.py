"""Node-graph helpers for the weather port: round one's expression builder (eidoblend.fx._nodes) plus the Geometry
Nodes pieces and the hash / noise functions of weather_system.js, so the TSL ports as code.

    b = G(tree)
    h1 = b.hash_i(b.index(), 1)                  # weather_system.js hashI(instanceIndex, 1)
    n = b.vnoise2(x, z)                          # vnoise2 over the Hoskins hash2
"""
import math

import bpy

from ..fx._nodes import Builder, Expr, Vec, new_group  # noqa: F401  (re-exported)


class G(Builder):
    """Builder + Geometry Nodes nodes + the weather hashes (works in shader and geometry trees)."""

    # ---- scalar helpers ----
    def sstep(self, e0, e1, x):
        """smoothstep with edges that may be Exprs or sockets (GLSL: undefined when e0 >= e1; the JS never does)."""
        e0, e1 = self.s(e0), self.s(e1)
        t = self.clamp((self.s(x) - e0) / (e1 - e0))
        return t * t * (3.0 - 2.0 * t)

    def lerp(self, a, b, t):
        return a + (b - a) * t

    def hash_i(self, n, k):
        """hashI(n, k) = fract(q2 * (q2 + q)), q = fract(n * 0.1031 + k * 0.61803), q2 = q * (q + 33.33)."""
        q = self.fract(self.s(n) * 0.1031 + k * 0.61803)
        q2 = q * (q + 33.33)
        return self.fract(q2 * (q2 + q))

    def hash2(self, x, y):
        """The Hoskins-style hash2 of the wetness wrapper: a = fract((x, y, x) * 0.1031); d = dot(a, a.yzx + 33.33);
        b = a + d; fract((b.x + b.y) * b.z)."""
        ax = self.fract(self.s(x) * 0.1031)
        ay = self.fract(self.s(y) * 0.1031)
        az = ax
        d = ax * (ay + 33.33) + ay * (az + 33.33) + az * (ax + 33.33)
        bx, by, bz = ax + d, ay + d, az + d
        return self.fract((bx + by) * bz)

    def vnoise2(self, x, y):
        """vnoise2: value noise on the hash2 lattice with a quintic fade (C2, no lattice creases)."""
        ix, iy = self.floor(x), self.floor(y)
        fx, fy = self.s(x) - ix, self.s(y) - iy
        sx = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0)
        sy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0)
        a = self.hash2(ix, iy)
        b = self.hash2(ix + 1.0, iy)
        c = self.hash2(ix, iy + 1.0)
        d = self.hash2(ix + 1.0, iy + 1.0)
        return self.lerp(self.lerp(a, b, sx), self.lerp(c, d, sx), sy)

    def atan2(self, y, x):
        return self.math('ARCTAN2', y, x)

    def length2(self, x, y):
        return self.sqrt(self.s(x) * x + self.s(y) * y)

    def normalize(self, v):
        return self.vmath('NORMALIZE', v)

    def dot(self, a, b):
        return self.vmath('DOT_PRODUCT', a, b)

    def cross(self, a, b):
        return self.vmath('CROSS_PRODUCT', a, b)

    def length(self, a):
        return self.vmath('LENGTH', a)

    def lt(self, a, b):
        """a < b as 0/1."""
        return self.math('LESS_THAN', a, b)

    def gt(self, a, b):
        return self.math('GREATER_THAN', a, b)

    # ---- geometry nodes ----
    def index(self):
        return Expr(self, self.node('GeometryNodeInputIndex').outputs[0])

    def position(self):
        return Vec(self, self.node('GeometryNodeInputPosition').outputs[0])

    def scene_seconds(self):
        return Expr(self, self.node('GeometryNodeInputSceneTime').outputs['Seconds'])

    def named(self, name, data_type='FLOAT'):
        n = self.node('GeometryNodeInputNamedAttribute', data_type=data_type)
        n.inputs['Name'].default_value = name
        out = n.outputs[0]
        return Vec(self, out) if data_type in ('FLOAT_VECTOR', 'FLOAT_COLOR') else Expr(self, out)

    def points(self, count):
        n = self.node('GeometryNodePoints')
        if isinstance(count, int):
            n.inputs['Count'].default_value = count
        else:
            self.link(count, n.inputs['Count'])
        return n.outputs['Points']

    def instance_on_points(self, points, instance):
        n = self.node('GeometryNodeInstanceOnPoints')
        self.links.new(points, n.inputs['Points'])
        self.links.new(instance, n.inputs['Instance'])
        return n.outputs['Instances']

    def combine_matrix(self, c1, c2, c3, c4):
        """A 4x4 transform from its columns (vectors): local x, y, z axes and the translation."""
        n = self.node('FunctionNodeCombineMatrix')
        for ci, col in enumerate((c1, c2, c3, c4)):
            xyz = self.vec(col).xyz() if not isinstance(col, (tuple, list)) else tuple(col)
            for r in range(3):
                self.link(xyz[r], n.inputs[ci * 4 + r])
            self.link(0.0 if ci < 3 else 1.0, n.inputs[ci * 4 + 3])
        return n.outputs['Matrix']

    def set_instance_transform(self, instances, matrix):
        n = self.node('GeometryNodeSetInstanceTransform')
        self.links.new(instances, n.inputs['Instances'])
        self.links.new(matrix, n.inputs['Transform'])
        return n.outputs['Instances']

    def realize(self, geo):
        n = self.node('GeometryNodeRealizeInstances')
        self.links.new(geo, n.inputs['Geometry'])
        return n.outputs['Geometry']

    def store(self, geo, name, value, data_type='FLOAT', domain='POINT'):
        n = self.node('GeometryNodeStoreNamedAttribute', data_type=data_type, domain=domain)
        self.links.new(geo, n.inputs['Geometry'])
        n.inputs['Name'].default_value = name
        self.link(value, n.inputs['Value'])
        return n.outputs['Geometry']

    def set_material(self, geo, material):
        n = self.node('GeometryNodeSetMaterial')
        self.links.new(geo, n.inputs['Geometry'])
        n.inputs['Material'].default_value = material
        return n.outputs['Geometry']

    def three_to_blender(self, geo):
        """three.js Y-up -> Blender Z-up: a +90 degree rotation about X, (x, y, z) -> (x, -z, y)."""
        n = self.node('GeometryNodeTransform')
        self.links.new(geo, n.inputs['Geometry'])
        n.inputs['Rotation'].default_value = (math.pi / 2, 0.0, 0.0)
        return n.outputs['Geometry']

    def blender_to_three(self, geo):
        n = self.node('GeometryNodeTransform')
        self.links.new(geo, n.inputs['Geometry'])
        n.inputs['Rotation'].default_value = (-math.pi / 2, 0.0, 0.0)
        return n.outputs['Geometry']

    def image_sample(self, image, u, v, interpolation='Linear', extension='REPEAT'):
        """(Color Vec, Alpha Expr) of a GN Image Texture at (u, v). The Vector input is an implicit field: linked."""
        n = self.node('GeometryNodeImageTexture', interpolation=interpolation, extension=extension)
        n.inputs['Image'].default_value = image
        self.link(self.combine(u, v, 0.0), n.inputs['Vector'])
        return Vec(self, n.outputs['Color']), Expr(self, n.outputs['Alpha'])

    def red(self, color_vec):
        n = self.node('FunctionNodeSeparateColor')
        self.link(color_vec, n.inputs[0])
        return Expr(self, n.outputs[0])

    def collection_geometry(self, collection):
        """The realized geometry of a collection's objects, in world space."""
        n = self.node('GeometryNodeCollectionInfo', transform_space='RELATIVE')
        n.inputs['Collection'].default_value = collection
        return self.realize(n.outputs['Instances'])

    def raycast(self, target, source, direction, length):
        """(is_hit 0/1 Expr, hit position Vec, hit normal Vec) along a ray."""
        n = self.node('GeometryNodeRaycast')
        self.links.new(target, n.inputs['Target Geometry'])
        self.link(source, n.inputs['Source Position'])
        self.link(direction, n.inputs['Ray Direction'])
        self.link(length, n.inputs['Ray Length'])
        sw = self.node('GeometryNodeSwitch', input_type='FLOAT')
        self.links.new(n.outputs['Is Hit'], sw.inputs['Switch'])
        sw.inputs['False'].default_value = 0.0
        sw.inputs['True'].default_value = 1.0
        return Expr(self, sw.outputs[0]), Vec(self, n.outputs['Hit Position']), Vec(self, n.outputs['Hit Normal'])

    def delete_where(self, geo, cond, domain='POINT'):
        """Delete elements where cond (a 0/1 Expr) > 0.5."""
        cmp_ = self.node('FunctionNodeCompare', data_type='FLOAT', operation='GREATER_THAN')
        self.link(cond, cmp_.inputs['A'])
        cmp_.inputs['B'].default_value = 0.5
        n = self.node('GeometryNodeDeleteGeometry', domain=domain)
        self.links.new(geo, n.inputs['Geometry'])
        self.links.new(cmp_.outputs[0], n.inputs['Selection'])
        return n.outputs['Geometry']

    def grid(self, size_x=1.0, size_y=1.0):
        """A one-quad grid with its UV map stored as 'UVMap' (corner FLOAT2)."""
        n = self.node('GeometryNodeMeshGrid')
        self.link(size_x, n.inputs['Size X'])
        self.link(size_y, n.inputs['Size Y'])
        n.inputs['Vertices X'].default_value = 2
        n.inputs['Vertices Y'].default_value = 2
        return self.store(n.outputs['Mesh'], 'UVMap', n.outputs['UV Map'], 'FLOAT2', 'CORNER')

    def translate(self, geo, offset):
        n = self.node('GeometryNodeTransform')
        self.links.new(geo, n.inputs['Geometry'])
        n.inputs['Translation'].default_value = offset
        return n.outputs['Geometry']


def gn_group(name, inputs, outputs=(('Geometry', 'NodeSocketGeometry'),)):
    """A Geometry Nodes group with typed inputs [(name, socket_type, default)]: (tree, group input, group output,
    {input name: socket identifier} for keying modifier inputs)."""
    tree, gi, go = new_group(name, 'GeometryNodeTree', [(n, t) for n, t, *_ in inputs], list(outputs))
    tree.is_modifier = True
    ids = {}
    for spec in inputs:
        n, t = spec[0], spec[1]
        item = tree.interface.items_tree[n]
        ids[n] = item.identifier
        if len(spec) > 2 and spec[2] is not None and hasattr(item, 'default_value'):
            item.default_value = spec[2]
    return tree, gi, go, ids


def shader_group(name, inputs, outputs):
    """A shader node group with typed inputs [(name, socket_type, default)] and outputs [(name, socket_type)]."""
    tree, gi, go = new_group(name, 'ShaderNodeTree', [(n, t) for n, t, *_ in inputs], list(outputs))
    for spec in inputs:
        if len(spec) > 2 and spec[2] is not None:
            item = tree.interface.items_tree[spec[0]]
            if hasattr(item, 'default_value'):
                item.default_value = spec[2]
    return tree, gi, go


def mod_path(mod, ident):
    """The data path of a Geometry Nodes modifier input's value. Blender 5.2 keeps each input as a struct
    (value, type, attribute_name) at modifier.properties.inputs.<identifier>, not as an ID property."""
    return f'modifiers["{mod.name}"].properties.inputs.{ident}.value'


def add_gn(obj, tree, name):
    """Attach `tree` as a Geometry Nodes modifier named `name` (replacing one of that name)."""
    if name in obj.modifiers:
        obj.modifiers.remove(obj.modifiers[name])
    mod = obj.modifiers.new(name, 'NODES')
    mod.node_group = tree
    return mod


def set_input(mod, ident, value):
    """Set a Geometry Nodes modifier input (Blender 5.2: modifier.properties.inputs.<identifier>.value)."""
    item = getattr(mod.properties.inputs, ident)
    item.value = tuple(value) if isinstance(value, (list, tuple)) else value


def get_input(mod, ident):
    v = getattr(mod.properties.inputs, ident).value
    return tuple(v) if hasattr(v, '__len__') and not isinstance(v, str) else v


def empty_mesh_object(name, collection):
    """An object at the origin with an empty mesh: a host for a Geometry Nodes generator."""
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
    if ob.name not in collection.objects:
        collection.objects.link(ob)
    ob.location = (0, 0, 0)
    ob.rotation_euler = (0, 0, 0)
    ob.scale = (1, 1, 1)
    return ob
