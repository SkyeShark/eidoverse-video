"""nuclear_explosion: the SDF mushroom-cloud raymarcher (eidoverse/effects_tsl/nuclear_explosion.js) as a real volume.

In WebGPU it was a world-layer post effect, NuclearExplosionFX.applyTo({scene, camera, opts}): its pre-SSR hook
marched every pixel's view ray through the cloud's SDF (an entry march to the surface, then a volume march at
0.08-unit strides, density x 0.22 per stride) and composited the cloud over the frame, clamped to the scene depth; a
second hook marched the reflected rays of metal surfaces through it, and a third blurred those by roughness. In
Blender the cloud is in the scene: two Volume objects (the wide, thin base surge and the tall mushroom over it, so no
voxel is spent on the air round the cap) hold the same density, heat and palette per frame, EEVEE draws them with
depth, fog and other volumes, reflections and refractions see them, and keyed lamps carry their glow onto the
ground (light_from_emission: EEVEE's volume emission lights no surface).

    from eidoblend.sdf import nuclear_explosion as NX
    nuke = NX.apply_to(scene, camera, {'origin': [0, 0, -120], 'scale': 3.0, 'time_offset': 2.0},
                       cache_dir=os.path.join(out, 'nuke_cache'))
    nuke.bake(1, 480)                    # one .vdb per volume per frame + the keyed glow lights
    nuke.uniforms['opacity'] = 0.5       # (a socket, keyable: nuke.key_opacity(frame, value))

The anatomy and lifecycle are the original's, unchanged: cap, stem, trail, base-surge torus and ground pad fused by
sminCubic, noise at positions advected round the cap's and the surge's vortex rings (the original's If-gated rolls),
a 4-octave density cascade x the SDF-depth falloff, the late dispersal that dissolves wisps first, heat from the
distance to the core cooling over the loop, the near-black smoke band under the fire ramp. The base surge is NOT
capped (EXAMPLES['nuclear_blast'] caps it to fit its box): it runs to 20 x scale units, the 2 km ring.

Options (the effect's, snake_case; the camelCase spelling is accepted):
    origin         [x, y, z] ground zero in three's axes (y up) -> the volumes' Blender location (x, -z, y)
    scale          size multiplier (1 unit ~ 100 m: scale 1 is a ~900 m cap and a ~2 km surge ring)
    time_offset    phase offset in seconds (staggers several blasts)
    loop_seconds   cycle period (20)
    opacity        the effect's mix over the frame -> a keyable multiplier on the media's density and emission, and
                   (each lamp's energy is a driver over it) on the glow lamps
    vol_steps      the volume march's step count -> the reference march's (the grids hold the whole cloud)
    surf_steps, reflect_steps, max_t, width, height: the screen march's budgets and size (see OPTION_NOTES)
    disable_for_perf_test   the volumes are built hidden and nothing is baked (the effect's no-hook mode)
Extra here: quality ('fast' | 'balanced' | 'high': voxel 0.16 / 0.08 / 0.055 original units, x scale), voxel,
cache_dir, name, lights (lamps per frame from the emission, 3: cap, stem, surge), light_scale, bake ((fs, fe) or
'scene': bake now).
"""

from __future__ import annotations

from .examples_volumes import _NUKE_COMMON, fit_volume_range, light_from_emission

# the original's If-gated advection (nuclear_explosion.js advectSamplePos), its density threshold (sampleDensity),
# heat (densityToHeat) and its volume march's per-stride weight (0.22 per 0.08 world units)
_NX_EXTRA = _NUKE_COMMON + r"""
vec3 nxAdvect(vec3 p, NukeAnim A) {
    float radialDist = length(p.xz);
    float torusW = exp(abs(radialDist - A.surgeR) * -0.4) * exp(abs(p.y - 1.0) * -0.4);
    float capW = exp(abs(p.y - A.capY) * -0.18) * exp(max(radialDist - A.capR, 0.0) * -0.3);
    vec3 advected = p;
    // BASE SURGE rolling
    if (torusW > 0.01 && radialDist > 0.5) {
        vec2 outward = normalize(p.xz);
        vec2 rolled = nukeRot2(vec2(radialDist - A.surgeR, p.y - 1.0), uTime * 0.25);
        vec2 newXZ = outward * (rolled.x + A.surgeR);
        advected = mix(advected, vec3(newXZ.x, rolled.y + 1.0, newXZ.y), torusW);
    }
    // CAP rolling
    if (capW > 0.005 && radialDist > 0.3) {
        vec2 outward = normalize(p.xz);
        float tubeRingR = A.capR * 0.65;
        vec2 rolled = nukeRot2(vec2(radialDist - tubeRingR, p.y - A.capY), uTime * 0.35);
        vec2 newXZ = outward * (rolled.x + tubeRingR);
        advected = mix(advected, vec3(newXZ.x, rolled.y + A.capY, newXZ.y), capW);
    }
    return advected;
}
"""

