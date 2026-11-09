"""Distance fog in the sky's colour: the Blender form of three.js scene.fog under the eidoverse sky.

The WebGPU sky never owns fog density (the scene does) but writes the fog COLOUR every frame from the
weathered horizon (applyToLights: horizon * fog tint * (0.5 + int * 0.12)). Here the compositor blends
the rendered geometry toward that keyed colour by the Depth pass, with three's FogExp2 (1 - exp(-(d z)^2))
or linear Fog ((z - near) / (far - near)), and leaves the sky itself unfogged (three's domes use fog: false).
The sky elements are unfogged too, as WebGPU's are (fog: false on every ring and moon material): the shattered moon's
materials write 1 to the 'eido_sky_element' AOV (sky_view.mark_sky_element), which the fog reads; the ringworld's
band reaches the frame inside the sky's camera layer, where the depth is the sky's.

The fog is spliced in right after Render Layers: whatever read the render image before (another family's
glare or grade chain, or the tree's output) now reads the fogged image, so a post chain stays connected.
"""
import bpy

from .sky_view import SKY_ELEMENT_AOV

TREE = 'eido_sky_fog'


def _input_socket(node, identifier):
    return next(s for s in node.inputs if s.identifier == identifier)


def setup_fog(scene, density=0.0004, kind='exp2', near=1.0, far=1000.0):
    scene.render.use_compositing = True
    for vl in scene.view_layers:
        vl.use_pass_z = True
        if not any(a.name == SKY_ELEMENT_AOV for a in vl.aovs):
            aov = vl.aovs.add()
            aov.name = SKY_ELEMENT_AOV
            aov.type = 'VALUE'
    tree = scene.compositing_node_group
    if tree is None:
        tree = bpy.data.node_groups.new(TREE, 'CompositorNodeTree')
        scene.compositing_node_group = tree
    N, L = tree.nodes, tree.links
    if not any(s.in_out == 'OUTPUT' and s.name == 'Image' for s in tree.interface.items_tree):
        tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = next((n for n in N if n.bl_idname == 'CompositorNodeRLayers'), None) or N.new('CompositorNodeRLayers')
    go = next((n for n in N if n.bl_idname == 'NodeGroupOutput'), None) or N.new('NodeGroupOutput')
    # the sockets the fogged image feeds: those our previous fog fed (a re-bake), else those that read the
    # render image now (then they are re-routed through the fog), else the tree's output
    old = N.get('eido_fog_mix')
    if old is not None:
        feeds = [l for l in L if l.from_node.name == old.name]
    else:
        feeds = [l for l in L if l.from_node.name == rl.name and l.from_socket.name == 'Image']
    targets = [(l.to_node.name, l.to_socket.identifier) for l in feeds if not l.to_node.name.startswith('eido_fog')]
    if old is None:
        for l in feeds:
            L.remove(l)
    for n in [n for n in N if n.name.startswith('eido_fog')]:
        N.remove(n)
    if not targets:
        targets = [(go.name, go.inputs['Image'].identifier)]

    def node(kind_, name, **kw):
        n = N.new(kind_)
        n.name = n.label = name
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def math(op, a, b, name):
        n = node('ShaderNodeMath', name, operation=op)
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    depth = rl.outputs['Depth']
    if kind == 'exp2':
        dz = math('MULTIPLY', depth, float(density), 'eido_fog_dz')
        f = math('SUBTRACT', 1.0, math('EXPONENT', math('MULTIPLY', math('MULTIPLY', dz, dz, 'eido_fog_sq'), -1.0,
                                                         'eido_fog_neg'), 0.0, 'eido_fog_exp'), 'eido_fog_f')
    else:
        f = math('DIVIDE', math('SUBTRACT', depth, float(near), 'eido_fog_zn'), float(far - near), 'eido_fog_lin')
    f = math('MINIMUM', math('MAXIMUM', f, 0.0, 'eido_fog_lo'), 1.0, 'eido_fog_hi')
    geometry = math('LESS_THAN', depth, 1e8, 'eido_fog_geometry')          # the sky keeps its own colour
    fk = math('MULTIPLY', f, geometry, 'eido_fog_k')
    sky_el = rl.outputs.get(SKY_ELEMENT_AOV)
    if sky_el is not None:                                                   # and so do the sky elements
        fk = math('MULTIPLY', fk, math('SUBTRACT', 1.0, sky_el, 'eido_fog_not_sky_element'), 'eido_fog_k_local')
    col = node('CompositorNodeRGB', 'eido_fog_color')
    mix = node('ShaderNodeMix', 'eido_fog_mix', data_type='RGBA')
    L.new(fk, mix.inputs['Factor'])
    L.new(rl.outputs['Image'], mix.inputs['A'])
    L.new(col.outputs[0], mix.inputs['B'])
    for node_name, ident in targets:
        L.new(mix.outputs['Result'], _input_socket(N[node_name], ident))
    return col


def key_fog(color_node, frames):
    """Key the fog colour per frame (CONSTANT, from frame f on); only the fog's own F-curves are touched."""
    from .world_nodes import constant_interpolation, remove_fcurves
    tree = color_node.id_data
    path = 'nodes["%s"]' % color_node.name
    remove_fcurves(tree, path)                  # a re-bake replaces the old keys instead of interleaving them
    for fr in frames:
        c = fr['lights']['fog_color']
        color_node.outputs[0].default_value = (c[0], c[1], c[2], 1.0)
        color_node.outputs[0].keyframe_insert('default_value', frame=fr['frame'])
    constant_interpolation(tree, prefix=path)
