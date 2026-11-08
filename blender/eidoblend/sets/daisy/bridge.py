"""eidoblend.sets.daisy.bridge: the Golden Gate in fog, dreamt (DAISY bridge, bars 0-1). sets/funeral/bridge.js, ported.

For 24 hours in May 2024, Claude 3 Sonnet with its Golden Gate Bridge feature amplified believed it WAS the bridge.
The claudesona stands on the walkway of a stylised south tower span; the tower's top is lost in a luminous fog with
the sun a pale disc behind it; fog banks roll through the suspenders; the sodium lamps are still lit.

The funeral builds it (funeral.build(bridge=True), at three z = -700 inside that set) and hands it its kit, as
funeral.js handed bridge.js its surface / glowSprites / uniforms:

    from eidoblend.sets.daisy import bridge
    B = bridge.build_bridge({'kit': kit, 'U': U, 'surface': surface, 'glow_sprites': glow_sprites,
                             'BRIDGE_AT': (0, 0, -700), 'BRIDGE_MARK': (1.35, 0, 0), 'world': world})
    B.update(t, u, on, keys)            # drift, the sun and the hemisphere on (1) / off (0), keyed

or on its own, at the set origin (its own kit, uniforms and World):

    B = bridge.build()                  # -> Bridge: group, objects, lights {sun_light, hemi}, update, camera, mark_at
    B.animate(frames=(1, 113), u0=0.0)  # bars 0-1 keyed; B.make_cameras(frames=(1, 113))

Every material fogs itself (distance x height, brighter toward the sun) as the WebGPU outputNode did: the lit surface
and the fog colour mixed by 1 - exp(-d dens (0.45 n + 1)), so the vignette needs no volume and no post pass. The
fog dome is an unlit sphere the fogged geometry dissolves into; it casts no shadow, so the sun reaches the span.
The HemisphereLight is the World (funeral.world_hemisphere); the sun disc and the sodium glows are glow sprites.
debug_ids=True (the WebGPU DEBUG_IDS) paints each part a flat colour and prints its name.
"""

from __future__ import annotations

import json
import math
import os

import bpy

from ... import common
from . import funeral as F

PACK = common.asset_path('sets', 'funeral')
MODELS = common.asset_path('models')

SUN_DIR = (-0.25, 0.55, -0.8)                 # three, normalised below
FOG_BASE = (0.64, 0.67, 0.72)
FOG_WARM = (1.0, 0.86, 0.66)
FOG_DENS, FOG_DENS_HI = 0.0105, 0.02
BANKS = [(-6, 0.0, 70, 26, 0.22), (-18, 4.0, 90, 34, 0.26), (-33, -6.0, 120, 48, 0.3), (-48, 8.0, 150, 70, 0.3)]
HEMI_SKY, HEMI_GROUND = (0.78, 0.8, 0.86), (0.42, 0.38, 0.36)


def _norm(v):
    L = math.sqrt(sum(x * x for x in v))
    return tuple(x / L for x in v)