_NX_SAMPLE = r"""
SdfSample sample(vec3 pw) {
    // pw: the point relative to ground zero, world units (three axes); p: the original's local units
    float S = uScale;
    vec3 p = pw / S;
    NukeAnim A = nukeAnim(fract((uTime + uTimeOffset) / uLoopSeconds), 1e9);
    float dLocal = nukeMap(p, A);
    float d = dLocal * S;                  // the marcher's world units
    float density = 0.0;
    float falloff = clamp(dLocal / -0.8, 0.0, 1.0);
    if (falloff > 0.0) {
        density = nukeShape(falloff * nukeCascade(nxAdvect(p, A)), p, A);
    }
    float coreTerm = exp(length(p - vec3(0.0, A.capY * 0.85, 0.0)) * -0.18);
    float heat = clamp(density * coreTerm * A.coolFactor + coreTerm * 0.6 * A.coolFactor, 0.0, 1.0);
    vec3 col = nukeHeatToColor(heat);
    float alpha = (d < 0.2 && density > 0.001) ? density * 0.22 : 0.0;
    float stp = d < 0.2 ? 0.08 : max(d * 0.6, 0.15);
    return sdfSample(col, alpha, stp);
}"""

DEFAULTS = dict(origin=(0.0, 0.0, 0.0), scale=1.0, time_offset=0.0, loop_seconds=20.0, max_t=80.0, surf_steps=64,
                vol_steps=96, reflect_steps=48, opacity=1.0, width=None, height=None, disable_for_perf_test=False)
EXTRA = dict(quality='balanced', voxel=None, cache_dir='//sdf_cache', name='nuclear_explosion', lights=3,
             light_scale=1.0, bake=None, split=True)
_CAMEL = {'timeOffset': 'time_offset', 'loopSeconds': 'loop_seconds', 'maxT': 'max_t', 'surfSteps': 'surf_steps',
          'volSteps': 'vol_steps', 'reflectSteps': 'reflect_steps', 'disableForPerfTest': 'disable_for_perf_test'}
QUALITY_VOXEL = {'fast': 0.16, 'balanced': 0.08, 'high': 0.055}

# what each screen-effect option became (an option with no Blender counterpart is accepted and said so)
OPTION_NOTES = {
    'max_t': "the screen march's longest view ray (80 units). The cloud is in the scene, drawn at any distance; "
             "EEVEE's froxel range is fitted round it instead (fit_volume_range)",
    'surf_steps': "the entry march to the SDF before the volume march; the reference march starts at the grids' "
                  "box instead, and EEVEE needs none",
    'reflect_steps': "the metal-reflection march; reflections of the cloud are EEVEE's own (ray traced / probes)",
    'width': "the screen pass's resolution (iResolution, unused by its shader): a volume has none",
    'height': "the screen pass's resolution (iResolution, unused by its shader): a volume has none",
}

# the cloud's extent over the whole loop, in original units: the surge ring runs to r = 20 + its tube (20.6), and
# rises at most 3.5 high; the mushroom (cap 5.1 radius at y 9, squashed 0.78) tops out at 13.2
RING_R = 20.7
SPLIT_Y = 3.6
CAP_R = 5.5
TOP_Y = 13.3


def _opts(opts, kw):
    o = dict(DEFAULTS)
    o.update(EXTRA)
    given = {_CAMEL.get(k, k): v for k, v in dict(opts or {}, **kw).items()}
    unknown = set(given) - set(o)
    if unknown:
        raise KeyError(f'nuclear_explosion: unknown options {sorted(unknown)} (has {sorted(o)})')
    o.update(given)
    return o


