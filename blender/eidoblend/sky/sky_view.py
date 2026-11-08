"""The bake camera's projection, shared by the world and every material that reads a camera layer.

eido_sky_view       a node group whose outputs are the bake camera of the frame (Right, Up, Forward, TanX, TanY),
                    keyed per frame CONSTANT and held over [f, f+1) with the image sequences (world_nodes, P6)
eido_sky_overlay    what draws OVER a sky element for a camera ray: the shield and the clouds of the frame's camera
                    layers, premultiplied (Color, Alpha). The ringworld's band, walls and cloud sheet and the shattered
                    moon composite it over themselves, so the clouds always draw in front of them, as WebGPU's draw
                    order did (sky elements -99.x, cloud dome -98). With a cloud dome the dome draws the clouds over
                    whatever lies beyond its radius, so the overlay then keeps only the shield there.

    surface = overlay_opaque(g, shader)              # opaque: (1 - a) * surface + Color
    emission, alpha = overlay_blended(g, c, alpha)   # blended: c (1 - a) + alpha * Color over (1 - alpha) * behind
"""
import bpy

from .nodes import Graph, new_group

VIEW = 'eido_sky_view'
OVERLAY = 'eido_sky_overlay'


def view_group():
    """eido_sky_view: the keyed bake-camera basis (Combine XYZ / Value nodes inside; key their inputs)."""
    ng = bpy.data.node_groups.get(VIEW)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(VIEW, 'ShaderNodeTree')
    go = ng.nodes.new('NodeGroupOutput')
    go.location = (500, 0)
    for i, key in enumerate(('Right', 'Up', 'Forward')):
        ng.interface.new_socket(key, in_out='OUTPUT', socket_type='NodeSocketVector')
        n = ng.nodes.new('ShaderNodeCombineXYZ')
        n.name = n.label = 'eido_cam_' + key.lower()
        n.location = (0, -i * 160)
        ng.links.new(n.outputs['Vector'], go.inputs[key])
    for i, key in enumerate(('TanX', 'TanY')):
        ng.interface.new_socket(key, in_out='OUTPUT', socket_type='NodeSocketFloat')
        n = ng.nodes.new('ShaderNodeValue')
        n.name = n.label = 'eido_cam_' + key.lower()
        n.location = (0, -500 - i * 100)
        n.outputs[0].default_value = 1.0
        ng.links.new(n.outputs[0], go.inputs[key])
    return ng


def view_handles():
    ng = view_group()
    basis = {k: ng.nodes['eido_cam_' + k.lower()] for k in ('Right', 'Up', 'Forward')}
    tans = {k: ng.nodes['eido_cam_' + k.lower()] for k in ('TanX', 'TanY')}
    return basis, tans


def project(g, direction):
    """The camera-layer UV (and 'valid') of a world direction, through eido_sky_view: the world's projection."""
    from .world_nodes import _projection_group
    v = g.group(view_group())
    p = g.group(_projection_group(), Direction=direction, Right=v.outputs['Right'], Up=v.outputs['Up'],
                Forward=v.outputs['Forward'], TanX=v.outputs['TanX'], TanY=v.outputs['TanY'])
    return p.outputs['UV'], p.outputs['Valid']


OVERLAY_OUTPUTS = (('Color', 'NodeSocketColor'), ('Alpha', 'NodeSocketFloat'),
                   ('ColorAll', 'NodeSocketColor'), ('AlphaAll', 'NodeSocketFloat'))


def ensure_overlay_group():
    """The eido_sky_overlay group the sky-element materials are built with: empty (no overlay) until a bake fills
    it in place, so the materials keep their links to it."""
    ng = bpy.data.node_groups.get(OVERLAY)
    if ng is not None and 'ColorAll' not in {i.name for i in ng.interface.items_tree}:
        bpy.data.node_groups.remove(ng)              # an older two-output group: rebuild with all four
        ng = None
    if ng is None:
        ng, gi, go = new_group(OVERLAY, [], list(OVERLAY_OUTPUTS))
        for item in ng.interface.items_tree:
            if getattr(item, 'in_out', None) == 'OUTPUT':
                item.default_value = (0.0, 0.0, 0.0, 1.0) if item.name.startswith('Color') else 0.0
        for name, _t in OVERLAY_OUTPUTS:
            go.inputs[name].default_value = (0.0, 0.0, 0.0, 1.0) if name.startswith('Color') else 0.0
    return ng