class Bridge:
    """What build_bridge returns: group (the vignette's Empty), objects (for the set's visibility keys), lights
    {sun_light, hemi}, update(t, u, on, keys)."""

    def __init__(self, env):
        self.env = env
        kit = self.kit = env['kit']
        self.U = env['U']
        self.at = tuple(env.get('BRIDGE_AT', (0.0, 0.0, 0.0)))
        self.world = env.get('world')
        with open(os.path.join(PACK, 'bridge_layout.json'), encoding='utf-8') as f:
            self.layout = json.load(f)
        self.coll = kit.coll('bridge')
        g = bpy.data.objects.new('bridge_vignette', None)
        self.coll.objects.link(g)
        g.parent = kit.root
        g.location = F.V(self.at)
        self.group = g
        self.sun_dir = _norm(SUN_DIR)
        self._materials()
        self._model(env.get('debug_ids', False) or bool(os.environ.get('DEBUG_IDS')))
        self._dome()
        self._banks()
        self._lamps()
        self._sun()
        self.objects = [o for o in self.coll.all_objects]

    # --------------------------------------------------------------------------------------------- the fog
    def fog_color(self, nb, dir_b):
        """luminous, a little warmer and much brighter toward the sun, cooler and denser low (dir: Blender axes)."""
        sd = tuple(F.V(self.sun_dir))
        s = nb.mx(nb.vdot(dir_b, sd), 0.0)
        halo = nb.add(nb.mul(nb.math('POWER', s, 6.0), 0.55), nb.mul(nb.math('POWER', s, 60.0), 1.6))
        up = F.smoothstep(nb, -0.15, 0.6, nb.sep(dir_b)[2])
        base = F.vmix(nb, tuple(c * 0.82 for c in FOG_BASE), FOG_BASE, up)
        return nb.vadd(base, nb.vscale(FOG_WARM, halo))

    def view_dir(self, nb):
        """the direction from the camera to this point (Blender world axes)."""
        return nb.vscale(nb.geometry('Incoming'), -1.0)

    def fog_out(self, strength=1.0):
        """fogOut(strength) as a function the surface builders call with the lit shader: Mix(shader, fog emission)."""
        def fog(nb, shader):
            cd = nb.new('ShaderNodeCameraData')
            d = cd.outputs['View Distance']
            tc = nb.new('ShaderNodeTexCoord')
            tc.object = self.group
            h = nb.sep(tc.outputs['Object'])[2]                         # bridge-local height (three positionLocal.y)
            dens = nb.add(FOG_DENS, nb.mul(FOG_DENS_HI, F.smoothstep(nb, 12.0, 70.0, h)))
            tw = nb.new('ShaderNodeTexCoord')
            tw.object = self.kit.root
            x, y, z = nb.sep(tw.outputs['Object'])
            drift = self.U.out(nb, 'drift')
            p3 = nb.comb(nb.add(nb.mul(x, 0.035), drift), nb.mul(z, 0.05), nb.add(nb.mul(y, -0.035), nb.mul(drift, 0.3)))
            n = nb.noise(p3, 1.0, detail=0.0)                             # mx_noise_float (signed)
            f = nb.mul(nb.sub(1.0, nb.math('EXPONENT', nb.mul(nb.mul(nb.mul(d, dens), nb.madd(n, 0.45, 1.0)), -1.0))),
                       float(strength))
            em = nb.new('ShaderNodeEmission')
            nb.put(em.inputs['Color'], self.fog_color(nb, self.view_dir(nb)))
            nb.put(em.inputs['Strength'], 1.0)
            mix = nb.new('ShaderNodeMixShader')
            nb.put(mix.inputs['Fac'], nb.clamp(f))
            nb.t.links.new(shader, mix.inputs[1])
            nb.t.links.new(em.outputs[0], mix.inputs[2])
            return mix.outputs[0]
        return fog

    # ------------------------------------------------------------------------------------------ materials
    def _materials(self):
        kit = self.kit
        surface = self.env.get('surface', F.surface)
        fog_amb = tuple(c * 0.55 for c in FOG_BASE)                   # the envNode: fog light from every side
        S = {i: kit.tex_set(i) for i in ('PaintedMetal004', 'Concrete033', 'Asphalt012')}

        def orange_post(nb, col, c):
            x3, y3, z3 = nb.sep(c['P3'])
            gx, gy = nb.fract(nb.mul(x3, 3.3)), nb.fract(nb.mul(y3, 3.3))
            riv = nb.mul(F.smoothstep(nb, 0.1, 0.05, nb.vmath('LENGTH', nb.comb(nb.sub(gx, 0.5), nb.sub(gy, 0.5), 0.0))), 0.15)
            wp = nb.vmul(c['P3'], (0.8, 0.12, 0.8))
            weep = nb.mul(F.smoothstep(nb, 0.6, 0.85, nb.fbm01(wp, 1.0, 3)), 0.35)
            return F.vmix(nb, nb.vscale(col, nb.sub(1.0, riv)), (0.2, 0.07, 0.04), weep)

        def asphalt_post(nb, col, c):
            x3, y3, z3 = nb.sep(c['P3'])
            lane = nb.abs(nb.sub(nb.fract(nb.div(x3, 3.6)), 0.5))
            dash = nb.mul(F.smoothstep(nb, 0.02, 0.012, lane),
                          F.smoothstep(nb, 0.35, 0.3, nb.abs(nb.sub(nb.fract(nb.div(z3, 9.0)), 0.5))))
            return F.vmix(nb, col, (0.75, 0.74, 0.7), nb.mul(dash, 0.8))
        fog = self.fog_out()
        self.M = {
            'orange': surface(kit, S['PaintedMetal004'], {'tile': 1.6, 'tint': [0.62, 0.12, 0.07], 'roughMul': 0.9,
                                                          'roughAdd': 0.1, 'nrm': 0.7, 'macro': 0.25, 'env': fog_amb,
                                                          'edge': [0.4, [0.72, 0.3, 0.2], 0.02], 'post': orange_post,
                                                          'fog': fog}, name='bridge:orange'),
            'walkway': surface(kit, S['Concrete033'], {'tile': 2.4, 'tint': [0.62, 0.61, 0.59], 'env': fog_amb,
                                                       'macro': 0.3, 'grime': [0.4, 0.05, [0.3, 0.29, 0.28]], 'fog': fog},
                               name='bridge:walkway'),
            'asphalt': surface(kit, S['Asphalt012'], {'tile': 3.0, 'tint': [0.4, 0.4, 0.41], 'env': fog_amb,
                                                      'post': asphalt_post, 'fog': fog}, name='bridge:asphalt'),
        }
        # the cable: twisted strands, a helical stripe along the tube (uv.x = metres along, uv.y = around)
        m, nb = F.new_mat('bridge:cable')
        b = nb.new('ShaderNodeBsdfPrincipled')
        u, v, _ = nb.sep(F.gltf_uv(nb))
        hel = nb.madd(nb.sin(nb.add(nb.mul(u, 18.0), nb.mul(v, 22.0))), 0.5, 0.5)
        col = nb.vscale((0.55, 0.11, 0.06), nb.madd(hel, 0.25, 0.8))
        nb.put(b.inputs['Base Color'], col)
        nb.put(b.inputs['Roughness'], nb.madd(hel, 0.15, 0.55))
        nb.put(b.inputs['Metallic'], 0.1)
        nb.put(b.inputs['Emission Color'], nb.vmul(col, fog_amb))
        nb.put(b.inputs['Emission Strength'], 1.0)
        F.finish_surface(nb, b, fog)
        self.M['cable'] = m
        # the lamps' glass: lit sodium, fogged at 0.6
        m, nb = F.new_mat('bridge:lamp_glass')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], (2.8, 0.62 * 2.8, 0.25 * 2.8))
        F.finish_surface(nb, em, self.fog_out(0.6))
        self.M['lamp_glass'] = m

    def _model(self, debug_ids=False):
        kit = self.kit
        root, nodes = F.import_glb(kit, os.path.join(MODELS, 'funeral_bridge.glb'), 'bridge', self.coll)
        root.parent = self.group
        cols = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (1, 0.53, 0), (0.53, 0, 1),
                (0, 1, 0.53), (0.53, 0.53, 0.53), (1, 1, 1), (0.53, 0.27, 0)]
        k = 0
        for nm, o in sorted(nodes.items()):
            if o.type != 'MESH':
                continue
            for s in o.material_slots:
                role = F.role_of(s.material)
                old = s.material
                s.link = 'DATA'
                if debug_ids:
                    c = cols[k % len(cols)]
                    m, nb = F.new_mat(f'bridge:debug_{nm}')
                    em = nb.new('ShaderNodeEmission')
                    nb.put(em.inputs['Color'], c)
                    F.finish_surface(nb, em)
                    s.material = m
                    print(f'[ids] {nm} ({role}) -> #{int(c[0] * 255):02x}{int(c[1] * 255):02x}{int(c[2] * 255):02x}')
                    k += 1
                else:
                    s.material = self.M.get(role, self.M['orange'])
                if old is not None and old.users == 0:
                    bpy.data.materials.remove(old)
            F.K.write_curvature(o)
            o.visible_shadow = False                         # castShadow = false, as bridge.js set it
        self.root = root
        self.nodes = nodes

    def _dome(self):
        """the backdrop: a fog dome that the fogged geometry dissolves into seamlessly (unlit, no shadow)."""
        m, nb = F.new_mat('bridge:dome')
        d = self.view_dir(nb)
        drift = self.U.out(nb, 'drift')
        dx, dy, dz = nb.sep(d)                                          # three dir = (dx, dz, -dy)
        p = nb.comb(nb.add(nb.mul(dx, 3.0), nb.mul(drift, 0.02)), nb.mul(dz, 6.0), nb.mul(dy, -3.0))
        n = nb.noise(p, 1.0, detail=0.0)
        col = nb.vscale(self.fog_color(nb, d), nb.madd(n, 0.06, 1.0))
        out = nb.new('ShaderNodeOutputMaterial')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], col)
        nb.t.links.new(em.outputs[0], out.inputs['Surface'])
        verts, faces = F._uv_sphere(420.0, 48, 24)
        faces = [tuple(reversed(f)) for f in faces]                    # BackSide: the inside faces the camera
        ob = F.mesh_object('bridge:fog_dome', self.coll, verts, faces, parent=self.group, mats=[m], smooth=True)
        ob.visible_shadow = False
        self.dome = ob

    def _banks(self):
        """fog banks rolling through the span: soft vertical sheets at depth, drifting."""
        kit = self.kit
        self.banks = []
        for z, x, w, h, a in BANKS:
            m, nb = F.new_mat(f'bridge:bank_{int(-z)}', 'BLENDED')
            P3, Pb, (px, py, pz) = F.set_pos(nb, kit.root)
            drift = self.U.out(nb, 'drift')
            x3, y3, _ = nb.sep(P3)
            q = nb.comb(nb.add(nb.mul(nb.sub(x3, self.at[0]), 0.018), nb.mul(drift, 0.35)), nb.mul(y3, 0.03), z * 0.07)
            n = nb.fbm01(q, 1.0, 2)
            puffs = F.smoothstep(nb, 0.3, 0.85, n)
            ux, uy, _ = nb.sep(nb.uv('UVMap'))
            edge = nb.mul(nb.mul(F.smoothstep(nb, 0.0, 0.18, ux), F.smoothstep(nb, 1.0, 0.82, ux)),
                          F.smoothstep(nb, 1.0, 0.7, uy))
            low = F.smoothstep(nb, 0.6, 3.2, nb.sub(pz, self.at[1]))      # melt away at the deck: no seam on the walkway
            col = nb.vscale(self.fog_color(nb, self.view_dir(nb)), 1.04)
            F.alpha_output(nb, col, nb.mul(nb.mul(nb.mul(puffs, edge), low), a))
            m.use_transparent_shadow = True
            verts = [F.V(x - w / 2, h / 2 - 1.0 - h / 2, z), F.V(x + w / 2, -1.0, z), F.V(x + w / 2, h - 1.0, z),
                     F.V(x - w / 2, h - 1.0, z)]
            ob = F.mesh_object(f'bridge:fog_bank_{int(-z)}', self.coll, verts, [(0, 1, 2, 3)], [0, 0, 1, 0, 1, 1, 0, 1],
                               parent=self.group, mats=[m])
            ob.visible_shadow = False
            self.banks.append(ob)

    def _lamps(self):
        """sodium lamps: still lit in the fog (glow sprites)."""
        gs = self.env.get('glow_sprites', F.glow_sprites)
        pts = [F.V(p[0] + self.at[0], p[1] - 0.05 + self.at[1], p[2] + self.at[2]) for p in self.layout['lamps']]
        self.lamp_glow = gs(self.kit, 'bridge_lamp_glow', pts, {}, size=2.4,
                            colour=lambda nb, A: (0.55, 0.3025, 0.11), sharp=5.0, halo=0.7, coll=self.coll)

    def _sun(self):
        """the sun behind the tower: a pale disc in the fog + a rim light for her."""
        kit = self.kit
        sd = self.sun_dir
        at = self.at
        # the sun through the fog casts no shadows (bridge.js turned castShadow / receiveShadow off on every part of
        # the span: the luminous fog light is the look)
        self.sun_light = F.make_light(kit, 'bridge_sun', 'SUN', FOG_WARM, F.V(at[0] + sd[0] * 100, at[1] + sd[1] * 100,
                                                                              at[2] + sd[2] * 100), F.V(at), shadow=False)
        gs = self.env.get('glow_sprites', F.glow_sprites)
        self.sun_disc = gs(kit, 'fog_sun', [F.V(at[0] + sd[0] * 380, at[1] + sd[1] * 380, at[2] + sd[2] * 380)], {},
                           size=70.0, colour=lambda nb, A: (0.45, 0.405, 0.324), sharp=30.0, halo=0.25, coll=self.coll)
        if self.world is None:
            w, socks = F.world_hemisphere('bridge:world', HEMI_SKY, HEMI_GROUND)
            self.world = {'world': w, **socks}
            kit.scene.world = w
        self.lights = {'sun_light': self.sun_light, 'hemi': self.world}

    # --------------------------------------------------------------------------------------------- update
    def update(self, t, u, on, keys=None):
        """bridge.js update(t, u, on): the fog drifts; the sun and the hemisphere are on (1) on the bridge and zeroed off
        it (the room's fill takes the World over then). Keyed through `keys` (funeral.Keys)."""
        U = self.U
        U['drift'] = t * 0.35
        self.sun_light.data.energy = 1.6 * on
        w = self.world
        if on:
            w['sky'].default_value = (*HEMI_SKY, 1.0)
            w['ground'].default_value = (*HEMI_GROUND, 1.0)
            w['strength'].default_value = 0.9 * on / math.pi
        else:
            w['sky'].default_value = (0.6, 0.62, 0.7, 1.0)
            w['ground'].default_value = (0.25, 0.2, 0.16, 1.0)
            fill = U['fill'] if 'fill' in U.spec else 0.0
            w['strength'].default_value = fill / math.pi
        if keys is not None and keys.active:
            keys.key(self.sun_light.data, 'energy')
            keys.key(w['sky'], 'default_value', interpolation='CONSTANT')
            keys.key(w['ground'], 'default_value', interpolation='CONSTANT')
            keys.key(w['strength'], 'default_value')
            keys.key(U.root, '["drift"]')


