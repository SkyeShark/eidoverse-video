"""eidoblend.harness.post: the WebGPU runner's auto-enhance stack, its hooks and its overlay layer, on EEVEE.

render_scene.mjs built one post graph after setup() and patched the renderer to draw through it. The Blender runner
does the same after setup() and the config's "render" block: EEVEE's own features stand in for the screen-space
passes, and the hooks become stages of the compositor chain (eidoblend.look.post.chain), in the engine's order.

    WebGPU (applyAutoEnhanceTSL)              Blender
    N8AO ambient occlusion (_aoParams)        EEVEE's horizon scan / fast GI (_ao_params)
    SSR (_ssrParams)                          EEVEE's ray tracing (_ssr_params)
    _autoEnhancePreBloomHook                  a stage just before the bloom (chain slot 'bloom')
    UnrealBloom (_bloomParams)                the chain's Glare (strength, radius -> size, threshold); strength 0 = off
    _autoEnhanceColorHook                     chain slot 'under' (after the bloom, before the overlay)
    the overlay pass (_overlayScene)          chain slot 'overlay': the overlay scene's Render Layers, alpha over
    _autoEnhanceScreenHook                    chain slot 'over' (after the overlay: a HUD is part of the signal)
    renderOutput + FXAA                       AgX after the compositor; EEVEE's pixel filter antialiases
    _noAutoEnhance / NO_AUTOENHANCE=1         ray tracing and fast GI off, no runner stages (the scene's own stay)

A scene script names them at module level, as the engine's globals were named (snake_case; the JS spelling is read
too), or makes them in setup() with `global`:

    _bloom_params = {'strength': 0.4, 'radius': 0.6, 'threshold': 1.0}
    _ao_params = {'ao_radius': 0.4, 'quality': 'high'}            # enabled, half_res, quality, ao_radius
    _ssr_params = {'thickness': 0.1, 'max_roughness': 0.6}         # enabled, thickness, quality, max_roughness

    def _auto_enhance_color_hook(scene, tree):        # return a node with an Image input and output (a node group
        n = tree.nodes.new('CompositorNodeHueSat')    #   for a bigger graph); chain.source_pass(scene, 'Depth')
        n.inputs['Saturation'].default_value = 0.6    #   gives the depth / normal passes the engine's hooks got
        return n

    def setup(ctx):
        global _overlay
        _overlay = post.make_overlay_layer(ctx.scene)  # the engine's makeOverlayLayer: a static camera at the origin
        _overlay.add(title_plane)                      # parented to it, screen-locked at z = -1

What does not carry over, and why:
    _autoEnhancePreSSRHook                     EEVEE traces reflections inside the renderer: there is no pass between
                                               shading and reflection to hook.
    _autoEnhanceCloudReflectHook / BlurHook    the sky family's world (make_sky) lights metals and glass itself.
    the alpha-to-coverage / depthWrite fixes   three.js render-state repairs; EEVEE's render methods have none to make.
    _aoParams intensity / distanceFalloff      EEVEE's occlusion is physical: no strength or falloff knob exists.
    _ssrParams maxDistance                     EEVEE's screen traces have no length limit to set.

Colour: the engine mixed the overlay in before renderOutput, and the runner's renderer tone-mapped nothing (three's
default NoToneMapping), so a lower third landed exactly as drawn, its 80 % panel 80 % dark over the film. The Blender
film always ends in AgX, which would grade a plain alpha-over (measured: an 80 % panel darkened the film behind it
by about a third, #f4efe6 text came out (193, 191, 188), a brand orange washed out). So the overlay stage is the
media family's signal route, authored
(media.overlay.chain_overlay(authored=True)): the over is done in display space and brought back through the
inverse view transform, so the HUD lands as drawn and the 'over' hooks still process it with the film.
make_overlay_layer(..., authored=False) keeps the plain alpha-over, graded by AgX with the film. A scene that made
its own overlay stage (chain_overlay) keeps it. Saturated ink only comes back as close as AgX can show it (see
media/overlay.py); for such ink with no 'over' hook, media.overlay's display route (make_edit_scene) is exact.
"""

from __future__ import annotations

import os

import bpy

