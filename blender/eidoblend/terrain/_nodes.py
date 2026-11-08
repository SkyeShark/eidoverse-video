"""Terse shader-node building for the terrain family's materials (private)."""
import bpy

# ShaderNodeMix socket indices per data_type (Blender 5.2):
# inputs  0 Factor(float) 1 Factor(vector) 2 A(float) 3 B(float) 4 A(vec) 5 B(vec) 6 A(rgba) 7 B(rgba)
# outputs 0 Result(float) 1 Result(vec) 2 Result(rgba)
_MIX_IO = {'FLOAT': (2, 3, 0), 'VECTOR': (4, 5, 1), 'RGBA': (6, 7, 2)}


class Graph:
    """Wraps a node tree: every helper returns an OUTPUT socket, and every input accepts a socket
    or a constant, so maths reads like maths."""

    def __init__(self, tree):
        self.tree = tree
        self.nodes = tree.nodes
        self.links = tree.links
        self._col = 0
        self._row = 0

    def node(self, idname, label=None, **props):
        n = self.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        if label:
            n.label = label
        n.location = (-200 * (self._col % 40) - 400, -160 * (self._row % 60))
        self._row += 1
        if self._row % 12 == 0:
            self._col += 1
        return n

    def set(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.links.new(v, sock)
        else:
            if hasattr(sock, 'default_value'):
                dv = sock.default_value
                try:
                    n = len(dv)
                except TypeError:
                    n = 0
                if n and not hasattr(v, '__len__'):
                    v = [v] * n
                    if n == 4:
                        v[3] = 1.0
                sock.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        self.set(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b):
        return self.math('ADD', a, b)

    def mul(self, a, b, clamp=False):
        return self.math('MULTIPLY', a, b, clamp=clamp)

    def sub(self, a, b):
        return self.math('SUBTRACT', a, b)

    def vmath(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        if scale is not None:
            self.set(n.inputs[3], scale)
        return n.outputs[1] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs[0]

    def mix(self, data_type, fac, a, b, blend='MIX', clamp=False):
        n = self.node('ShaderNodeMix', data_type=data_type, blend_type=blend, clamp_result=clamp)
        ia, ib, io = _MIX_IO[data_type]
        self.set(n.inputs[0], fac)
        self.set(n.inputs[ia], a)
        self.set(n.inputs[ib], b)
        return n.outputs[io]

    def smoothstep(self, e0, e1, x):
        """GLSL smoothstep(e0, e1, x) (e0 > e1 allowed, like the JS masks use)."""
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
        self.set(n.inputs['Value'], x)
        self.set(n.inputs['From Min'], e0)
        self.set(n.inputs['From Max'], e1)
        self.set(n.inputs['To Min'], 0.0)
        self.set(n.inputs['To Max'], 1.0)
        return n.outputs['Result']

    def map_range(self, x, a, b, c, d, clamp=True):
        n = self.node('ShaderNodeMapRange', clamp=clamp)
        self.set(n.inputs['Value'], x)
        self.set(n.inputs['From Min'], a)
        self.set(n.inputs['From Max'], b)
        self.set(n.inputs['To Min'], c)
        self.set(n.inputs['To Max'], d)
        return n.outputs['Result']

    def tex(self, image, vector, interpolation='Linear'):
        n = self.node('ShaderNodeTexImage', interpolation=interpolation, extension='REPEAT')
        n.image = image
        self.set(n.inputs['Vector'], vector)
        return n

    def noise(self, vector, scale, detail=3.0, roughness=0.55, w=None, dims='3D'):
        n = self.node('ShaderNodeTexNoise', noise_dimensions=('4D' if w is not None else dims))
        self.set(n.inputs['Vector'], vector)
        self.set(n.inputs['Scale'], scale)
        self.set(n.inputs['Detail'], detail)
        self.set(n.inputs['Roughness'], roughness)
        if w is not None:
            self.set(n.inputs['W'], w)
        return n.outputs['Fac']

    def attribute(self, name):
        n = self.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name)
        return n

    def separate_rgb(self, col):
        n = self.node('ShaderNodeSeparateColor')
        self.set(n.inputs[0], col)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def geometry(self):
        return self.node('ShaderNodeNewGeometry')

    def separate_xyz(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.set(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def combine_xyz(self, x, y, z=0.0):
        n = self.node('ShaderNodeCombineXYZ')
        self.set(n.inputs[0], x)
        self.set(n.inputs[1], y)
        self.set(n.inputs[2], z)
        return n.outputs[0]

    def view_distance(self):
        """Camera Data > View Distance: metres from the camera to the shaded point."""
        return self.node('ShaderNodeCameraData').outputs['View Distance']

    def handover(self, near, far):
        """0 within `near` metres of the camera, 1 past `far`: where 'Auto' reads switch from the
        full-resolution image to its mipmaps."""
        return self.smoothstep(near, far, self.view_distance())

    def read(self, image, vector, interpolation='Linear', far=None):
        """An image's Color. interpolation 'Auto' reads 'Cubic' (EEVEE: the full-resolution image,
        no mipmaps: sharp at grazing angles, crawls in motion once a pixel covers many texels) where
        `far` (a handover() socket) is 0 and mipmapped 'Linear' where it is 1."""
        if interpolation != 'Auto':
            return self.tex(image, vector, interpolation).outputs['Color']
        return self.mix('RGBA', far, self.tex(image, vector, 'Cubic').outputs['Color'],
                        self.tex(image, vector, 'Linear').outputs['Color'])


def new_material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    return mat


def principled(mat):
    for n in mat.node_tree.nodes:
        if n.bl_idname == 'ShaderNodeBsdfPrincipled':
            return n
    return None


def output(mat):
    for n in mat.node_tree.nodes:
        if n.bl_idname == 'ShaderNodeOutputMaterial':
            return n
    return None
