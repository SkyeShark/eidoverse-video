"""eidoblend.characters.claudesona.look: a VRM's MToon look as the VRM add-on imports it, or a PBR look, switchable
(tools-guides/claudesona.md, "MToon or PBR"). Which one a film uses is the artist's call; MToon stays the default.

    from eidoblend.characters.claudesona.look import set_look
    set_look(me, 'pbr')          # every MToon material also renders through a Principled BSDF
    set_look(me, 'mtoon')        # back to the add-on's MToon (and its outlines)

How the add-on's MToon renders in EEVEE (measured): each material has a top-level glTF-compatible Principled output
(target ALL: what Cycles and exporters see) and an MToon output group whose INSIDE holds an EEVEE-target Material
Output; EEVEE flattens groups before choosing the output, and an output for its own target wins over ALL, so EEVEE draws
MToon. The PBR look adds its own EEVEE output fed by a Principled BSDF, and mutes the MToon group node in that material
(a muted group is not flattened, so its inner output is gone); the add-on's outline modifiers are switched off (an ink
outline on a lit PBR surface reads as a cartoon). The Principled takes:
    Base Color   MToon's Lit Color x Lit Color Texture Color (whatever feeds them: the wardrobe's paints included;
                 refresh_pbr re-reads them after a repaint)
    Metallic, Roughness, IOR, Normal    the glTF-compatible shader's own (the VRM's pbrMetallicRoughness, its normal map)
    Emission     MToon's Emissive Factor x Emissive Texture at Emissive Strength
    Alpha        Lit Color Alpha x the texture's alpha, for materials whose MToon alpha mode is not opaque
"""

import bpy

PBR = 'pbr.'


def _mtoon(m):
    return m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output') if (m and m.node_tree) else None


def _feed(nt, src_socket, dst_socket):
    """dst takes what feeds src: its link's source, or its value"""
    for l in list(dst_socket.links):
        nt.links.remove(l)
    if src_socket.is_linked:
        nt.links.new(src_socket.links[0].from_socket, dst_socket)
    else:
        v = src_socket.default_value
        try:
            dst_socket.default_value = v
        except (TypeError, ValueError):
            dst_socket.default_value = tuple(v)[:len(dst_socket.default_value)]


def _sock(sockets, ident):
    return next(s for s in sockets if s.identifier == ident)


def _node(nt, kind, name, loc):
    n = nt.nodes.get(name)
    if n is None:
        n = nt.nodes.new(kind)
        n.name = n.label = name
        n.location = loc
    return n


def to_pbr(m):
    """add (or refresh) the PBR path in one MToon material and make it EEVEE's output"""
    mo = _mtoon(m)
    if mo is None:
        return False
    nt = m.node_tree
    x, y = mo.location.x + 600, mo.location.y - 900
    base = _node(nt, 'ShaderNodeMix', PBR + 'base', (x, y))
    base.data_type, base.blend_type, base.clamp_result = 'RGBA', 'MULTIPLY', False
    base.inputs['Factor'].default_value = 1.0
    emis = _node(nt, 'ShaderNodeMix', PBR + 'emission', (x, y - 260))
    emis.data_type, emis.blend_type = 'RGBA', 'MULTIPLY'
    emis.inputs['Factor'].default_value = 1.0
    alpha = _node(nt, 'ShaderNodeMath', PBR + 'alpha', (x, y - 480))
    alpha.operation = 'MULTIPLY'
    bsdf = _node(nt, 'ShaderNodeBsdfPrincipled', PBR + 'bsdf', (x + 300, y))
    out = _node(nt, 'ShaderNodeOutputMaterial', PBR + 'out', (x + 600, y))
    out.target = 'EEVEE'
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    nt.links.new(_sock(base.outputs, 'Result_Color'), bsdf.inputs['Base Color'])
    nt.links.new(_sock(emis.outputs, 'Result_Color'), bsdf.inputs['Emission Color'])
    refresh_pbr(m)
    cs = nt.nodes.get('Mtoon1Material.CompatibleShader')
    if cs is not None:
        for nm in ('Metallic', 'Roughness', 'IOR', 'Normal'):
            _feed(nt, cs.inputs[nm], bsdf.inputs[nm])
    _feed(nt, mo.inputs['Emissive Strength'], bsdf.inputs['Emission Strength'])
    am = mo.inputs.get('Alpha Mode')
    if am is not None and not am.is_linked and int(round(am.default_value)) != 0:
        nt.links.new(alpha.outputs['Value'], bsdf.inputs['Alpha'])
    out.is_active_output = True
    mo.mute = True
    return True


def refresh_pbr(m):
    """the PBR path re-reads MToon's colour inputs (after a wardrobe repaint); a no-op without the PBR path"""
    mo = _mtoon(m)
    if mo is None or (PBR + 'base') not in m.node_tree.nodes:
        return
    nt = m.node_tree
    base, emis, alpha = nt.nodes[PBR + 'base'], nt.nodes[PBR + 'emission'], nt.nodes[PBR + 'alpha']
    _feed(nt, mo.inputs['Lit Color'], _sock(base.inputs, 'A_Color'))
    _feed(nt, mo.inputs['Lit Color Texture Color'], _sock(base.inputs, 'B_Color'))
    _feed(nt, mo.inputs['Emissive Factor'], _sock(emis.inputs, 'A_Color'))
    _feed(nt, mo.inputs['Emissive Texture'], _sock(emis.inputs, 'B_Color'))
    _feed(nt, mo.inputs['Lit Color Alpha'], alpha.inputs[0])
    _feed(nt, mo.inputs['Lit Color Texture Alpha'], alpha.inputs[1])


def to_mtoon(m):
    mo = _mtoon(m)
    if mo is None:
        return False
    nt = m.node_tree
    mo.mute = False
    out = nt.nodes.get(PBR + 'out')
    if out is not None:
        out.is_active_output = False
        nt.nodes.remove(out)
    co = nt.nodes.get('Mtoon1Material.CompatibleMaterialOutput')
    if co is not None:
        co.is_active_output = True
    return True


def set_look(h, look='mtoon'):
    """'pbr' or 'mtoon' for every MToon material of a VRMHandle (and its outline modifiers); returns a report"""
    if look not in ('pbr', 'mtoon'):
        raise ValueError(f"set_look look={look!r}: 'pbr' or 'mtoon'")
    seen, n = set(), 0
    for o in h.meshes:
        for s in o.material_slots:
            m = s.material
            if m is None or m.name in seen or m.name.startswith('MToon Outline'):
                continue
            seen.add(m.name)
            n += bool(to_pbr(m) if look == 'pbr' else to_mtoon(m))
        for md in o.modifiers:
            if md.type == 'NODES' and md.node_group and 'Outline' in md.node_group.name:
                md.show_render = md.show_viewport = (look == 'mtoon')
    h.look = look
    return {'look': look, 'materials': n}