class _Uniforms:
    """fx.uniforms: the effect's uniforms (time, origin, scale, time_offset, loop_seconds, opacity, ...). Reading
    gives the current value; time_offset / loop_seconds / time set the shader's (bake again to see them); origin
    moves the volumes; opacity is the material's socket (keyable)."""

    def __init__(self, fx):
        self._fx = fx

    def __getitem__(self, k):
        k = _CAMEL.get(k, k)
        fx = self._fx
        if k == 'opacity':
            return fx.opacity_socket.default_value if fx.opacity_socket is not None else fx.o['opacity']
        if k == 'origin':
            return tuple(fx.o['origin'])
        if k in ('time', 'time_offset', 'loop_seconds', 'scale'):
            name = {'time': 'uTime', 'time_offset': 'uTimeOffset', 'loop_seconds': 'uLoopSeconds',
                    'scale': 'uScale'}[k]
            return fx.volumes[0].program.get_uniform(name)
        return fx.o[k]

    def __setitem__(self, k, v):
        k = _CAMEL.get(k, k)
        fx = self._fx
        if k == 'opacity':
            fx.set_opacity(v)
        elif k == 'origin':
            fx.o['origin'] = tuple(float(x) for x in v)
            for vol in fx.volumes:
                vol.object.location = _blender_origin(fx.o['origin'])
        elif k in ('time', 'time_offset', 'loop_seconds'):
            name = {'time': 'uTime', 'time_offset': 'uTimeOffset', 'loop_seconds': 'uLoopSeconds'}[k]
            fx.o[k] = float(v)
            for vol in fx.volumes:
                vol.program.set_uniform(name, float(v))
        elif k == 'scale':
            raise ValueError('nuclear_explosion: scale sets the size of the volumes\' grids; pass it to apply_to')
        else:
            raise KeyError(f'nuclear_explosion: no uniform {k!r}')

    def keys(self):
        return ['time', 'origin', 'scale', 'time_offset', 'loop_seconds', 'opacity']

    def __repr__(self):
        return 'NuclearExplosion.uniforms(%s)' % ', '.join(f'{k}={self[k]!r}' for k in self.keys())


def _blender_origin(o3):
    x, y, z = (float(v) for v in o3)
    return (x, -z, y)