FLAG_NO_AUTO_ENHANCE = ('_no_auto_enhance', '_noAutoEnhance')
NAMES = {
    'ao': ('_ao_params', '_aoParams'),
    'ssr': ('_ssr_params', '_ssrParams'),
    'bloom': ('_bloom_params', '_bloomParams'),
    'pre_bloom': ('_auto_enhance_pre_bloom_hook', '_autoEnhancePreBloomHook'),
    'color': ('_auto_enhance_color_hook', '_autoEnhanceColorHook'),
    'screen': ('_auto_enhance_screen_hook', '_autoEnhanceScreenHook'),
    'overlay': ('_overlay', '_overlay_scene', '_overlayScene'),
    'overlay_camera': ('_overlay_camera', '_overlayCamera'),
    'pre_ssr': ('_auto_enhance_pre_ssr_hook', '_autoEnhancePreSSRHook'),
    'cloud_reflect': ('_auto_enhance_cloud_reflect_hook', '_autoEnhanceCloudReflectHook',
                      '_auto_enhance_cloud_reflect_blur_hook', '_autoEnhanceCloudReflectBlurHook'),
}
OVERLAY_PROP = 'eido_overlay_scene'          # film scene custom property: the overlay scene's name
OVERLAY_AUTHORED_PROP = 'eido_overlay_authored'   # False: the overlay alpha-overs in scene light, graded by AgX
AO_QUALITY = {'low': (4, 1), 'medium': (8, 2), 'high': (12, 3), 'ultra': (16, 4)}   # (fast GI steps, rays)


def _chain():
    from ..look.post import chain
    return chain


def _get(ns, scene, key):
    for n in NAMES[key]:
        if ns is not None and n in ns:
            return ns[n]
    for n in NAMES[key]:
        if n in scene.keys():
            return scene[n]
    return None


# --------------------------------------------------------------------------------------------- overlay layer ---

class OverlayLayer:
    """The engine's makeOverlayLayer result: .scene, .camera, and add(obj), which parents obj to the static camera so
    it is screen-locked. Place overlay meshes in camera-local space at z = -1, sized to the frustum: half_h =
    tan(fov / 2), half_w = half_h * width / height (both given here). The media family's Overlay methods (panel,
    place) work on it too."""

    def __init__(self, ov):
        self._ov = ov
        self.scene, self.camera = ov.scene, ov.camera
        self.half_w, self.half_h = ov.half_w, ov.half_h

    def add(self, obj):
        mw = obj.matrix_basis.copy()
        obj.parent = self.camera
        obj.matrix_parent_inverse.identity()
        obj.matrix_basis = mw
        if obj.name not in self.scene.collection.objects:
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            self.scene.collection.objects.link(obj)
        return obj

    def __getattr__(self, name):
        return getattr(self._ov, name)


def make_overlay_layer(scene=None, fov=None, near=0.01, far=10.0, samples=8, name='overlay', authored=True):
    """render_scene.mjs's makeOverlayLayer: a transparent scene of its own with a STATIC camera at the origin whose
    field of view is the film camera's (or fov degrees, vertical, three's convention), registered on the film scene
    so the runner composites it over every frame (chain slot 'overlay'), before the screen hook. Built on the media
    family's overlay scene (eidoblend.media.overlay), so its panels and subtitles work on it. authored (default): the
    HUD lands as drawn, as the engine's did; False: its linear colours alpha-over the film and AgX grades them."""
    from ..media import overlay as mo
    film = scene or bpy.context.scene
    ov = mo.make_overlay_layer(film, fov=fov, name=name, samples=samples)
    ov.camera.data.clip_start, ov.camera.data.clip_end = float(near), float(far)
    film[OVERLAY_PROP] = ov.scene.name
    film[OVERLAY_AUTHORED_PROP] = bool(authored)
    return OverlayLayer(ov)


def overlay_scene_of(scene, ns=None):
    """The overlay scene a film composites: the script's _overlay (an OverlayLayer, a media Overlay or a Scene) or
    the scene's registration (make_overlay_layer)."""
    v = _get(ns, scene, 'overlay')
    if v is not None:
        sc = v if isinstance(v, bpy.types.Scene) else getattr(v, 'scene', None)
        if isinstance(sc, bpy.types.Scene) and sc != scene:
            return sc                                    # anything else named _overlay is the script's own business
    nm = scene.get(OVERLAY_PROP)
    return bpy.data.scenes.get(nm) if nm else None


# ------------------------------------------------------------------------------------------------ the stack ---

