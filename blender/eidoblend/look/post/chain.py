"""look/post/chain.py: the compositor graph in a fixed order, the WebGPU post chain's order kept.

    source (Render Layers) -> 'prebloom' effects -> bloom (Glare) -> 'under' effects -> overlay (Alpha Over: a HUD)
        -> 'over' effects -> Output

('prebloom' is WebGPU's _autoEnhancePreBloomHook: lensflare and anamorphic_flare, which the bloom then softens.)

All of it works on scene-linear light; AgX (the scene's view transform) applies after the whole graph, as three's tone
map applied after its overlay and its effect hooks (which all ran on the lit HDR frame).

    from eidoblend.look.post import chain
    chain.set_bloom(scene, strength=0.25, size=0.5, threshold=3.0)       # Glare 'Bloom'; set_bloom(scene, None) removes
    chain.add_stage(scene, 'under', 'grade', node)                        # any node with an Image in and out
    chain.set_overlay(scene, image_node)                                  # alpha over everything below it
    chain.stages(scene)                                                   # [(slot, name, node)] in order
    chain.source_pass(scene, 'Depth')                                     # a pass of the source (enabled if needed)
    chain.use_saved_frames(scene, '//raw/frame_####.exr')                 # the post over rendered frames, not a render

Stages are nodes named '<slot>:<name>', ordered by slot then by when they were added; relink() rewires them, so adding
or removing one never leaves a dangling link. A node can ride along with a stage (`node['look_input_of'] = name`): it
gets the same input as that stage on every relink (a history writer recording what an effect sees). With no stages
the scene renders without a compositor at all (the house's look: EEVEE + AgX + motion blur + DOF, no post pass).

The source is the scene's Render Layers, or with use_saved_frames() an image sequence (a multilayer EXR holding
Combined, and Depth / Normal when a look needs them): the per-frame compositing pass over saved output. The effects
cannot tell the difference, so a look can be re-graded over a rendered film without rendering it again.
"""
import bpy

SLOTS = ('prebloom', 'bloom', 'under', 'overlay', 'over')
TREE = 'look_post'
SOURCE = 'look:render'
_PASS_PROP = {'Depth': 'use_pass_z', 'Normal': 'use_pass_normal', 'Vector': 'use_pass_vector',
              'Mist': 'use_pass_mist', 'Diffuse Direct': 'use_pass_diffuse_direct'}


def tree(scene, create=True):
    """The scene's compositor tree (made, with Render Layers -> Group Output, when missing)."""
    t = scene.compositing_node_group
    if t is None and create:
        t = bpy.data.node_groups.new(TREE, 'CompositorNodeTree')
        if not any(s.in_out == 'OUTPUT' for s in t.interface.items_tree if s.item_type == 'SOCKET'):
            t.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = t.nodes.new('CompositorNodeRLayers')
        rl.name = SOURCE
        rl.location = (-400, 0)
        rl.scene = scene
        out = t.nodes.new('NodeGroupOutput')
        out.name = 'look:output'
        out.location = (1200, 0)
        t.links.new(rl.outputs['Image'], out.inputs[0])
        scene.compositing_node_group = t
    if t is not None:
        scene.render.use_compositing = True
    return t


def _ends(t):
    rl = t.nodes.get(SOURCE) or next(n for n in t.nodes if n.bl_idname == 'CompositorNodeRLayers')
    out = t.nodes.get('look:output') or next(n for n in t.nodes if n.bl_idname == 'NodeGroupOutput')
    return rl, out


def source(scene):
    """The node every chain starts from (Render Layers, or the saved-frames Image node)."""
    return _ends(tree(scene))[0]


def _src_image(n):
    return n.outputs['Image'] if 'Image' in n.outputs else n.outputs[0]


def _img_in(n):
    for s in n.inputs:
        if s.type == 'RGBA' and s.name in ('Image', 'Color', 'Background'):
            return s
    return next(s for s in n.inputs if s.type == 'RGBA')


def _img_out(n):
    for s in n.outputs:
        if s.type == 'RGBA' and s.name in ('Image', 'Color'):
            return s
    return next(s for s in n.outputs if s.type == 'RGBA')


def stages(scene):
    t = scene.compositing_node_group
    if t is None:
        return []
    out = []
    for n in t.nodes:
        if ':' in n.name and n.get('look_slot') in SLOTS:
            out.append((SLOTS.index(n['look_slot']), int(n.get('look_order', 0)), n))
    out.sort(key=lambda x: (x[0], x[1]))
    return [(SLOTS[s], n.name.split(':', 1)[1], n) for s, _o, n in out]


