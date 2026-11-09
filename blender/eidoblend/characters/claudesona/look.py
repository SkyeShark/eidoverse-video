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
    Metallic, Roughness, IOR    the glTF-compatible shader's own (the VRM's pbrMetallicRoughness)
    Normal       the glTF-compatible shader's (the VRM's normal map), or the bump this package's surfaces put on MToon's
                 Normal (the TuTa's weave, seams and piping: a node named 'cs.*')
    Emission     MToon's Emissive Factor x Emissive Texture at Emissive Strength, and the DRIVER on Emissive Strength
                 when it has one (the TuTa's badges glow by a driver: snaps, flight flicker, neon)
    Alpha        Lit Color Alpha x the texture's alpha, for materials whose MToon alpha mode is not opaque
A value MToon takes from a driver is driven the same way on the Principled side (_feed copies the driver), so every
keyed switch of the wardrobe and the TuTa animates in both looks.
"""

import bpy

PBR = 'pbr.'


def _mtoon(m):
    return m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output') if (m and m.node_tree) else None


def _drivers_of(nt, sock):
    """the driver fcurves on a socket's default_value ([] when it has none)"""
    ad = nt.animation_data
    if ad is None:
        return []
    try:
        path = sock.path_from_id('default_value')
    except (ValueError, TypeError):
        return []
    return [fc for fc in ad.drivers if fc.data_path == path]


def _copy_driver(nt, src_socket, dst_socket):
    """dst's default_value driven as src's is (any old driver on dst removed first); returns how many were copied"""
    for fc in _drivers_of(nt, dst_socket):
        nt.animation_data.drivers.remove(fc)
    n = 0
    for fc in _drivers_of(nt, src_socket):
        multi = hasattr(dst_socket.default_value, '__len__')
        nf = dst_socket.driver_add('default_value', fc.array_index) if multi else dst_socket.driver_add('default_value')
        s, d = fc.driver, nf.driver
        d.type = s.type
        for v in list(d.variables):
            d.variables.remove(v)
        for sv in s.variables:
            v = d.variables.new()
            v.name, v.type = sv.name, sv.type
            for st, t in zip(sv.targets, v.targets):
                if sv.type == 'SINGLE_PROP':
                    t.id_type = st.id_type
                t.id = st.id
                t.data_path = st.data_path
                t.bone_target, t.transform_type, t.transform_space = st.bone_target, st.transform_type, st.transform_space
                t.rotation_mode = st.rotation_mode
        if s.type == 'SCRIPTED':
            d.expression = s.expression
        d.is_valid = True
        n += 1
    return n


def _feed(nt, src_socket, dst_socket):
    """dst takes what feeds src: its link's source, or its value and the driver on it"""
    for l in list(dst_socket.links):
        nt.links.remove(l)
    if src_socket.is_linked:
        for fc in _drivers_of(nt, dst_socket):
            nt.animation_data.drivers.remove(fc)
        nt.links.new(src_socket.links[0].from_socket, dst_socket)
    else:
        v = src_socket.default_value
        try:
            dst_socket.default_value = v
        except (TypeError, ValueError):
            dst_socket.default_value = tuple(v)[:len(dst_socket.default_value)]
        _copy_driver(nt, src_socket, dst_socket)


def _normal_source(nt, mo):
    """what the Principled's Normal takes: a 'cs.*' bump on MToon's Normal (this package's surfaces), else the
    glTF-compatible shader's normal (the VRM's normal map)"""
    nrm = mo.inputs.get('Normal')
    if nrm is not None and nrm.is_linked and nrm.links[0].from_node.name.startswith('cs.'):
        return nrm
    cs = nt.nodes.get('Mtoon1Material.CompatibleShader')
    return cs.inputs['Normal'] if cs is not None else None


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
    cs = nt.nodes.get('Mtoon1Material.CompatibleShader')
    if cs is not None:
        for nm in ('Metallic', 'Roughness', 'IOR'):
            _feed(nt, cs.inputs[nm], bsdf.inputs[nm])
    am = mo.inputs.get('Alpha Mode')
    if am is not None and not am.is_linked and int(round(am.default_value)) != 0:
        nt.links.new(alpha.outputs['Value'], bsdf.inputs['Alpha'])
    refresh_pbr(m)
    out.is_active_output = True
    mo.mute = True
    return True


def refresh_pbr(m):
    """the PBR path re-reads what MToon takes (after a wardrobe repaint or a TuTa surface): colours, emission and its
    strength (with its driver), the bump normal; a no-op without the PBR path"""
    mo = _mtoon(m)
    if mo is None or (PBR + 'base') not in m.node_tree.nodes:
        return
    nt = m.node_tree
    base, emis, alpha = nt.nodes[PBR + 'base'], nt.nodes[PBR + 'emission'], nt.nodes[PBR + 'alpha']
    bsdf = nt.nodes[PBR + 'bsdf']
    _feed(nt, mo.inputs['Lit Color'], _sock(base.inputs, 'A_Color'))
    _feed(nt, mo.inputs['Lit Color Texture Color'], _sock(base.inputs, 'B_Color'))
    _feed(nt, mo.inputs['Emissive Factor'], _sock(emis.inputs, 'A_Color'))
    _feed(nt, mo.inputs['Emissive Texture'], _sock(emis.inputs, 'B_Color'))
    _feed(nt, mo.inputs['Emissive Strength'], bsdf.inputs['Emission Strength'])
    _feed(nt, mo.inputs['Lit Color Alpha'], alpha.inputs[0])
    _feed(nt, mo.inputs['Lit Color Texture Alpha'], alpha.inputs[1])
    src = _normal_source(nt, mo)
    if src is not None:
        _feed(nt, src, bsdf.inputs['Normal'])


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