class NuclearExplosion:
    """What apply_to returns: .volumes (SdfVolume: [surge, mushroom], or one), .objects, .lights (EmissionLights
    per volume), .uniforms, update(t) (the frame at t, the effect's update), bake(fs, fe), set_opacity(v),
    key_opacity(frame, v), raymarch_reference(camera, ...), remove()."""

    def __init__(self, scene, camera, o):
        from .volume import create_sdf_volume
        self.scene = scene
        self.camera = camera
        self.o = o
        S = float(o['scale'])
        vox = float(o['voxel']) if o['voxel'] else QUALITY_VOXEL.get(o['quality'], 0.08) * S
        unif = {'uScale': S, 'uTimeOffset': float(o['time_offset']), 'uLoopSeconds': float(o['loop_seconds'])}
        boxes = ([('surge', [-RING_R, 0.0, -RING_R], [RING_R, SPLIT_Y, RING_R]),
                  ('mushroom', [-CAP_R, SPLIT_Y, -CAP_R], [CAP_R, TOP_Y, CAP_R])] if o['split']
                 else [('cloud', [-RING_R, 0.0, -RING_R], [RING_R, TOP_Y, RING_R])])
        self.volumes = []
        for part, lo, hi in boxes:
            vol = create_sdf_volume(
                name=f"{o['name']}_{part}", sample=_NX_SAMPLE, extra=_NX_EXTRA, uniforms=dict(unif),
                bounds={'min': [x * S for x in lo], 'max': [x * S for x in hi]}, steps=int(o['vol_steps']),
                voxel=vox, cache_dir=o['cache_dir'], location=_blender_origin(o['origin']), scene=scene,
                animated=True, build=False)
            vol.object['nuclear_explosion'] = part
            vol.part = part
            self.volumes.append(vol)
        self.objects = [v.object for v in self.volumes]
        self.lights = []
        self.opacity_socket = None
        self.uniforms = _Uniforms(self)
        for k, why in OPTION_NOTES.items():
            if k in o.get('_given', ()):
                print(f'[nuclear_explosion] option {k!r}: {why}', flush=True)
        if o['disable_for_perf_test']:
            for ob in self.objects:
                ob.hide_render = True
                ob.hide_viewport = True

    # ---------------------------------------------------------------------------------------------- building --
    def update(self, t, log=print):
        """The effect's update(t): the cloud at time t (seconds), as a still in every volume, with its lights."""
        if self.o['disable_for_perf_test']:
            for vol in self.volumes:
                vol.program.set_uniform('uTime', float(t))
            return self
        from .examples_volumes import build_still
        for vol in self.volumes:
            build_still(vol, float(t), log=log)
        self._finish(None, log)
        return self

    def bake(self, frame_start=None, frame_end=None, step=1, log=print):
        """One .vdb per volume per frame (t = (frame - frame_start) / fps; the effect's own phase is time_offset),
        then the glow lights keyed from them, and the froxel range fitted to the camera over the range."""
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        if self.o['disable_for_perf_test']:
            return self
        for vol in self.volumes:
            vol.bake(fs, fe, step=step, log=log)
        self._finish(range(fs, fe + 1), log)
        return self

    def _finish(self, frames, log):
        for rig in self.lights:
            rig.remove()
        self.lights = []
        n = int(self.o['lights'] or 0)
        if n > 0:
            per = {'surge': max(1, n - 2), 'mushroom': min(2, n), 'cloud': n}
            for vol in self.volumes:
                # a still reads the file the Volume shows ([None]), even after an earlier bake of the same volume
                self.lights.append(light_from_emission(vol, frames=list(frames) if frames is not None else [None],
                                                       count=per.get(vol.part, 1),
                                                       energy_scale=float(self.o['light_scale']), log=log))
        self._opacity_nodes()
        # the froxel range round the cloud and every other volume of the scene (a first blast, the fog), from the
        # camera that renders each frame: the scene's camera switched by timeline markers when there are some (the
        # cloud must render through every cut), else the effect's camera
        cuts = any(m.camera is not None for m in self.scene.timeline_markers)
        if self.camera is not None or cuts:
            fit_volume_range(self.scene, None if cuts else self.camera, self.volumes,
                             frames=list(frames) if frames is not None else [self.scene.frame_current])

    def _opacity_group(self):
        """The effect's one opacity: a shader node group holding a Value node, used by every volume's material, so
        one socket (the registry's uniform, keyable) drives them all."""
        import bpy
        g = getattr(self, '_opacity_tree', None)
        if g is None:
            g = bpy.data.node_groups.new(f"{self.o['name']}_opacity", 'ShaderNodeTree')
            g.interface.new_socket(name='Opacity', in_out='OUTPUT', socket_type='NodeSocketFloat')
            val = g.nodes.new('ShaderNodeValue')
            val.name = val.label = 'opacity'
            val.outputs[0].default_value = float(self.o['opacity'])
            out = g.nodes.new('NodeGroupOutput')
            out.location = (300, 0)
            g.links.new(val.outputs[0], out.inputs[0])
            self._opacity_tree = g
        return g

    def _opacity_nodes(self):
        """The effect's opacity (mix(scene, scene x (1 - a) + cloud, opacity)) on the media: the shared opacity group
        multiplies every volume's density and emission (and the glow lights' energy follows it). Exact for thin
        smoke; the dense core fades later than the screen mix did."""
        g = self._opacity_group()
        for vol in self.volumes:
            mat = vol.material
            if mat is None:
                continue
            nt = mat.node_tree
            if 'nx_opacity' in nt.nodes:
                continue
            pv = next(n for n in nt.nodes if n.type == 'PRINCIPLED_VOLUME')
            grp = nt.nodes.new('ShaderNodeGroup')
            grp.node_tree = g
            grp.name = grp.label = 'nx_opacity'
            grp.location = (-900, 400)
            dens_link = pv.inputs['Density'].links[0] if pv.inputs['Density'].is_linked else None
            md = nt.nodes.new('ShaderNodeMath')
            md.operation = 'MULTIPLY'
            md.location = (-200, 300)
            if dens_link is not None:
                nt.links.new(dens_link.from_socket, md.inputs[0])
            else:
                md.inputs[0].default_value = pv.inputs['Density'].default_value
            nt.links.new(grp.outputs[0], md.inputs[1])
            nt.links.new(md.outputs[0], pv.inputs['Density'])
            me = nt.nodes.new('ShaderNodeMath')
            me.operation = 'MULTIPLY'
            me.location = (-200, 100)
            me.inputs[0].default_value = pv.inputs['Emission Strength'].default_value
            nt.links.new(grp.outputs[0], me.inputs[1])
            nt.links.new(me.outputs[0], pv.inputs['Emission Strength'])
        self.opacity_socket = g.nodes['opacity'].outputs[0]
        self._drive_lights()
        return self.opacity_socket

    def _drive_lights(self):
        """Each glow light's energy = its power (the keyed custom property 'glow_power', light_from_emission's
        watts per frame) x the effect's opacity, by a driver reading the shared opacity socket. However the opacity is
        set or keyed (set_opacity, key_opacity, the post registry's FX.key on the socket it hands out), the lights fade
        with the media, in the session and in the saved file (a simple-expression driver: no script needs to run)."""
        from bpy_extras import anim_utils

        from .examples_volumes import _linear
        g = self._opacity_group()
        for rig in self.lights:
            for lo in rig.lights:
                ld = lo.data
                ad = ld.animation_data
                if ad is not None and any(d.data_path == 'energy' for d in ad.drivers):
                    continue
                keys = []
                if ad is not None and ad.action is not None:
                    try:
                        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
                    except (AttributeError, TypeError, RuntimeError):
                        cb = None
                    fc = cb.fcurves.find('energy') if cb is not None else None
                    if fc is not None:
                        keys = [(float(kp.co[0]), float(kp.co[1])) for kp in fc.keyframe_points]
                        cb.fcurves.remove(fc)
                ld['glow_power'] = keys[0][1] if keys else float(ld.energy)
                for f, v in keys:
                    ld['glow_power'] = v
                    ld.keyframe_insert('["glow_power"]', frame=f)
                _linear(ld)
                drv = ld.driver_add('energy').driver
                drv.type = 'SCRIPTED'
                drv.expression = 'power * opacity'
                for vname, id_type, idb, path in (('power', 'LIGHT', ld, '["glow_power"]'),
                                                  ('opacity', 'NODETREE', g,
                                                   'nodes["opacity"].outputs[0].default_value')):
                    var = drv.variables.new()
                    var.name = vname
                    var.type = 'SINGLE_PROP'
                    var.targets[0].id_type = id_type
                    var.targets[0].id = idb
                    var.targets[0].data_path = path

    def set_opacity(self, v):
        """The effect's opacity uniform: the media's density and emission and (by their drivers) the lights' energy
        x v."""
        self.o['opacity'] = float(v)
        self._opacity_group().nodes['opacity'].outputs[0].default_value = float(v)
        return self

    def key_opacity(self, frame, value):
        """Key the opacity at a frame (LINEAR) on the shared opacity group: a fade in / out of the whole effect, the
        media and (by their drivers) the glow lights together. A key set on fx.opacity_socket any other way, e.g.
        by the post registry's FX.key, does the same."""
        from .examples_volumes import _linear
        self.o['opacity'] = float(value)
        g = self._opacity_group()
        sock = g.nodes['opacity'].outputs[0]
        sock.default_value = float(value)
        sock.keyframe_insert('default_value', frame=frame)
        _linear(g)
        return self

    def sync_lights(self):
        """The lights follow the opacity by drivers, so there is nothing to re-key; kept for code written before
        (it makes sure every light has its driver)."""
        self._drive_lights()
        return self

    # ------------------------------------------------------------------------------------------------ review --
    def raymarch_reference(self, camera, width=480, height=270, samples=2, t=None):
        """The effect's own march of the cloud from a Blender camera (premultiplied linear (H, W, 4)): each volume's
        reference march, composited front to back by the camera distance of its box centre."""
        from mathutils import Vector
        cam = camera.matrix_world.translation
        order = sorted(self.volumes, key=lambda v: (v.object.matrix_world @ Vector(0.5 * (v.lo + v.hi)) - cam).length)
        out = None
        for vol in order:
            img = vol.raymarch_reference(camera, width, height, samples, t=t)
            out = img if out is None else out + img * (1.0 - out[..., 3:4])
        return out

    def remove(self):
        """Take the effect out of the scene: its volumes, their materials and lights."""
        import bpy
        for rig in self.lights:
            rig.remove()
        self.lights = []
        for vol in self.volumes:
            ob = vol.object
            vd = ob.data
            mats = [m for m in vd.materials if m is not None]
            bpy.data.objects.remove(ob, do_unlink=True)
            if vd.users == 0:
                bpy.data.volumes.remove(vd)
            for m in mats:
                if m.users == 0:
                    bpy.data.materials.remove(m)
        g = getattr(self, '_opacity_tree', None)
        if g is not None and g.users == 0:
            bpy.data.node_groups.remove(g)
        self._opacity_tree = None
        self.opacity_socket = None
        self.volumes = []
        self.objects = []


