"""look/stage_rig.py: stage lights that EXIST. Every light is built with its fixture (a par can or a profile spot, hung
on a pipe), aimed by construction, its lens glowing in the light's colour at the light's own level. A light can't hang
where no fixture is, and a fixture whose light is off is dark. stage_rig.js ported.

    from eidoblend.look.stage_rig import create_stage_rig
    rig = create_stage_rig(scene, ceiling=4.6)
    foh = rig.pipe(x0=-2.4, x1=2.4, z=4.38, y=-4.9)                # Blender axes: z is the height, y the depth
    key = rig.fixture(type='profile', pipe=foh, x=0, target=(0, 0.2, 0.9), kelvin_k=4200, watts=900,
                      angle=0.33, penumbra=0.45)                   # -> Fixture(light, body, lens, ...)
    key.light.data.energy = 450                                     # key it: the lens follows (a driver), no update()
    key.light.hide_render = True                                    # off: its lens goes dark too
    rig.clears(key, y=-2.0, z=3.2)                                 # does the cone pass under the arch's face?

Axes: three's pipe {y: height, z: depth} is Blender's {z: height, y: -depth} (three (x, y, z) -> (x, -z, y)).
Levels: three's SpotLight candela -> watts with lighting.candela_to_watts (cd x 4 pi / 683); angle and penumbra are
three's (half angle, 0..1) -> spot_size = 2 x angle, spot_blend = penumbra.
The light sits 3 cm in front of its lens; the fixture's own parts cast no shadow (visible_shadow off), so a fixture never
shadows its own beam. Unlike the WebGPU rig (shadow maps cost there), lights cast shadows by default: EEVEE's virtual
shadow maps are cheap and a stage without shadows reads as a render. lamp=False hangs a dark fixture with NO light
in it (never a light at energy 0).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import camera as C
from . import lighting as L


def _mesh_obj(name, bm, mat, col):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.visible_shadow = False
    return ob


def _cylinder(r1, r2, depth, segs=24, cap=True):
    """A cylinder (or a cone frustum) along +Z from -depth/2 to +depth/2."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r1, radius2=r2, depth=depth)
    return bm


def _torus(major, minor, segs=24, rings=6, arc=2 * math.pi):
    """A torus (or an arc of one, from +X round toward +Y) round the Z axis."""
    bm = bmesh.new()
    n = segs + (1 if arc < 2 * math.pi - 1e-6 else 0)
    rings_v = []
    for i in range(n):
        a = arc * i / segs
        c = Vector((math.cos(a), math.sin(a), 0.0))
        ring = []
        for j in range(rings):
            b = 2 * math.pi * j / rings
            ring.append(bm.verts.new(c * (major + minor * math.cos(b)) + Vector((0, 0, minor * math.sin(b)))))
        rings_v.append(ring)
    closed = arc >= 2 * math.pi - 1e-6
    for i in range(segs if closed else n - 1):
        a, b = rings_v[i], rings_v[(i + 1) % n]
        for j in range(rings):
            bm.faces.new((a[j], a[(j + 1) % rings], b[(j + 1) % rings], b[j]))
    return bm


def _disc(r, segs=24):
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=segs, radius=r)
    return bm


def _xform(bm, m):
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return bm


# the two fixture shapes, built along +Z (the beam), the pivot (yoke axis) at the origin
SHAPES = {
    'par': {'yoke_r': 0.135, 'lens_r': 0.09, 'front': 0.15,
            'parts': lambda: [_cylinder(0.095, 0.105, 0.3, cap=False),
                              _xform(_disc(0.095), Matrix.Translation((0, 0, -0.15))),
                              _xform(_torus(0.1, 0.01), Matrix.Translation((0, 0, 0.15)))]},
    'profile': {'yoke_r': 0.13, 'lens_r': 0.065, 'front': 0.36,
                'parts': lambda: [_cylinder(0.1, 0.1, 0.3),
                                  _xform(_cylinder(0.08, 0.072, 0.21, 20, cap=False), Matrix.Translation((0, 0, 0.255))),
                                  _xform(_torus(0.07, 0.008, 20), Matrix.Translation((0, 0, 0.36)))]},
}


