"""Graphics on the frame: the overlay layer, subtitles and the edit scene (makeOverlayLayer, ported).

Two routes put the overlay on the film, and signal effects can follow it over the edit; all start from the same
overlay layer.

The display route (the default): graphics are laid over the finished film in display space, after the film's own
view transform, in the edit scene, the way DAISY's burned-in ASS subtitles were: colours land exactly as authored.

    from eidoblend.media import overlay
    ov = overlay.make_overlay_layer(film_scene, camera=film_scene.camera)     # a scene of its own, view Standard
    bar = ov.panel(draw=lower_third, x=-0.28, y=-0.36, w=0.38, h=0.09, px=900, frames=(1, 240))
    frames_dir = overlay.render_overlay(ov, 'work/<id>/overlay')              # RGBA PNGs
    edit = overlay.make_edit_scene(film='work/<id>/film.mp4', overlays=[frames_dir],
                                   subtitles=overlay.subtitle_cues(lines, font='Share Tech Mono'),
                                   sounds=[('work/<id>/mix.wav', 1)])
    overlay.render_edit(edit, 'work/<id>/final.mp4')                         # one pass: picture, graphics, sound

The signal route (the WebGPU engine's layering): the overlay goes into the film's own post chain (look/post/chain.py)
between the world effects and the signal effects, and the film's view transform applies after all of it:

    Render Layers -> bloom -> 'under' (world) effects -> the overlay -> 'over' (signal) effects -> AgX
    overlay.chain_overlay(ov, film_scene)          # vhs / glitch / rgb_shift in 'over' now process the HUD too

In the engine the overlay was mixed in before tone mapping; parole.js put its SOLID ink through the inverse of ACES
so it landed as drawn and left glows and soft edges in display light (the inverse curve would blow a 10 % glow up
into a bright box), split by smoothstep(0.55, 0.95, alpha), because a material cannot see the film under it. The
compositor can: chain_overlay (authored=True) takes the film at the overlay slot into display space with its own
view transform, lays the overlay over it there exactly as the display route does, and brings the result back to
scene light through the inverse, so solid ink, glows, soft edges and fades all land as drawn (measured against the
display route: the lyric's glow ring within 1-2 levels, where a per-pixel inverse is 46 off).
AgX cannot show every display colour: neutrals and moderately saturated ink (teal #27e0a0) come back within 2/255,
saturated colours do not (cyan #00d4ff 16/255 off, #ff2d95 21, pure red 26, #ffd400 50, pure blue 67). When such
ink must be exact and no signal effect runs over it, use the display route.

The signal over the edit: when such ink must be exact AND signal effects run over it, the effects leave the film's
chain for the edit scene, where they run over the film and the overlay together, after the view transform:

    sig = overlay.take_signal_effects(film_scene)          # the 'over' stages (and their keys) leave the chain
    # render the film; frames_dir = overlay.render_overlay(ov, ...)
    edit = overlay.make_edit_scene(film=..., overlays=[frames_dir], signal=sig)   # a COMPOSITOR strip modifier
    overlay.render_edit(edit, 'work/<id>/final.mp4')

An overlay plane sits at z = -1 under the overlay camera, whose field of view is the film camera's, so the frame is
2 * half_w x 2 * half_h there; ``ov.place(obj, x, y)`` takes frame fractions (-0.5 .. 0.5, centre origin, y up).
"""
import math

import bpy

from . import raster
from .screens import _abspath, _is_hold, make_screen, set_interpolation
from .timebase import Timebase


class Overlay:
    def __init__(self, scene, camera, film):
        self.scene, self.camera, self.film = scene, camera, film
        self.half_w, self.half_h = frame_half_extents(camera, scene)

    def place(self, obj, x=0.0, y=0.0, z=-1.0):
        """Parent ``obj`` to the overlay camera at frame fractions x, y (centre origin, y up) and depth -z."""
        obj.parent = self.camera
        k = -z
        obj.location = (x * 2 * self.half_w * k, y * 2 * self.half_h * k, z)
        if obj.name not in self.scene.collection.objects:            # it lives in the overlay scene only
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            self.scene.collection.objects.link(obj)
        return obj

    def panel(self, draw, x=0.0, y=0.0, w=0.5, h=0.1, px=1024, frames=None, out_dir=None, name='overlay_panel',
              fps=0, supersample=2, z=-1.0, **kw):
        """A screen-locked, transparent drawn panel: w and h are fractions of the frame's width and height at
        z = -1. draw(canvas, t, w_px, h_px) as make_screen's (clear to transparent and draw). A graphic on the
        frame exists only in its ``frames``: outside them the panel is hidden from the render (keyed), where an
        in-world screen holds its first and last drawings."""
        ww, hh = w * 2 * self.half_w, h * 2 * self.half_h
        fa, fb = frames or (self.scene.frame_start, self.scene.frame_end)
        scr = make_screen(width=ww, height=hh, px=px, draw=draw, frames=(fa, fb), fps=fps, transparent=True,
                          out_dir=out_dir, name=name, supersample=supersample, scene=self.scene, strength=1.0,
                          double_sided=True, **kw)
        scr.obj.rotation_euler = (-math.pi / 2, 0.0, 0.0)       # the panel faces -Y; the overlay camera looks down -Z
        self.place(scr.obj, x, y, z)
        key_render_range(scr.obj, fa, fb, self.scene)
        return scr