def relink(scene):
    """Wire the source -> every stage in order -> Group Output, through each stage's Image socket; a node riding
    along with a stage (look_input_of) gets that stage's input too."""
    t = tree(scene)
    rl, out = _ends(t)
    st = stages(scene)
    riders = {}
    for n in t.nodes:
        if n.get('look_input_of'):
            riders.setdefault(n['look_input_of'], []).append(n)
    for _slot, _name, n in st:
        for s in list(_img_in(n).links):
            t.links.remove(s)
    for s in list(out.inputs[0].links):
        t.links.remove(s)
    src = _src_image(rl)
    x = -150
    for _slot, name, n in st:
        t.links.new(src, _img_in(n))
        for r in riders.get(name, ()):
            sock = _img_in(r) if any(s.type == 'RGBA' for s in r.inputs) else r.inputs[0]
            for s in list(sock.links):
                t.links.remove(s)
            t.links.new(src, sock)
        n.location = (x, 0)
        x += 260
        src = _img_out(n)
    t.links.new(src, out.inputs[0])
    out.location = (x, 0)
    return st


def add_stage(scene, slot, name, node):
    """Put `node` (already in the scene's compositor tree) into the chain at `slot`, after that slot's stages."""
    if slot not in SLOTS:
        raise ValueError(f'slot {slot!r}: one of {SLOTS}')
    order = 1 + max([int(n.get('look_order', 0)) for _s, _n, n in stages(scene)] or [0])
    node.name = f'{slot}:{name}'
    node.label = name
    node['look_slot'] = slot
    node['look_order'] = order
    relink(scene)
    return node


def remove_stage(scene, name):
    t = scene.compositing_node_group
    if t is None:
        return
    for _slot, nm, n in stages(scene):
        if nm == name:
            for r in [r for r in t.nodes if r.get('look_input_of') == name]:
                t.nodes.remove(r)
            t.nodes.remove(n)
    relink(scene)
    if not stages(scene):
        scene.render.use_compositing = False


# ------------------------------------------------------------------------------------------------- the source
def source_pass(scene, name):
    """The source's output socket for a pass ('Depth', 'Normal', ...). For Render Layers the view layer's pass is
    switched on, and the node is made again when its socket predates the pass (a Render Layers node keeps the
    sockets it was made with: stack-notes.md); its links move to the new node. None when the source has no such
    pass (a saved frame without it): the effects then fall back as WebGPU did without a depth or normal buffer."""
    t = tree(scene)
    src = _ends(t)[0]
    if src.bl_idname != 'CompositorNodeRLayers':
        extra = t.nodes.get(f'{SOURCE}:{name}')                 # a pass saved as its own sequence
        if extra is not None:
            return extra.outputs['Image']
        s = src.outputs.get(name)
        return s if (s is not None and s.enabled) else None
    vl = scene.view_layers[src.layer] if src.layer in scene.view_layers else scene.view_layers[0]
    prop = _PASS_PROP.get(name)
    if prop and not getattr(vl, prop):
        setattr(vl, prop, True)
    s = src.outputs.get(name)
    if s is not None and s.enabled and not getattr(s, 'is_unavailable', False):
        return s
    new = _remake_render_layers(scene, t, src)
    s = new.outputs.get(name)
    return s if (s is not None and s.enabled) else None


def _remake_render_layers(scene, t, old):
    keep = [(lk.from_socket.name, lk.to_socket) for lk in t.links if lk.from_node == old]
    loc, layer = tuple(old.location), old.layer
    t.nodes.remove(old)
    rl = t.nodes.new('CompositorNodeRLayers')
    rl.name = SOURCE
    rl.location = loc
    rl.scene = scene
    rl.layer = layer
    for sname, to in keep:
        if sname in rl.outputs:
            t.links.new(rl.outputs[sname], to)
    return rl


def _sequence_node(t, name, filepath, frame_start, loc):
    im = bpy.data.images.load(bpy.path.abspath(filepath), check_existing=True)
    im.source = 'SEQUENCE'
    n = t.nodes.get(name) or t.nodes.new('CompositorNodeImage')
    n.name = n.label = name
    n.location = loc
    n.image = im
    n.frame_start = int(frame_start)
    n.frame_duration = 1000000
    n.use_auto_refresh = True
    return n


def save_frames_passes(scene, directory, passes=('Depth', 'Normal'), name='frame'):
    """File Outputs writing the render's Combined (RGBA half) and each pass (Depth 32-bit: a half float cannot hold a
    sky's depth) as sequences beside each other, one node per pass (a multilayer File Output keeps only its first
    item: stack-notes.md), for use_saved_frames later. Returns {pass: filename pattern}."""
    t = tree(scene)
    rl = _ends(t)[0]
    out = {}
    for p in ('Combined',) + tuple(passes):
        sock = rl.outputs['Image'] if p == 'Combined' else source_pass(scene, p)
        if sock is None:
            continue
        rl = _ends(t)[0]
        fo = t.nodes.get(f'look:save:{p}') or t.nodes.new('CompositorNodeOutputFile')
        fo.name = fo.label = f'look:save:{p}'
        fo.location = (-150, -300 - 140 * len(out))
        if not len(fo.file_output_items):
            fo.file_output_items.new('RGBA' if p in ('Combined', 'Normal') else 'FLOAT', p.lower())
        fo.directory = bpy.path.abspath(directory).rstrip('\\/') + '/'
        fo.file_name = f'{name}_####_'
        fmt = fo.format
        fmt.media_type = 'IMAGE'
        fmt.file_format = 'OPEN_EXR'
        fmt.color_depth = '32' if p == 'Depth' else '16'
        fmt.exr_codec = 'ZIP'
        fo.save_as_render = False
        t.links.new(sock, fo.inputs[0])
        out[p] = f'{name}_####_{p.lower()}.exr'
    return out