def apply_to(scene=None, camera=None, opts=None, **kw):
    """NuclearExplosionFX.applyTo({scene, camera, opts}): the mushroom cloud as volumes in the scene. scene and
    camera may come inside opts, as the engine's args did ({'scene': ..., 'camera': ..., 'opts': {...}}). Builds the
    frame at the scene's current time unless bake=(fs, fe) or 'scene' bakes a range now. Returns NuclearExplosion."""
    import bpy
    if isinstance(scene, dict):                       # applyTo({scene, camera, opts}) in one dict
        args = dict(scene)
        scene, camera = args.pop('scene', None), args.pop('camera', camera)
        opts = args.pop('opts', args)
    sc = scene or bpy.context.scene
    cam = camera if camera is not None else sc.camera
    o = _opts(opts, kw)
    o['_given'] = set({_CAMEL.get(k, k) for k in dict(opts or {}, **kw)})
    fx = NuclearExplosion(sc, cam, o)
    bake = o['bake']
    if bake == 'scene':
        fx.bake(sc.frame_start, sc.frame_end)
    elif bake:
        fx.bake(int(bake[0]), int(bake[1]))
    elif not o['disable_for_perf_test']:
        fps = sc.render.fps / sc.render.fps_base
        fx.update((sc.frame_current - sc.frame_start) / fps)
    return fx