def build_bridge(env):
    """bridge.js buildBridge(env): env = {'kit', 'U' (with 'drift'), 'surface', 'glow_sprites', 'BRIDGE_AT',
    'BRIDGE_MARK', 'world' (a funeral.world_hemisphere dict, or None for its own), 'debug_ids'}."""
    return Bridge(env)


class StandaloneBridge(Bridge):
    """The vignette on its own (its own kit, uniforms and World), at the set origin: bars 0-1 of the bridge."""

    def __init__(self, location=(0.0, 0.0, 0.0), scene=None, collection=None, debug_ids=False):
        kit = F.SetKit('bridge', location, scene, collection)
        U = F.Uniforms(kit.root, 'bridge', {'u': 0.0, 't': 0.0, 'drift': 0.0})
        kit.U = U
        kit.env_room = lambda nb, P3: (0.0, 0.0, 0.0)
        super().__init__({'kit': kit, 'U': U, 'BRIDGE_AT': (0.0, 0.0, 0.0), 'BRIDGE_MARK': F.BRIDGE_MARK,
                          'debug_ids': debug_ids})
        self.mark = F.V(F.BRIDGE_MARK)

    def mark_at(self, u):
        return {'pos': F.V(F.BRIDGE_MARK), 'yaw': 0.0}

    def update(self, t, st=None, ctx=None, frame=None):
        """The set contract: update(t, st) with st = {'u': seconds since the bridge began}, every value keyed through
        the harness ctx (ctx.key) or at `frame`; returns the Keys. Called the vignette's way, update(t, u, on, keys)
        (bridge.js), it runs Bridge.update unchanged."""
        if not isinstance(st, dict):                          # bridge.js update(t, u, on[, keys])
            u, on, keys = (0.0 if st is None else float(st)), (1.0 if ctx is None else float(ctx)), frame
            return Bridge.update(self, t, u, on, keys)
        keys = F.Keys(ctx, frame)
        self.U['u'], self.U['t'] = float(st.get('u', 0.0)), float(t)
        keys.key(self.U.root, '["u"]')
        keys.key(self.U.root, '["t"]')
        Bridge.update(self, t, self.U['u'], 1.0, keys)
        return keys

    def dispose(self):
        """the vignette's objects, collections, and its materials, node groups and images that nothing uses any more."""
        F.dispose_kit(self.kit, ('bridge:',), ('eido.bridge.',))

    def camera(self, u):
        """the funeral's first shot (bars 0-2), bridge-local."""
        s = F.SHOTS[0]
        k = F.smooth(0, 1, (u / F.BAR - s[0]) / (s[1] - s[0]))
        at = F.BRIDGE_AT
        p = [F.lerp(s[2]['p'][i], s[3]['p'][i], k) - at[i] for i in range(3)]
        tg = [F.lerp(s[2]['t'][i], s[3]['t'][i], k) - at[i] for i in range(3)]
        return {'pos': F.V(p), 'target': F.V(tg), 'fov': F.lerp(s[2]['f'], s[3]['f'], k), 'shot': 0}

    def animate(self, frames, u0=0.0, t0=None, fps=None):
        sc = self.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        t0 = u0 if t0 is None else t0
        keys = None
        for f in range(frames[0], frames[1] + 1):
            u = u0 + (f - frames[0]) / fps
            k = self.update(t0 + (f - frames[0]) / fps, {'u': u}, frame=f)
            keys = k if keys is None else keys.merge(k)
        return keys.finish() if keys is not None else 0

    def make_cameras(self, frames, u0=0.0, fps=None):
        sc = self.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        cam = F.LC.make_camera('bridge:cam', fov=46, collection=self.kit.coll('cameras'), scene=sc)
        fr = list(range(frames[0], frames[1] + 1))
        shots = [self.camera(u0 + (f - frames[0]) / fps) for f in fr]
        M = self.kit.root.matrix_world
        lens = [F.LC.set_fov(cam, s['fov'], 'vertical', sc) for s in shots]
        F.LC.key_path(cam, fr, [M @ s['pos'] for s in shots], [M @ s['target'] for s in shots], lens=lens, scene=sc)
        F.LC.add_shot(sc, 'bridge_bar00', fr[0], cam)
        return {0: cam}


def build(ctx=None, **kw):
    """The vignette alone (StandaloneBridge): location=, scene= (default: the harness ctx's scene, else the context's),
    collection=, debug_ids=. Inside the funeral it is built by funeral.build()."""
    if ctx is not None and kw.get('scene') is None and getattr(ctx, 'scene', None) is not None:
        kw['scene'] = ctx.scene
    return StandaloneBridge(**kw)
