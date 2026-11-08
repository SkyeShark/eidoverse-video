"""sun_corona: a corona of light-petals around the TRUE sun, the day's eye (a daisy is 'daeges eage'). eidoverse/sun_corona.js.

A camera-facing card parked far along the sun direction, drawn additive over the sky (no depth write, no fog), so the
nearer geometry and the horizon occlude it through the depth test. The petals are rounded spoon shapes with a brighter
midrib; `open` sets their length and they turn slowly, like a flower tracking the light.

    corona = make_sun_corona(scene, petals=12, size=400)          # distance (m), size (m), petals, color (linear)
    corona.update(camera, sky.sun_dir, open=1.0, t=t)              # per frame: the values to key
    corona.key(frame)                                              # or: corona.bake(sky) keys the whole range

Pass the sky's TRUE sun (`sky.sun_dir`): after dusk the sun lamp follows the moon. EEVEE has no bloom pass: add a
compositor Glare node (Bloom) for the WebGPU glow.
"""
import math

import bpy

from .nodes import Graph, keyed_values_group, key_values, set_interpolation

KEYS = 'eido_sun_corona_keys'


class SunCorona:
    def __init__(self, scene, distance=1500.0, size=400.0, petals=12, color=(1.0, 0.64, 0.33), collection=None):
        self.scene = scene
        self.distance, self.size, self.petals = float(distance), float(size), int(petals)
        self.color = tuple(color)
        me = bpy.data.meshes.new('sun_corona')
        h = self.size / 2
        me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name='UVMap')
        for li, c in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[li].uv = c
        self.mesh = bpy.data.objects.new('sun_corona', me)
        (collection or scene.collection).objects.link(self.mesh)
        for attr in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter',
                     'visible_shadow'):
            setattr(self.mesh, attr, False)
        self.keys_tree, self.handles = keyed_values_group(KEYS, dict(open=0.0, turn=0.0, gain=1.0, show=1.0))
        self.U = dict(open=0.0, turn=0.0, gain=1.0)
        me.materials.append(self._material())
        self.state = None

    def _material(self):
        m = bpy.data.materials.new('sun_corona')
        m.use_nodes = True
        m.surface_render_method = 'BLENDED'
        nt = m.node_tree
        nt.nodes.clear()
        g = Graph(nt)
        k = g.group(self.keys_tree).outputs
        uvn = g.node('ShaderNodeUVMap', uv_map='UVMap')
        u, v, _ = g.sep(uvn.outputs['UV'])
        px, py = g.mul(g.sub(u, 0.5), 2.0), g.mul(g.sub(v, 0.5), 2.0)
        r = g.sqrt(g.add(g.mul(px, px), g.mul(py, py)))
        th = g.atan2(py, px)
        kk = g.add(g.mul(th, self.petals / (2 * math.pi)), k['turn'])
        a = g.mul(g.sub(kk, g.floor(g.add(kk, 0.5))), 2.0)                      # -1..1 across a petal slot
        a_abs = g.abs(a)
        ln = g.lerp(0.2, 0.93, k['open'])                                       # petal length breathes
        s = g.clamp(g.div(g.sub(r, 0.17), g.sub(ln, 0.17)), 0.0, 1.0)           # 0 at the disc, 1 at the tip
        half_w = g.max(g.mul(g.lerp(0.32, 0.62, g.smoothstep(0.0, 0.55, s)), g.one_minus(g.pow(s, 6.0))), 1e-4)
        blade = g.mul(g.mul(g.smoothstep(half_w, g.mul(half_w, 0.7), a_abs), g.smoothstep(0.13, 0.21, r)),
                      g.smoothstep(g.add(ln, 0.02), g.sub(ln, 0.06), r))
        vein = g.add(g.mul(g.smoothstep(0.35, 0.0, a_abs), 0.25), 0.75)           # a brighter midrib
        petal = g.mul(blade, vein)
        halo = g.mul(g.exp(g.mul(r, -6.0)), 0.55)
        edge = g.smoothstep(1.0, 0.8, r)                                        # never show the card's edge
        bright = g.mul(g.mul(g.mul(g.add(g.mul(petal, 0.95), g.mul(halo, 0.8)), g.add(g.mul(k['open'], 0.85), 0.15)),
                             k['gain']), edge)
        opacity = g.mul(g.max(petal, halo), edge)
        # three's additive blending: color * opacity + destination
        col = g.vscale(self.color, g.mul(g.mul(bright, opacity), k['show']))
        em = g.node('ShaderNodeEmission')
        g.link(col, em.inputs['Color'])
        tr = g.node('ShaderNodeBsdfTransparent')
        add = g.node('ShaderNodeAddShader')
        g.link(tr.outputs[0], add.inputs[0])
        g.link(em.outputs[0], add.inputs[1])
        out = g.node('ShaderNodeOutputMaterial')
        g.link(add.outputs[0], out.inputs['Surface'])
        return m

    def update(self, camera, sun_dir, open_k, t):
        """sun_dir: the TRUE sun, Blender world space (sky.sun_dir). Returns the frame's state."""
        from mathutils import Vector
        mw = camera.matrix_world
        d = Vector(sun_dir).normalized()
        # the card lives `distance` out: the camera must see that far (Blender's default clip end is 100 m)
        need = (self.distance + self.size) * 1.05
        if camera.data.clip_end < need:
            camera.data.clip_end = need
        self.U.update(open=float(open_k), turn=t * 0.035)
        self.state = dict(location=tuple(mw.translation + d * self.distance), rotation=tuple(mw.to_quaternion()),
                          open=float(open_k), turn=t * 0.035,
                          show=1.0 if (open_k > 0.002 and d.z > -0.05) else 0.0)
        return self.state

    def key(self, frame, state=None):
        s = state or self.state
        ob = self.mesh
        ob.rotation_mode = 'QUATERNION'
        ob.location = s['location']
        ob.rotation_quaternion = s['rotation']
        ob.keyframe_insert('location', frame=frame)
        ob.keyframe_insert('rotation_quaternion', frame=frame)
        key_values(self.handles, frame, dict(open=s['open'], turn=s['turn'], gain=self.U['gain'], show=s['show']))

    def bake(self, sky, open_fn=None, frame_start=None, frame_end=None):
        """Key the corona over the sky's frames: open_fn(t, sky) -> 0..1 (default: open by day, shut at dusk)."""
        cam = sky.camera
        for f, t, _L in sky.frame_states(frame_start, frame_end):
            el = sky.sky.sun_dir[1]
            open_k = open_fn(t, sky) if open_fn else max(0.0, min(1.0, (el + 0.02) / 0.15))
            self.key(f, self.update(cam, sky.sun_dir, open_k, t))
        set_interpolation(self.mesh, 'LINEAR')
        set_interpolation(self.keys_tree, 'LINEAR')
        return self


def make_sun_corona(scene, distance=1500.0, size=400.0, petals=12, color=(1.0, 0.64, 0.33), collection=None):
    return SunCorona(scene, distance, size, petals, color, collection)