def _set_ao(ee, p, notes):
    if p.get('enabled') is False:
        ee.use_fast_gi = False
        notes.append('ao off (fast GI off)')
        return
    if 'half_res' in p or 'halfRes' in p:
        ee.fast_gi_resolution = '2' if (p.get('half_res', p.get('halfRes'))) else '1'
    q = p.get('quality')
    if isinstance(q, str) and q.lower() in AO_QUALITY:
        ee.fast_gi_step_count, ee.fast_gi_ray_count = AO_QUALITY[q.lower()]
    r = p.get('ao_radius', p.get('aoRadius'))
    if r is not None:
        ee.fast_gi_distance = float(r)
    skipped = [k for k in ('intensity', 'distance_falloff', 'distanceFalloff') if k in p]
    notes.append(f'ao: fast GI {ee.fast_gi_resolution} res, {ee.fast_gi_step_count} steps x {ee.fast_gi_ray_count} '
                 f'rays, {ee.fast_gi_distance:.2f} m' + (f" ({', '.join(skipped)}: no EEVEE knob, ignored)"
                                                          if skipped else ''))


def _set_ssr(ee, p, notes):
    if p.get('enabled') is False:
        ee.use_raytracing = False
        notes.append('ssr off (ray tracing off)')
        return
    ee.use_raytracing = True
    o = ee.ray_tracing_options
    if 'thickness' in p:
        o.screen_trace_thickness = float(p['thickness'])
    if 'quality' in p and isinstance(p['quality'], (int, float)):
        o.screen_trace_quality = float(p['quality'])
    if 'max_roughness' in p or 'maxRoughness' in p:
        o.trace_max_roughness = float(p.get('max_roughness', p.get('maxRoughness')))
    skipped = [k for k in ('max_distance', 'maxDistance', 'opacity', 'resolution_scale') if k in p]
    notes.append(f'ssr: ray tracing, thickness {o.screen_trace_thickness:.3f}, quality {o.screen_trace_quality:.2f}, '
                 f'max roughness {o.trace_max_roughness:.2f}'
                 + (f" ({', '.join(skipped)}: no EEVEE knob, ignored)" if skipped else ''))


def _hook_node(fn, scene, what):
    chain = _chain()
    tree = chain.tree(scene)
    node = fn(scene, tree)
    if node is None:
        return None
    if not isinstance(node, bpy.types.Node):
        raise TypeError(f'{what} returned {type(node).__name__}: return a compositor node with an Image in and out')
    return node


def apply(scene, ns=None, led=None):
    """Install the auto-enhance stack and the hooks on a built scene (the runner calls it once, after setup() and the
    config's "render" block). Returns the list of what it added, which the digest records like the engine's
    '[auto-enhance] TSL pipeline: scenePass + ...' line."""
    added, notes = [], []
    off = any(ns is not None and ns.get(n) for n in FLAG_NO_AUTO_ENHANCE) or any(scene.get(n) for n in
                                                                                FLAG_NO_AUTO_ENHANCE) \
        or os.environ.get('NO_AUTOENHANCE') == '1'
    ignored = [k for k in ('pre_ssr', 'cloud_reflect') if _get(ns, scene, k) is not None]
    if off:
        ee = scene.eevee
        ee.use_raytracing = False
        ee.use_fast_gi = False
        _record(led, 'PASS', 'auto-enhance OFF (the scene set _no_auto_enhance, or NO_AUTOENHANCE=1): EEVEE ray '
                             'tracing and fast GI off, no runner stages; the scene\'s own compositor stages stay',
                {'added': []})
        return []
    ee = scene.eevee
    ao, ssr = _get(ns, scene, 'ao'), _get(ns, scene, 'ssr')
    if isinstance(ao, dict):
        _set_ao(ee, ao, notes)
    if isinstance(ssr, dict):
        _set_ssr(ee, ssr, notes)
    if ee.use_fast_gi:
        added.append('AO (EEVEE fast GI)')
    if ee.use_raytracing:
        added.append('SSR (EEVEE ray tracing)')
    bp = _get(ns, scene, 'bloom')
    hooks = {k: _get(ns, scene, k) for k in ('pre_bloom', 'color', 'screen')}
    ovs = overlay_scene_of(scene, ns)
    if not (bp is not None or any(callable(h) for h in hooks.values()) or ovs is not None):
        _record(led, 'PASS', 'auto-enhance: ' + ' + '.join(added or ['EEVEE as set']) + ' (no hooks, no overlay)'
                + (f"; {'; '.join(notes)}" if notes else '') + _ignored_text(ignored), {'added': added})
        return added
    chain = _chain()
    if isinstance(bp, dict):
        strength = float(bp.get('strength', 0.25))
        if strength > 0:
            chain.set_bloom(scene, strength=strength, size=float(bp.get('radius', bp.get('size', 0.5))),
                            threshold=float(bp.get('threshold', 1.0)))
            added.append(f'bloom (Glare: strength {strength:g})')
        else:
            chain.set_bloom(scene, None)
            notes.append('bloom off (strength 0)')
    failed = []

    def install(key, what, slot, stage, label):
        """One hook as a chain stage; a hook that raises is reported and skipped, as the engine warned and went on
        ('[auto-enhance] color-hook failed: ...')."""
        if not callable(hooks[key]):
            return
        try:
            n = _hook_node(hooks[key], scene, what)
        except Exception as e:                                      # noqa: BLE001 - the scene's own code
            failed.append(f'{what} failed ({type(e).__name__}: {e})')
            print(f'[auto-enhance] {what} failed: {e}', flush=True)
            return
        if n is None:
            return
        chain.add_stage(scene, slot, stage, n)
        added.append(label)
    # the chain's own slot before the bloom: the engine's _autoEnhancePreBloomHook ran BEFORE its bloom
    install('pre_bloom', '_auto_enhance_pre_bloom_hook', 'prebloom', 'pre_bloom_hook', 'preBloom-hook')
    install('color', '_auto_enhance_color_hook', 'under', 'color_hook', 'hook')
    if ovs is not None:
        cam = _get(ns, scene, 'overlay_camera')
        if isinstance(cam, bpy.types.Object) and cam.type == 'CAMERA':
            ovs.camera = cam
        ovs.render.film_transparent = True
        _match(ovs, scene)
        added.append(f"overlay ('{ovs.name}', {_overlay_stage(scene, ovs)})")
    install('screen', '_auto_enhance_screen_hook', 'over', 'screen_hook', 'screenHook')
    _record(led, 'WARN' if failed else 'PASS', 'auto-enhance: ' + ' + '.join(added)
            + f' + {scene.view_settings.view_transform}' + (f"; {'; '.join(notes)}" if notes else '')
            + _ignored_text(ignored) + (f"; NOT installed: {'; '.join(failed)}" if failed else ''),
            {'added': added, 'stages': [f'{s}:{n}' for s, n, _x in chain.stages(scene)]})
    return added