def key_render_range(obj, fa, fb, scene):
    """Render ``obj`` only on frames fa..fb: CONSTANT hide_render keys at fa - 1, fa and fb + 1 (none for a range
    that covers the scene's)."""
    keys = ([(fa - 1, True)] if fa > scene.frame_start else []) + [(fa, False)] + (
        [(fb + 1, True)] if fb < scene.frame_end else [])
    if len(keys) == 1:
        return obj
    for f, hidden in keys:
        obj.hide_render = hidden
        obj.keyframe_insert('hide_render', frame=f)
    set_interpolation(obj, 'CONSTANT', 'hide_render')
    obj.hide_render = keys[0][1]
    return obj


def frame_half_extents(camera, scene, distance=1.0):
    """Half width and half height of a camera's frame at ``distance`` in front of it (any sensor fit)."""
    corners = camera.data.view_frame(scene=scene)
    xs = [abs(c.x / -c.z) for c in corners]
    ys = [abs(c.y / -c.z) for c in corners]
    return max(xs) * distance, max(ys) * distance


def make_overlay_layer(film_scene=None, camera=None, fov=None, name='overlay', samples=8, filter_size=1.5,
                       near=0.01, far=10.0):
    """A scene for graphics on the frame: the film scene's resolution, rate and range; view Standard, a
    transparent film, no motion blur, and a static camera at the origin (looking down -Z) with the film camera's
    field of view (or ``fov`` degrees vertical, three's convention; ``near`` / ``far`` its clip range, the engine's
    0.01 / 10). ``filter_size``: EEVEE's pixel filter (1.5 px antialiases 3D type placed on the layer; 0 keeps drawn
    graphics at their own pixels: a full-frame panel drawn at the film's resolution, like make_lyric_layer's, then
    renders exactly as drawn). Returns an Overlay."""
    film = film_scene or bpy.context.scene
    sc = bpy.data.scenes.new(name)
    r, fr = sc.render, film.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = fr.resolution_x, fr.resolution_y, fr.resolution_percentage
    r.pixel_aspect_x, r.pixel_aspect_y = fr.pixel_aspect_x, fr.pixel_aspect_y
    r.fps, r.fps_base = fr.fps, fr.fps_base
    sc.frame_start, sc.frame_end = film.frame_start, film.frame_end
    if 'eido_frame0' in film:
        sc['eido_frame0'] = film['eido_frame0']
    r.film_transparent = True
    r.filter_size = float(filter_size)
    r.dither_intensity = 0.0          # Blender dithers float -> 8 bit by default: solid ink would land +-1 off
    r.use_motion_blur = False
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    cd = bpy.data.cameras.new(name + '_cam')
    src = (camera or film.camera)
    if fov is not None or src is None:
        cd.sensor_fit = 'VERTICAL'
        cd.angle_y = math.radians(fov if fov is not None else 50.0)
    else:
        s = src.data
        cd.lens, cd.sensor_width, cd.sensor_height, cd.sensor_fit = s.lens, s.sensor_width, s.sensor_height, s.sensor_fit
        cd.shift_x, cd.shift_y = s.shift_x, s.shift_y
    cd.clip_start, cd.clip_end = float(near), float(far)
    cam = bpy.data.objects.new(name + '_cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return Overlay(sc, cam, film)


def render_overlay(ov, out_dir, frames=None, prefix='ov_'):
    """Render the overlay scene to RGBA PNGs: <out_dir>/<prefix>####.png, numbered by scene frame."""
    sc = ov.scene if isinstance(ov, Overlay) else ov
    out = _abspath(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    keep = sc.frame_start, sc.frame_end
    if frames:
        sc.frame_start, sc.frame_end = frames
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGBA'
    r.image_settings.color_depth = '8'
    r.filepath = str(out / f'{prefix}####')
    r.use_file_extension = True
    try:
        bpy.ops.render.render(animation=True, scene=sc.name)
    finally:
        sc.frame_start, sc.frame_end = keep
    return out


# ---------------------------------------------------------------------------------------------------- the signal route
AUTHORED_TAG = 'eido_display'           # look/post/display.py's tag: its sync() keeps these nodes on the film's view
SOURCE_NODE = 'media:overlay_source'


def _view_node(N, film, invert, x, y):
    """Convert To Display with the film's view transform, look and display (tagged for look/post/display.sync)."""
    n = N.new('CompositorNodeConvertToDisplay')
    n[AUTHORED_TAG] = 'inv' if invert else 'fwd'
    n.inputs['Invert'].default_value = bool(invert)
    n.display_settings.display_device = film.display_settings.display_device
    n.view_settings.view_transform = film.view_settings.view_transform
    n.view_settings.look = film.view_settings.look
    n.location = (x, y)
    return n


def _authored_group(film, name='eido_overlay_authored'):
    """The signal route's overlay stage as a compositor group: Background (the film at the overlay slot, scene light),
    Foreground (the overlay, premultiplied; its straight colour is what its Standard view shows), Factor (the
    overlay's opacity), Exposure (the film's view exposure, driven) -> Image.

    The over happens in DISPLAY space, as the display route's sequencer does it: the film goes through its own view
    transform (Convert To Display, exposure applied), the overlay's straight colour is sRGB-encoded, the two mix by
    the overlay's alpha (times Factor), and the inverse view transform (exposure divided out) brings the mix back to
    scene light, so AgX after the chain shows exactly that mix: solid ink as drawn and glows, soft edges and fades
    as they look over the film in display space. Where the film's light is beyond what the view shows (a lamp above
    AgX's white), its own round trip comes back short; the stage keeps the film's light where the overlay is clear
    and lets (1 - alpha) of the excess through under soft pixels:

        C = (1 - a) * (B - inv(view(B))) + inv((1 - a) * view(B) + a * enc(F / F.a))

    exact at a = 0 (the film untouched) and at a = 1 (the ink), the display route's blend wherever the view can
    show the film."""
    g = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    I = g.interface
    I.new_socket(name='Background', in_out='INPUT', socket_type='NodeSocketColor')
    I.new_socket(name='Foreground', in_out='INPUT', socket_type='NodeSocketColor')
    fs = I.new_socket(name='Factor', in_out='INPUT', socket_type='NodeSocketFloat')
    fs.default_value, fs.min_value, fs.max_value = 1.0, 0.0, 1.0
    I.new_socket(name='Exposure', in_out='INPUT', socket_type='NodeSocketFloat')
    I.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    N, L = g.nodes, g.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    gi.location, go.location = (-900, 0), (1500, 0)

    def put(sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            L.new(val, sock)
        else:
            sock.default_value = val

    def node(kind, x, y, **props):
        n = N.new(kind)
        n.location = (x, y)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def math(op, a, b, x, y, clamp=False):
        n = node('ShaderNodeMath', x, y, operation=op, use_clamp=clamp)
        put(n.inputs[0], a)
        put(n.inputs[1], b)
        return n.outputs[0]

    def vmath(op, a, b, x, y):
        n = node('ShaderNodeVectorMath', x, y, operation=op)
        put(n.inputs[0], a)
        put(n.inputs[1], b)
        return n.outputs[0]

    def clamp01(v, x, y):
        return vmath('MAXIMUM', vmath('MINIMUM', v, (1.0, 1.0, 1.0), x, y), (0.0, 0.0, 0.0), x + 160, y)

    def exposure(img, ev, x, y):
        n = node('CompositorNodeExposure', x, y)
        L.new(img, n.inputs['Image'])
        L.new(ev, n.inputs['Exposure'])
        return n.outputs['Image']

    B, F, fac, ev = gi.outputs['Background'], gi.outputs['Foreground'], gi.outputs['Factor'], gi.outputs['Exposure']
    neg_ev = math('MULTIPLY', ev, -1.0, -700, -700)
    # the overlay: alpha (times Factor) and its straight colour, sRGB-encoded as its Standard view writes it
    sep_f = node('CompositorNodeSeparateColor', -700, -380)
    L.new(F, sep_f.inputs['Image'])
    a = math('MULTIPLY', sep_f.outputs['Alpha'], fac, -500, -380, clamp=True)
    one_minus_a = math('SUBTRACT', 1.0, a, -300, -380)
    straight = node('CompositorNodePremulKey', -700, -200)
    straight.inputs['Type'].default_value = 'To Straight'
    L.new(F, straight.inputs['Image'])
    enc = node('CompositorNodeConvertColorSpace', -500, -200, from_color_space='Linear Rec.709', to_color_space='sRGB')
    L.new(straight.outputs['Image'], enc.inputs['Image'])
    s_enc = clamp01(enc.outputs['Image'], -300, -200)
    # the film in display space
    fwd = _view_node(N, film, False, -500, 120)
    L.new(exposure(B, ev, -700, 120), fwd.inputs['Image'])
    d_film = clamp01(fwd.outputs['Image'], -300, 120)
    # the over in display space, and both back to scene light
    mix = node('ShaderNodeMix', 0, 0, data_type='VECTOR', factor_mode='UNIFORM', clamp_factor=True)
    ins = {s.identifier: s for s in mix.inputs}       # Mix holds a socket per data type under the same names
    L.new(a, ins['Factor_Float'])
    L.new(d_film, ins['A_Vector'])
    L.new(s_enc, ins['B_Vector'])
    inv_mix = _view_node(N, film, True, 220, 0)
    L.new(next(s for s in mix.outputs if s.identifier == 'Result_Vector'), inv_mix.inputs['Image'])
    inv_film = _view_node(N, film, True, 220, 240)
    L.new(d_film, inv_film.inputs['Image'])
    lin_mix = exposure(inv_mix.outputs['Image'], neg_ev, 440, 0)
    lin_film = exposure(inv_film.outputs['Image'], neg_ev, 440, 240)
    # C = (1 - a) * (B - inv(view(B))) + inv(mix)
    excess = vmath('SUBTRACT', B, lin_film, 660, 240)
    sc = node('ShaderNodeVectorMath', 860, 240, operation='SCALE')
    L.new(excess, sc.inputs[0])
    L.new(one_minus_a, sc.inputs['Scale'])
    col = vmath('ADD', sc.outputs[0], lin_mix, 1060, 0)
    # alpha: the over's (1 on an opaque film)
    sep_b = node('CompositorNodeSeparateColor', -700, 420)
    L.new(B, sep_b.inputs['Image'])
    a_out = math('ADD', math('MULTIPLY', a, math('SUBTRACT', 1.0, sep_b.outputs['Alpha'], -500, 420), -300, 420),
                 sep_b.outputs['Alpha'], 1060, 420, clamp=True)
    seta = node('CompositorNodeSetAlpha', 1260, 0)
    seta.inputs['Type'].default_value = 'Replace Alpha'
    L.new(col, seta.inputs['Image'])
    L.new(a_out, seta.inputs['Alpha'])
    L.new(seta.outputs['Image'], go.inputs['Image'])
    return g


def _clear_holds(first, last):
    """Fully transparent hold files one below the first overlay frame and one above the last (marked as holds,
    never frames). A compositor Image node shows file <first - 1> before its range and clamps to its last file
    after it (Blender's image-user rule), so without them an overlay sequence shorter than the film would show
    magenta before its first frame and freeze its last one after its range."""
    from PIL.PngImagePlugin import PngInfo
    from .screens import HOLD_KEY, _seq_split
    first, last = _abspath(first), _abspath(last)
    with raster.Image.open(first) as im:
        size = im.size
    head, n0, nd = _seq_split(first)
    _h, n1, _nd = _seq_split(last)
    for num in (n0 - 1, n1 + 1):
        hold = first.with_name(f'{head}{num:0{nd}d}{first.suffix}')
        if num < 0 or (hold.exists() and not _is_hold(hold)):
            continue
        info = PngInfo()
        info.add_text(HOLD_KEY, '1')
        tmp = hold.with_name(hold.name + '.part')
        raster.Image.new('RGBA', size, (0, 0, 0, 0)).save(tmp, format='PNG', pnginfo=info)
        tmp.replace(hold)


def _drive_exposure(film, socket):
    """A driver keeping ``socket`` equal to the film's view exposure (a keyed exposure follows)."""
    try:
        socket.driver_remove('default_value')
    except (TypeError, RuntimeError):
        pass
    fc = socket.driver_add('default_value')
    fc.driver.type = 'SCRIPTED'
    v = fc.driver.variables.new()
    v.name, v.type = 'ev', 'SINGLE_PROP'
    v.targets[0].id_type = 'SCENE'
    v.targets[0].id = film
    v.targets[0].data_path = 'view_settings.exposure'
    fc.driver.expression = 'ev'
    socket.default_value = film.view_settings.exposure
    return fc


def _drop_overlay_stage(film):
    """Take the film chain's overlay stage out, with its source node and its exposure driver. Returns True if there
    was one."""
    from ..look.post import chain
    t = film.compositing_node_group
    if t is None:
        return False
    found = False
    for _s, nm, n in chain.stages(film):
        if nm == 'overlay':
            ad = t.animation_data                        # the old stage's exposure driver goes with it
            for fc in [fc for fc in (ad.drivers if ad else ()) if fc.data_path.startswith(f'nodes["{n.name}"]')]:
                ad.drivers.remove(fc)
            chain.remove_stage(film, 'overlay')
            found = True
    for n in [n for n in t.nodes if n.name.startswith(SOURCE_NODE)]:
        t.nodes.remove(n)
    return found


def chain_overlay(ov, film_scene=None, authored=True, source=None, factor=1.0):
    """The signal route: put the overlay layer into the film's post chain at its overlay slot (look/post/chain.py),
    the WebGPU layering: world effects ('under') below it, signal effects ('over': vhs, glitch, rgb_shift, grain)
    over it and the HUD together, the film's view transform after everything.

    ``source``: None renders the overlay scene with the film (a Render Layers node of the overlay scene: Blender
    renders both scenes for each film frame), or a folder / first file of render_overlay's RGBA PNGs (rendered
    once, reused). ``authored`` (the default): the overlay stage is _authored_group, the over done in display space
    and brought back through the inverse view transform, so the overlay lands as it looks on the display route,
    solid ink, glows, soft edges and fades alike (exact for neutrals and moderately saturated ink; saturated colours
    only as close as AgX can show them: see the module notes). False: the overlay's linear colours alpha-over the
    film (chain.set_overlay's Alpha Over) and AgX grades them with the film, as the engine graded a plain overlay.
    ``factor``: the overlay's opacity; key the returned 'factor' socket (a fade through it is a display-space fade
    on the authored route). The chain holds one overlay stage: calling again replaces it and its source (switching
    routes). Panels keep their keyed hide_render ranges. Returns {'foreground': the source node, 'stage': the
    overlay stage (the group node, or the Alpha Over), 'factor': its Factor socket, 'authored': the group node or
    None}."""
    from ..look.post import chain                      # the look family's chain owns the order and the relinking
    sc = ov.scene if isinstance(ov, Overlay) else ov
    film = film_scene or (ov.film if isinstance(ov, Overlay) else bpy.context.scene)
    t = chain.tree(film)
    _drop_overlay_stage(film)
    if source is None:
        fg = t.nodes.new('CompositorNodeRLayers')
        fg.scene = sc
        fg.layer = sc.view_layers[0].name
        sc.render.film_transparent = True
    else:
        p = _abspath(source)
        if p.is_dir():
            files = sorted(p.glob('*.png'))
        else:
            head = p.stem.rstrip('0123456789')
            files = sorted(x for x in p.parent.glob(f'{head}*.png') if x.stem[len(head):].isdigit())
        files = [f for f in files if not _is_hold(f)]
        if not files:
            raise FileNotFoundError(f'{source}: no overlay frames')
        stem = files[0].stem
        digits = len(stem) - len(stem.rstrip('0123456789'))
        first = int(stem[-digits:]) if digits else 1
        _clear_holds(files[0], files[-1])
        img = bpy.data.images.load(str(files[0]), check_existing=False)
        img.source = 'SEQUENCE'
        img.alpha_mode = 'STRAIGHT'
        fg = t.nodes.new('CompositorNodeImage')
        fg.image = img
        fg.frame_start = first                         # render_overlay numbers its files by the scene's frame
        fg.frame_duration = len(files) + 1             # + the clear hold after the last: a graphic ends with its frames
        fg.frame_offset = first - 1
    fg.name = SOURCE_NODE
    fg.location = (-400, -420)
    grp = None
    if authored:
        grp = t.nodes.new('CompositorNodeGroup')
        grp.node_tree = _authored_group(film)
        chain.add_stage(film, 'overlay', 'overlay', grp)     # relink() feeds it the chain's colour as Background
        t.links.new(fg.outputs['Image'], grp.inputs['Foreground'])
        grp.inputs['Factor'].default_value = float(factor)
        _drive_exposure(film, grp.inputs['Exposure'])
        stage = grp
    else:
        stage = chain.set_overlay(film, fg, factor=factor)
    film.render.use_compositing = True
    return {'foreground': fg, 'stage': stage, 'factor': stage.inputs['Factor'], 'authored': grp}


# ---------------------------------------------------------------------------------------------------- signal over the edit
SIGNAL_PROP = 'eido_signal_group'      # film scene custom property: the group take_signal_effects made from its chain
_NODE_SKIP = {'rna_type', 'name', 'label', 'location', 'location_absolute', 'width', 'height', 'dimensions', 'select',
              'parent', 'color', 'color_tag', 'use_custom_color', 'hide', 'show_options', 'show_preview',
              'show_texture', 'inputs', 'outputs', 'internal_links', 'type', 'bl_idname', 'bl_label',
              'bl_description', 'bl_icon', 'bl_static_type', 'bl_width_default', 'bl_width_min', 'bl_width_max',
              'bl_height_default', 'bl_height_min', 'bl_height_max', 'warning_propagation'}


def _tree_has(tree, test, seen=None):
    seen = seen if seen is not None else set()
    if tree is None or tree.name in seen:
        return False
    seen.add(tree.name)
    for n in tree.nodes:
        if test(n) or (getattr(n, 'node_tree', None) is not None and _tree_has(n.node_tree, test, seen)):
            return True
    return False


def _why_not_movable(t, name, node):
    """Why a chain stage cannot run over the edit scene (None when it can)."""
    from ..look.post import chain, display
    img = chain._img_in(node)
    for s in node.inputs:
        if s.is_linked and s.identifier != img.identifier:
            return (f'its {s.name!r} input comes from {s.links[0].from_node.name!r} (a pass of the film\'s render or a '
                    f'record of earlier frames), which the edit scene does not have')
    if any(n.get('look_input_of') == name for n in t.nodes):
        return 'it reads earlier frames (a history writer rides with it)'
    ad = t.animation_data
    if ad is not None and any(d.data_path.startswith(f'nodes["{node.name}"]') for d in ad.drivers):
        return 'a driver sets one of its inputs from the film scene'
    if _tree_has(getattr(node, 'node_tree', None), lambda n: n.get(display.TAG) or n.bl_idname == 'CompositorNodeRLayers'):
        return 'it works through the film\'s view transform (display space) or renders a scene of its own'
    return None


def _copy_node(src, tree):
    """``src`` (a chain stage) made again in ``tree``: its node tree or settings, its unlinked input values, its name,
    label and custom properties."""
    n = tree.nodes.new(src.bl_idname)
    if src.bl_idname == 'CompositorNodeGroup':
        n.node_tree = src.node_tree
    else:
        for p in src.bl_rna.properties:
            if p.is_readonly or p.identifier in _NODE_SKIP:
                continue
            try:
                setattr(n, p.identifier, getattr(src, p.identifier))
            except (AttributeError, TypeError, ValueError):
                pass
    for a, b in zip(src.inputs, n.inputs):
        if not a.is_linked and hasattr(a, 'default_value'):
            try:
                b.default_value = a.default_value
            except (AttributeError, TypeError, ValueError):
                pass
    n.name, n.label, n.mute = src.name, src.label, src.mute
    for k in src.keys():
        n[k] = src[k]
    return n


def _copy_keys(src_tree, dst_tree, node_name):
    """Copy the keys on node ``node_name``'s inputs from one compositor tree to the same-named node of another
    (values, interpolation, easing, handles). Returns the number of F-curves copied."""
    from .screens import action_fcurves
    ad = src_tree.animation_data
    if ad is None or ad.action is None:
        return 0
    prefix = f'nodes["{node_name}"]'
    done = 0
    for fc in [fc for fc in action_fcurves(ad.action, getattr(ad, 'action_slot', None))
               if fc.data_path.startswith(prefix)]:
        owner_path, _, prop = fc.data_path.rpartition('.')
        owner = dst_tree.path_resolve(owner_path)
        rp = owner.bl_rna.properties[prop]
        idx = fc.array_index if rp.is_array else -1
        for kp in fc.keyframe_points:
            v = kp.co[1]
            v = int(round(v)) if rp.type == 'INT' else (v >= 0.5 if rp.type == 'BOOLEAN' else v)
            if rp.is_array:
                getattr(owner, prop)[fc.array_index] = v
            else:
                setattr(owner, prop, v)
            owner.keyframe_insert(prop, index=idx, frame=kp.co[0])
        dad = dst_tree.animation_data
        dst = next(f for f in action_fcurves(dad.action, getattr(dad, 'action_slot', None))
                   if f.data_path == fc.data_path and f.array_index == fc.array_index)
        for a, b in zip(fc.keyframe_points, dst.keyframe_points):
            b.interpolation, b.easing = a.interpolation, a.easing
            b.handle_left_type, b.handle_right_type = a.handle_left_type, a.handle_right_type
            b.handle_left, b.handle_right = a.handle_left, a.handle_right
        dst.update()
        done += 1
    return done


def take_signal_effects(film_scene=None, name='eido_signal'):
    """The edit route for signal effects: the film chain's 'over' stages (vhs_tape, glitch_bars, rgb_shift, a screen
    hook ...) leave it for one compositor group, which make_edit_scene(..., signal=group) runs over the film and the
    overlay together, in display light, as a COMPOSITOR strip modifier. The HUD lands exactly as drawn, saturated ink
    included, and the effects still process it as part of the signal.

    Call it after the film's effects are applied and before the film renders: the stages go, with their keys, in
    chain order, and so does a chain overlay stage (the edit lays the overlay instead). A stage that needs the film's
    render (its Depth / Normal passes, its earlier frames, a driver on the film, the view transform) cannot move: then
    nothing moves and the error names it (put such an effect 'under'). Returns the group (None when the chain has no
    'over' stage); the film scene records its name in SIGNAL_PROP."""
    from ..look.post import chain
    from .screens import action_fcurves, remove_fcurves
    film = film_scene or bpy.context.scene
    t = film.compositing_node_group
    over = [(nm, n) for s, nm, n in chain.stages(film) if s == 'over'] if t is not None else []
    if not over:
        print(f"[overlay] {film.name}: no 'over' stage in its post chain, nothing to take", flush=True)
        return None
    bad = [(nm, why) for nm, n in over if (why := _why_not_movable(t, nm, n))]
    if bad:
        raise ValueError(f'take_signal_effects({film.name!r}): ' + '; '.join(f'{nm!r} cannot run over the edit: {why}'
                                                                             for nm, why in bad))
    g = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    g.interface.new_socket(name='Image', in_out='INPUT', socket_type='NodeSocketColor')
    g.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    gi, go = g.nodes.new('NodeGroupInput'), g.nodes.new('NodeGroupOutput')
    gi.location = (-300, 0)
    src, x, keyed = gi.outputs['Image'], 0, 0
    for nm, n in over:
        c = _copy_node(n, g)
        c.location = (x, 0)
        x += 260
        g.links.new(src, chain._img_in(c))
        src = chain._img_out(c)
        keyed += _copy_keys(t, g, n.name)
    go.location = (x, 0)
    g.links.new(src, go.inputs['Image'])
    for nm, n in over:
        path = f'nodes["{n.name}"]'
        ad = t.animation_data
        if ad is not None and ad.action is not None:
            for p in {fc.data_path for fc in action_fcurves(ad.action, getattr(ad, 'action_slot', None))
                      if fc.data_path.startswith(path)}:
                remove_fcurves(t, p)
        chain.remove_stage(film, nm)
    dropped = _drop_overlay_stage(film)
    g['eido_signal_from'] = film.name
    film[SIGNAL_PROP] = g.name
    print(f"[overlay] {film.name}: took {', '.join(nm for nm, _n in over)} out of its chain ({keyed} keyed inputs)"
          + (', and its overlay stage' if dropped else '') + f": make_edit_scene(..., signal=bpy.data.node_groups"
          f"[{g.name!r}]) runs them over the film and the overlay", flush=True)
    return g


# ---------------------------------------------------------------------------------------------------- subtitles
def subtitle_cues(lines, pre=0.0, post=0.25, max_chars=None):
    """timebase.load_lines() lines -> [(text, t0, t1)], each held until the next starts (or ``post`` after its
    end). ``max_chars`` splits a long line at word boundaries into consecutive cues, time shared by length."""
    cues = []
    for i, l in enumerate(lines):
        t0 = l['start'] - pre
        nxt = lines[i + 1]['start'] - pre if i + 1 < len(lines) else math.inf
        t1 = min(l['end'] + post, nxt)
        text = l['text']
        if max_chars and len(text) > max_chars:
            parts, cur = [], ''
            for w in text.split():
                if cur and len(cur) + 1 + len(w) > max_chars:
                    parts.append(cur)
                    cur = w
                else:
                    cur = (cur + ' ' + w).strip()
            parts.append(cur)
            tot = sum(len(p) for p in parts)
            a = t0
            for p in parts:
                b = a + (t1 - t0) * len(p) / tot
                cues.append((p, a, b))
                a = b
        else:
            cues.append((text, t0, t1))
    return cues


def _seq_color(c):
    """An sRGB colour -> a text strip's colour: strips hold display values in the sequencer's sRGB space
    (a linearised '#ffd400' renders orange), so the authored hex goes in as is."""
    r, g, b, a = raster.color(c)
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)


def add_subtitles(edit, cues, channel=6, font='Share Tech Mono', size=0.05, color='#ffffff', outline='#000000',
                  outline_width=0.06, shadow=False, box=None, box_margin=0.012, y=0.075, wrap=0.84, align='CENTER'):
    """Plain subtitles as TEXT strips: ``cues`` [(text, t0, t1)] in film seconds; ``size`` the font size as a
    fraction of the frame height; ``y`` the baseline block's bottom as a fraction of the height; ``box`` a colour
    for a backing box. For karaoke styling, keep the ASS route (examples/daisy/captions.py, ffmpeg burn-in)."""
    tb = Timebase.of(edit)
    fnt = bpy.data.fonts.load(str(raster.font_path(font)), check_existing=True)
    out = []
    for i, (text, t0, t1) in enumerate(cues):
        f0 = int(round(tb.frame(t0)))
        f1 = max(f0 + 1, int(round(tb.frame(t1))))
        s = edit.sequence_editor.strips.new_effect(name=f'sub_{i:03d}', type='TEXT', channel=channel,
                                                   frame_start=f0, length=f1 - f0)
        s.text = text
        s.font = fnt
        s.font_size = size * edit.render.resolution_y
        s.color = _seq_color(color)
        s.use_outline = outline is not None
        if outline is not None:
            s.outline_color = _seq_color(outline)
            s.outline_width = outline_width
        s.use_shadow = bool(shadow)
        if box is not None:
            s.use_box = True
            s.box_color = _seq_color(box)
            s.box_margin = box_margin
        s.wrap_width = wrap
        s.location = (0.5, y)
        s.anchor_x, s.anchor_y = 'CENTER', 'BOTTOM'
        s.alignment_x = align
        s.blend_type = 'ALPHA_OVER'
        out.append(s)
    return out


# ---------------------------------------------------------------------------------------------------- the edit
def _strip_from(strips, name, src, channel, frame_start):
    """A movie strip, or an image-sequence strip from a directory / first file of numbered PNGs."""
    p = _abspath(src)
    if p.is_file() and p.suffix.lower() in ('.mp4', '.mov', '.mkv', '.avi', '.webm'):
        return strips.new_movie(name=name, filepath=str(p), channel=channel, frame_start=frame_start)
    if p.is_dir():
        files = sorted(x for x in p.iterdir() if x.suffix.lower() in ('.png', '.jpg', '.exr', '.tif'))
    else:
        stem = p.stem.rstrip('0123456789')
        files = sorted(x for x in p.parent.glob(stem + '*' + p.suffix) if x.stem[len(stem):].isdigit())
    if files and _is_hold(files[0]):                  # a screen's hold file (make_screen), not a frame
        files = files[1:]
    if files and _is_hold(files[-1]):                 # chain_overlay's clear hold after an overlay's last frame
        files = files[:-1]
    if not files:
        raise FileNotFoundError(f'{src}: no frames')
    s = strips.new_image(name=name, filepath=str(files[0]), channel=channel, frame_start=frame_start)
    for f in files[1:]:
        s.elements.append(f.name)
    return s


def make_edit_scene(film, overlays=(), subtitles=None, sounds=(), name='edit', like=None, frame_start=None,
                    subtitle_style=None, signal=None):
    """A sequencer scene that lays the graphics over the rendered film in display space and carries the sound:
    view Standard, sequencer colour space sRGB, so the film's AgX pixels pass through and the graphics land as
    authored. ``film``: a movie or a PNG sequence (directory or first file); ``overlays``: RGBA sequences laid
    ALPHA_OVER in order; ``subtitles``: cues [(text, t0, t1)] (subtitle_cues); ``sounds``: [(path, frame)] or
    [(path, frame, volume)]. ``like``: the film scene, for resolution, rate and frame range.
    ``signal``: the group take_signal_effects took from the film's chain: an adjustment strip over the film and the
    overlays runs it as a COMPOSITOR strip modifier, so the signal effects process picture and HUD together, on the
    display's light (the modifier hands its group the strips with the sRGB transfer undone, and encodes the result
    again, exactly: measured). Subtitles stay above it, clean."""
    like = like or bpy.context.scene
    sc = bpy.data.scenes.new(name)
    r, lr = sc.render, like.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = lr.resolution_x, lr.resolution_y, 100
    r.fps, r.fps_base = lr.fps, lr.fps_base
    if 'eido_frame0' in like:
        sc['eido_frame0'] = like['eido_frame0']
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.sequencer_colorspace_settings.name = 'sRGB'
    r.dither_intensity = 0.0
    r.use_sequencer = True
    sc.sequence_editor_create()
    strips = sc.sequence_editor.strips
    f0 = like.frame_start if frame_start is None else frame_start
    fs = _strip_from(strips, 'film', film, 1, f0)
    fs.colorspace_settings.name = 'sRGB'
    end = fs.frame_final_end - 1
    for i, ov in enumerate(overlays):
        s = _strip_from(strips, f'overlay_{i}', ov, 2 + i, f0)
        s.blend_type = 'ALPHA_OVER'
        s.colorspace_settings.name = 'sRGB'
        s.alpha_mode = 'STRAIGHT'
    if signal is not None:
        adj = strips.new_effect(name='signal', type='ADJUSTMENT', channel=2 + len(overlays), frame_start=f0,
                                length=end - f0 + 1)
        mod = adj.modifiers.new(name='signal', type='COMPOSITOR')
        mod.node_group = signal
    if subtitles:
        add_subtitles(sc, subtitles, channel=2 + len(overlays) + 1, **(subtitle_style or {}))
    for j, snd in enumerate(sounds):
        path, frame = snd[0], snd[1]
        s = strips.new_sound(name=f'sound_{j}', filepath=str(_abspath(path)), channel=20 + j, frame_start=int(frame))
        if len(snd) > 2:
            s.volume = float(snd[2])
    sc.frame_start, sc.frame_end = f0, end
    return sc


def render_edit(edit, out, video=True, crf='PERC_LOSSLESS', audio=True, frames=None):
    """Render the edit scene: an H.264 MP4 with AAC sound (``video``), or RGBA-free PNG frames to a folder."""
    out = _abspath(out)
    r = edit.render
    keep = edit.frame_start, edit.frame_end
    if frames:
        edit.frame_start, edit.frame_end = frames
    if video:
        out.parent.mkdir(parents=True, exist_ok=True)
        r.image_settings.media_type = 'VIDEO'
        r.image_settings.file_format = 'FFMPEG'
        r.ffmpeg.format = 'MPEG4'
        r.ffmpeg.codec = 'H264'
        r.ffmpeg.constant_rate_factor = crf
        r.ffmpeg.ffmpeg_preset = 'GOOD'
        r.ffmpeg.audio_codec = 'AAC' if audio else 'NONE'
        r.ffmpeg.audio_bitrate = 320
        r.ffmpeg.audio_mixrate = 48000
        r.ffmpeg.audio_channels = 'STEREO'
        r.use_file_extension = False
        r.filepath = str(out)
    else:
        out.mkdir(parents=True, exist_ok=True)
        r.image_settings.media_type = 'IMAGE'
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGB'
        r.filepath = str(out / 'edit_####')
        r.use_file_extension = True
    try:
        bpy.ops.render.render(animation=True, scene=edit.name)
    finally:
        edit.frame_start, edit.frame_end = keep
    return out