def use_saved_frames(scene, filepath, frame_start=1, passes=None):
    """Run the chain over an image sequence instead of the render (the per-frame compositing pass over saved output):
    `filepath` is any frame of the sequence. passes: {'Depth': path, 'Normal': path} of sequences saved beside it
    (save_frames_passes writes all three); source_pass() then hands those to the looks that read them.
    The scene's own render still runs; give it nothing to draw (an empty view layer) when only the post is wanted."""
    t = tree(scene)
    for i, (p, path) in enumerate((passes or {}).items()):
        _sequence_node(t, f'{SOURCE}:{p}', path, frame_start, (-400, -260 - 160 * i))
    old = _ends(t)[0]
    im = bpy.data.images.load(bpy.path.abspath(filepath), check_existing=True)
    im.source = 'SEQUENCE'
    keep = [(lk.from_socket.name, lk.to_socket) for lk in t.links if lk.from_node == old]
    loc = tuple(old.location)
    t.nodes.remove(old)
    n = t.nodes.new('CompositorNodeImage')
    n.name = SOURCE
    n.location = loc
    n.image = im
    n.frame_start = int(frame_start)
    n.frame_duration = 1000000
    n.use_auto_refresh = True
    if 'Combined' in n.outputs and 'Image' not in n.outputs:
        alias = {'Image': 'Combined'}
    else:
        alias = {}
    for sname, to in keep:
        sname = alias.get(sname, sname)
        if sname in n.outputs:
            t.links.new(n.outputs[sname], to)
    relink(scene)
    return n


def use_render(scene):
    """Back to the scene's own Render Layers as the source."""
    t = tree(scene)
    old = _ends(t)[0]
    if old.bl_idname == 'CompositorNodeRLayers':
        return old
    keep = [(lk.from_socket.name, lk.to_socket) for lk in t.links if lk.from_node == old]
    loc = tuple(old.location)
    t.nodes.remove(old)
    rl = t.nodes.new('CompositorNodeRLayers')
    rl.name = SOURCE
    rl.location = loc
    rl.scene = scene
    for sname, to in keep:
        sname = {'Combined': 'Image'}.get(sname, sname)
        if sname in rl.outputs:
            t.links.new(rl.outputs[sname], to)
    relink(scene)
    return rl


# ------------------------------------------------------------------------------------------------- glare, overlay
def set_bloom(scene, strength=0.25, size=0.5, threshold=1.0, type='Bloom', quality='High', smoothness=0.1,
              maximum=10.0, saturation=1.0, clamp=True):
    """The Glare node as the chain's bloom (UnrealBloom's strength / radius / threshold -> Strength / Size /
    Threshold). The threshold is scene-linear light before AgX, as three's was before its tone map. clamp/maximum
    keep NaN/Inf and fireflies from blooming the frame white. strength=None removes it."""
    if strength is None:
        remove_stage(scene, 'bloom')
        return None
    t = tree(scene)
    n = next((n for _s, nm, n in stages(scene) if nm == 'bloom'), None)
    if n is None:
        n = t.nodes.new('CompositorNodeGlare')
        add_stage(scene, 'bloom', 'bloom', n)
    vals = {'Type': type, 'Quality': quality, 'Threshold': float(threshold), 'Smoothness': float(smoothness),
            'Clamp': bool(clamp), 'Maximum': float(maximum), 'Strength': float(strength), 'Saturation': float(saturation),
            'Size': float(size)}
    for k, v in vals.items():
        n.inputs[k].default_value = v
    return n


def set_overlay(scene, foreground_node, factor=1.0):
    """An overlay (a HUD, captions, a second scene's render) alpha-over'd on everything below it. foreground_node: a
    node in the compositor tree with an image output (an Image node, a Render Layers of another scene...)."""
    t = tree(scene)
    ao = next((n for _s, nm, n in stages(scene) if nm == 'overlay'), None)
    if ao is None:
        ao = t.nodes.new('CompositorNodeAlphaOver')
        add_stage(scene, 'overlay', 'overlay', ao)
    ao.inputs['Factor'].default_value = float(factor)
    t.links.new(_img_out(foreground_node), ao.inputs['Foreground'])
    return ao
