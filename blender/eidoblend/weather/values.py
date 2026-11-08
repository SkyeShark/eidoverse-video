"""The per-frame shader values of the weather (the WebGPU uniforms rainK, rainLight, rainColor, wetness, ...), as one
shader node group whose Value nodes are keyed per frame. Every weather material reads them from here, so a saved
.blend plays the weather with no Python: eido_rain, eido_splash and every material wrapped with eido_wet.
"""
import bpy

from ._graph import shader_group

NAME = 'eido_weather_values'
SCALARS = ('time', 'rain_k', 'rain_light', 'rain_r', 'rain_g', 'rain_b', 'wetness', 'surface_water', 'puddle_k',
           'wet_tint_r', 'wet_tint_g', 'wet_tint_b', 'src_x', 'src_y', 'src_z', 'moist_cx', 'moist_cy', 'moist_span',
           'shelter_on', 'sh_x0', 'sh_y0', 'sh_sx', 'sh_sy', 'sh_w', 'sh_h', 'sh_dx', 'sh_dy', 'sh_dz', 'wet_target')
CONSTANT = ('moist_cx', 'moist_cy', 'moist_span', 'shelter_on', 'sh_x0', 'sh_y0', 'sh_sx', 'sh_sy', 'sh_w', 'sh_h',
            'sh_dx', 'sh_dy', 'sh_dz')
DEFAULTS = dict(rain_r=0.72, rain_g=0.78, rain_b=0.86, rain_light=1.0, puddle_k=1.0, wet_tint_r=1.0, wet_tint_g=1.0,
                wet_tint_b=1.0, src_z=1.0, moist_span=2048.0, sh_sx=1.0, sh_sy=1.0, sh_w=1.0, sh_h=1.0, sh_dz=-1.0)
OUTPUTS = (('Time', 'NodeSocketFloat'), ('Rain K', 'NodeSocketFloat'), ('Rain Light', 'NodeSocketFloat'),
           ('Rain Color', 'NodeSocketColor'), ('Wetness', 'NodeSocketFloat'), ('Surface Water', 'NodeSocketFloat'),
           ('Puddle K', 'NodeSocketFloat'), ('Wet Tint', 'NodeSocketColor'), ('Source Dir', 'NodeSocketVector'),
           ('Moisture Center', 'NodeSocketVector'), ('Moisture Span', 'NodeSocketFloat'),
           ('Shelter On', 'NodeSocketFloat'), ('Shelter Origin', 'NodeSocketVector'),
           ('Shelter Size', 'NodeSocketVector'), ('Shelter Res', 'NodeSocketVector'),
           ('Shelter Dir', 'NodeSocketVector'), ('Wet Target', 'NodeSocketFloat'))


def values_group():
    """The group (built once per file): Value nodes named after SCALARS, combined into its outputs."""
    if NAME in bpy.data.node_groups:
        return bpy.data.node_groups[NAME]
    tree, gi, go = shader_group(NAME, [], OUTPUTS)
    nodes = {}
    for i, k in enumerate(SCALARS):
        n = tree.nodes.new('ShaderNodeValue')
        n.name = n.label = k
        n.outputs[0].default_value = DEFAULTS.get(k, 0.0)
        n.location = (-600, 400 - i * 60)
        nodes[k] = n.outputs[0]

    def comb(kind, a, b, c, x):
        n = tree.nodes.new(kind)
        n.location = (-300, x)
        for i, s in enumerate((a, b, c)):
            tree.links.new(nodes[s], n.inputs[i])
        return n.outputs[0]

    link = tree.links.new
    link(nodes['time'], go.inputs['Time'])
    link(nodes['rain_k'], go.inputs['Rain K'])
    link(nodes['rain_light'], go.inputs['Rain Light'])
    link(comb('ShaderNodeCombineColor', 'rain_r', 'rain_g', 'rain_b', 300), go.inputs['Rain Color'])
    link(nodes['wetness'], go.inputs['Wetness'])
    link(nodes['surface_water'], go.inputs['Surface Water'])
    link(nodes['puddle_k'], go.inputs['Puddle K'])
    link(comb('ShaderNodeCombineColor', 'wet_tint_r', 'wet_tint_g', 'wet_tint_b', 100), go.inputs['Wet Tint'])
    link(comb('ShaderNodeCombineXYZ', 'src_x', 'src_y', 'src_z', -100), go.inputs['Source Dir'])
    link(comb('ShaderNodeCombineXYZ', 'moist_cx', 'moist_cy', 'moist_span', -300), go.inputs['Moisture Center'])
    link(nodes['moist_span'], go.inputs['Moisture Span'])
    link(nodes['shelter_on'], go.inputs['Shelter On'])
    link(comb('ShaderNodeCombineXYZ', 'sh_x0', 'sh_y0', 'shelter_on', -500), go.inputs['Shelter Origin'])
    link(comb('ShaderNodeCombineXYZ', 'sh_sx', 'sh_sy', 'shelter_on', -700), go.inputs['Shelter Size'])
    link(comb('ShaderNodeCombineXYZ', 'sh_w', 'sh_h', 'shelter_on', -900), go.inputs['Shelter Res'])
    link(comb('ShaderNodeCombineXYZ', 'sh_dx', 'sh_dy', 'sh_dz', -1100), go.inputs['Shelter Dir'])
    link(nodes['wet_target'], go.inputs['Wet Target'])       # the eidoverse wetness: w.wet x k, eased, no time constant
    return tree


def key_values(frames, rows):
    """Key every value of the group: rows is {name: [value per frame]} (LINEAR; the moisture centre CONSTANT)."""
    from .keys import key_series, changes_only
    tree = values_group()
    for k in SCALARS:
        if k not in rows:
            continue
        path = f'nodes["{k}"].outputs[0].default_value'
        if k in CONSTANT:
            f2, v2 = changes_only(frames, rows[k])
            key_series(tree, path, f2, v2, 'CONSTANT')
        else:
            key_series(tree, path, frames, rows[k], 'LINEAR')
    return tree


def add_values_node(nt, x=-900, y=0):
    """A group node of eido_weather_values in a material's tree."""
    n = nt.nodes.new('ShaderNodeGroup')
    n.node_tree = values_group()
    n.location = (x, y)
    n.label = 'weather values'
    return n