class Fixture:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class StageRig:
    def __init__(self, scene, collection=None, metal=None, ceiling=None, glow=2.5):
        self.scene = scene
        self.col = collection or bpy.data.collections.new('stage_rig')
        if self.col.name not in scene.collection.children and collection is None:
            scene.collection.children.link(self.col)
        self.metal = metal or self._metal()
        self.ceiling = ceiling
        self.glow = float(glow)
        self.fixtures = []

    @staticmethod
    def _metal():
        m = bpy.data.materials.new('rig_metal')
        m.use_nodes = True
        p = m.node_tree.nodes['Principled BSDF']
        p.inputs['Base Color'].default_value = (0.035, 0.035, 0.04, 1)
        p.inputs['Metallic'].default_value = 0.85
        p.inputs['Roughness'].default_value = 0.42
        return m

    def pipe(self, x0, x1, z, y, radius=0.024, rods=True, name='pipe'):
        """A pipe along X at height z and depth y; with a ceiling, two drop rods hold it up."""
        bm = _xform(_cylinder(radius, radius, x1 - x0, 16), Matrix.Translation(((x0 + x1) / 2, y, z))
                    @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
        _mesh_obj(name, bm, self.metal, self.col)
        if rods and self.ceiling is not None and self.ceiling > z:
            h = self.ceiling - z
            for x in (x0 + 0.2, x1 - 0.2):
                _mesh_obj(name + '_rod', _xform(_cylinder(0.009, 0.009, h, 8), Matrix.Translation((x, y, z + h / 2))),
                          self.metal, self.col)
        return {'x0': x0, 'x1': x1, 'z': z, 'y': y, 'radius': radius}

    def fixture(self, type='par', pipe=None, x=0.0, target=(0, 0, 0), color=None, kelvin_k=3200, watts=100.0,
                angle=0.5, penumbra=0.5, distance=0.0, cast_shadow=True, radius=None, name=None, lamp=True):
        """Hang a fixture on `pipe` at x, aimed at `target` (Blender metres). watts: Blender W (three candela ->
        lighting.candela_to_watts). angle/penumbra: three's half angle (radians) and penumbra. color: an RGB tuple
        (else the colour temperature kelvin_k). radius: the beam's source size (default the lens's: its shadows soften
        like a real lens)."""
        S = SHAPES[type]
        name = name or f'{type}_{len(self.fixtures)}'
        p = pipe
        pivot = Vector((x, p['y'], p['z'] - p['radius'] - 0.03 - 0.05 - S['yoke_r']))
        aim = Vector(target)
        # the yoke: panned to face the target (about Z), a half ring under the pipe from one side of the body to the
        # other, a stem and a clamp up to the pipe
        pan = math.atan2(aim.y - pivot.y, aim.x - pivot.x) - math.pi / 2
        yoke_m = Matrix.Translation(pivot) @ Matrix.Rotation(pan, 4, 'Z')
        ring = _xform(_torus(S['yoke_r'], 0.011, arc=math.pi), Matrix.Rotation(math.pi / 2, 4, 'X'))   # +X over +Z to -X
        _mesh_obj(name + '_yoke', _xform(ring, yoke_m), self.metal, self.col)
        _mesh_obj(name + '_stem', _xform(_cylinder(0.011, 0.011, 0.03, 8),
                                         yoke_m @ Matrix.Translation((0, 0, S['yoke_r'] + 0.015))), self.metal, self.col)
        clamp = bmesh.new()
        bmesh.ops.create_cube(clamp, size=1.0)
        _mesh_obj(name + '_clamp', _xform(clamp, yoke_m @ Matrix.Translation((0, 0, S['yoke_r'] + 0.055))
                                          @ Matrix.Diagonal((0.06, 0.06, 0.05, 1.0))), self.metal, self.col)
        # the body: +Z of its parts points at the target (a camera-style look matrix has -Z forward: flip it)
        look = C.look_matrix(pivot, aim) @ Matrix.Rotation(math.pi, 4, 'X')
        body = bpy.data.objects.new(name, None)
        self.col.objects.link(body)
        body.matrix_world = look
        for i, part in enumerate(S['parts']()):
            o = _mesh_obj(f'{name}_body{i}', part, self.metal, self.col)
            o.parent = body
        # the lens: its own material, emission = the light's colour x glow x level (a driver on the light's energy)
        rgb = tuple(color) if color is not None else L.blackbody_rgb(kelvin_k)
        lm = bpy.data.materials.new(name + '_lens')
        lm.use_nodes = True
        bsdf = lm.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.022, 1)
        bsdf.inputs['Roughness'].default_value = 0.12
        bsdf.inputs['Emission Color'].default_value = (*rgb, 1)
        bsdf.inputs['Emission Strength'].default_value = 0.0
        lens = _mesh_obj(name + '_lens', _xform(_disc(S['lens_r']), Matrix.Translation((0, 0, S['front'] + 0.002))),
                         lm, self.col)
        lens.parent = body
        light = None
        if lamp:
            light = bpy.data.objects.new(name + '_light', bpy.data.lights.new(name + '_light', 'SPOT'))
            self.col.objects.link(light)
            d = light.data
            d.energy = float(watts)
            d.spot_size = 2.0 * angle
            d.spot_blend = float(penumbra)
            d.shadow_soft_size = float(radius if radius is not None else S['lens_r'])
            d.use_shadow = bool(cast_shadow)
            if color is not None:
                d.color = rgb
            else:
                L.kelvin(d, kelvin_k)
            if distance:
                d.use_custom_distance = True
                d.cutoff_distance = float(distance)
            light.parent = body
            light.matrix_parent_inverse = Matrix()
            # the light 3 cm in front of the lens, shining along the body's +Z (a spot shines down its own -Z)
            light.matrix_basis = Matrix.Translation((0, 0, S['front'] + 0.03)) @ Matrix.Rotation(math.pi, 4, 'X')
            light['base'] = float(watts)
            fc = bsdf.inputs['Emission Strength'].driver_add('default_value')
            drv = fc.driver
            drv.type = 'SCRIPTED'
            v = drv.variables.new()
            v.name = 'e'
            v.type = 'SINGLE_PROP'
            v.targets[0].id_type = 'LIGHT'
            v.targets[0].id = d
            v.targets[0].data_path = 'energy'
            h = drv.variables.new()                  # a hidden light is off: its lens goes dark (WebGPU: !visible)
            h.name = 'h'
            h.type = 'SINGLE_PROP'
            h.targets[0].id_type = 'OBJECT'
            h.targets[0].id = light
            h.targets[0].data_path = 'hide_render'
            drv.expression = f'{self.glow:g} * e / {max(1e-6, float(watts)):g} * (1 - h)'
        f = Fixture(type=type, light=light, body=body, lens=lens, base=float(watts), pivot=pivot, aim=aim,
                    angle=angle, name=name)
        self.fixtures.append(f)
        return f

    def clears(self, f, y, z):
        """Does fixture f's cone pass under height z where it crosses the plane at depth y (the face of an arch between
        it and the stage)? -> dict(ok, edge_z): the cone's upper edge height at that plane."""
        bpy.context.view_layer.update()
        o = f.light.matrix_world.translation if f.light else f.pivot
        d = (f.aim - o).normalized()
        horiz = math.hypot(d.x, d.y)
        elev = math.atan2(-d.z, horiz)                       # the axis, below the horizon
        reach = abs(o.y - y) / max(1e-6, abs(d.y) / max(horiz, 1e-9))
        edge = o.z - reach * math.tan(elev - f.angle)
        return {'ok': edge < z, 'edge_z': edge}

    def update(self):
        """Nothing to do: each lens follows its light's energy through a driver (kept so ported code runs)."""
        return self


def create_stage_rig(scene, collection=None, metal=None, ceiling=None, glow=2.5):
    return StageRig(scene, collection, metal, ceiling, glow)