def _overlay_stage(scene, ovs):
    """The overlay scene into the chain's overlay slot, through the media family's signal route. A stage already
    there (the scene called media.overlay.chain_overlay itself, or a build reopened) is kept. Otherwise authored
    (scene['eido_overlay_authored'] unset or True: the over in display space, so the HUD lands as drawn) or graded
    (False: a plain alpha-over in scene light, AgX after it). Returns the route, for the digest."""
    from ..media import overlay as mo
    chain = _chain()
    st = next((n for _s, nm, n in chain.stages(scene) if nm == 'overlay'), None)
    if st is not None and 'Foreground' in st.inputs and st.inputs['Foreground'].is_linked:
        return 'its own overlay stage, kept'
    authored = bool(scene.get(OVERLAY_AUTHORED_PROP, True))
    mo.chain_overlay(ovs, scene, authored=authored)
    return 'authored: lands as drawn' if authored else 'graded with the film by AgX'


def _match(ovs, film):
    """The overlay scene renders the film's frame size, rate and range (a render of the film renders it too, frame
    for frame, through its Render Layers node)."""
    r, fr = ovs.render, film.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = fr.resolution_x, fr.resolution_y, fr.resolution_percentage
    r.fps, r.fps_base = fr.fps, fr.fps_base
    ovs.frame_start, ovs.frame_end = film.frame_start, film.frame_end


def match_overlay(scene):
    """Keep a composited overlay scene at the film's size (the probe caps shrink the film at render time)."""
    t = scene.compositing_node_group
    if t is None:
        return
    for n in t.nodes:
        if n.bl_idname == 'CompositorNodeRLayers' and n.scene is not None and n.scene != scene:
            _match(n.scene, scene)
            n.scene.eevee.taa_render_samples = min(n.scene.eevee.taa_render_samples, scene.eevee.taa_render_samples)


def _ignored_text(ignored):
    if not ignored:
        return ''
    why = {'pre_ssr': 'the pre-SSR hook (EEVEE traces reflections inside the renderer)',
           'cloud_reflect': 'the cloud-reflect hooks (the sky family\'s world lights metals)'}
    return '; not applied: ' + ', '.join(why[k] for k in ignored)


def _record(led, outcome, message, metrics):
    print(f'[auto-enhance] {message}', flush=True)
    if led is not None:
        led.record(check='render.auto_enhance', outcome=outcome, cls='REVIEW' if outcome == 'WARN' else 'INFO',
                   metrics=metrics, message=message)