# the engine's global name: NuclearExplosionFX.applyTo
class NuclearExplosionFX:
    apply_to = staticmethod(apply_to)
    applyTo = staticmethod(apply_to)


# ------------------------------------------------------------------------------------- the post registry ----
NATIVE_KEY = 'eido_nuclear_explosion'


def native_build(scene, o):
    """The post registry's build for 'nuclear_explosion' (look/post/custom_effects.py, kind='native'): the cloud
    baked over the scene's frame range from scene.camera. Returns (the mushroom's object, {'opacity': socket})."""
    o = dict(o or {})
    o.setdefault('bake', 'scene')
    o.pop('layer', None)                              # the registry's layer rule: a volume is in the render itself
    fx = apply_to(scene, scene.camera, o)
    scene[NATIVE_KEY] = [ob.name for ob in fx.objects] + [lo.name for rig in fx.lights for lo in rig.lights]
    if getattr(fx, '_opacity_tree', None) is not None:
        scene[NATIVE_KEY + '_group'] = fx._opacity_tree.name
    return fx.objects[-1], ({'opacity': fx.opacity_socket} if fx.opacity_socket is not None else {})


def native_undo(scene):
    """Take a registry-applied cloud back out (its volumes, materials, lights and opacity group)."""
    import bpy
    group = scene.get(NATIVE_KEY + '_group')
    for name in list(scene.get(NATIVE_KEY, [])):
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        data = ob.data
        mats = [m for m in getattr(data, 'materials', []) if m is not None]
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            (bpy.data.volumes if isinstance(data, bpy.types.Volume) else bpy.data.lights).remove(data)
        for m in mats:
            if m.users == 0:
                bpy.data.materials.remove(m)
    g = bpy.data.node_groups.get(group) if group else None
    if g is not None and g.users == 0:
        bpy.data.node_groups.remove(g)
    for k in (NATIVE_KEY, NATIVE_KEY + '_group'):
        if k in scene:
            del scene[k]