def overlay_group(cloud_img, shield_img=None, frame_start=1, n_frames=1, dome_radius=None):
    """eido_sky_overlay: the shield and clouds over a sky element, premultiplied, for camera rays only (Light Path
    'Is Camera Ray', probe_eevee_facts.py F2). Color / Alpha are for OPAQUE elements: with a cloud dome, beyond its
    radius the dome draws the clouds over them, so only the shield remains here. ColorAll / AlphaAll keep every
    cloud for BLENDED elements: the dome has already drawn its clouds into what such an element blends over, and
    c (1 - a) + alpha C over (1 - alpha) (C + (1 - a) B) is exactly C + (1 - a)(c + (1 - alpha) B), the clouds over
    the element over the sky. Rebuilt in place: the materials' links survive a re-bake."""
    from .world_nodes import _set_user
    ng = ensure_overlay_group()
    ng.nodes.clear()
    go = ng.nodes.new('NodeGroupOutput')
    go.location = (1800, 0)
    g = Graph(ng)
    geo = g.node('ShaderNodeNewGeometry')
    view_dir = g.vscale(geo.outputs['Incoming'], -1.0)
    uv, valid = project(g, view_dir)
    lp = g.node('ShaderNodeLightPath')
    gate = g.mul(lp.outputs['Is Camera Ray'], valid)
    ct = g.image(cloud_img, uv, extension='EXTEND', label='eido_overlay_cloud')
    _set_user(ct, frame_start, n_frames)
    cr_all = ct.outputs['Color']
    ca_all = ct.outputs['Alpha']
    cr, ca = cr_all, ca_all
    if dome_radius:
        cam = g.node('ShaderNodeCameraData')
        near = g.math('LESS_THAN', cam.outputs['View Distance'], float(dome_radius))
        cr = g.vscale(cr_all, near)
        ca = g.mul(ca_all, near)
    st = None
    if shield_img is not None:
        st = g.image(shield_img, uv, extension='EXTEND', label='eido_overlay_shield')
        _set_user(st, frame_start, n_frames)

    def over_shield(c_rgb, c_a):
        if st is None:
            return c_rgb, c_a
        # clouds over the shield: C + (1 - Ca) S
        return (g.vadd(c_rgb, g.vscale(st.outputs['Color'], g.one_minus(c_a))),
                g.one_minus(g.mul(g.one_minus(c_a), g.one_minus(st.outputs['Alpha']))))

    for (cn, an), (c_rgb, c_a) in ((('Color', 'Alpha'), (cr, ca)), (('ColorAll', 'AlphaAll'), (cr_all, ca_all))):
        rgb, alpha = over_shield(c_rgb, c_a)
        g.link(g.vscale(rgb, gate), go.inputs[cn])
        g.link(g.mul(alpha, gate), go.inputs[an])
    return ng


def overlay_opaque(g, shader):
    """(1 - a) * shader + Color: an opaque sky element under the shield and clouds."""
    o = g.group(ensure_overlay_group())
    black = g.node('ShaderNodeEmission')
    black.inputs['Strength'].default_value = 0.0
    mix = g.node('ShaderNodeMixShader')
    g.link(o.outputs['Alpha'], mix.inputs['Fac'])
    g.link(shader, mix.inputs[1])
    g.link(black.outputs[0], mix.inputs[2])
    em = g.node('ShaderNodeEmission')
    g.link(o.outputs['Color'], em.inputs['Color'])
    em.inputs['Strength'].default_value = 1.0
    add = g.node('ShaderNodeAddShader')
    g.link(mix.outputs[0], add.inputs[0])
    g.link(em.outputs[0], add.inputs[1])
    return add.outputs[0]


def blended_surface(g, emission, alpha, with_overlay=True):
    """A Blended surface: emission (premultiplied) over (1 - alpha) * behind; with the overlay composited for camera
    rays as c (1 - a) + alpha * C (the behind it lands on already carries the overlay, or the dome's clouds: the
    unmasked ColorAll / AlphaAll pair, see overlay_group)."""
    if with_overlay:
        o = g.group(ensure_overlay_group())
        emission = g.vadd(g.vscale(emission, g.one_minus(o.outputs['AlphaAll'])),
                          g.vscale(o.outputs['ColorAll'], alpha))
    em = g.node('ShaderNodeEmission')
    g.link(emission, em.inputs['Color'])
    em.inputs['Strength'].default_value = 1.0
    tr = g.node('ShaderNodeBsdfTransparent')
    one_minus = g.one_minus(alpha)
    g.link(g.comb(one_minus, one_minus, one_minus), tr.inputs['Color'])
    add = g.node('ShaderNodeAddShader')
    g.link(tr.outputs[0], add.inputs[0])
    g.link(em.outputs[0], add.inputs[1])
    return add.outputs[0]
