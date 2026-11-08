"""ocean/_land_nodes.py: the land's material and the dune grass (land.js's TSL), in Blender nodes.

    land_material(name)                        sand / wet sand / withered grass blended by height, the macro tone,
                                               the grass noise and her rise (Poly Haven CC0 2k from the shared library)
    dune_grass_material(name, gradient)        the blade gradient x a per-tuft shade, rough 0.78, two-sided
    dune_grass_object(name, tuft, blades, mat, parent, collection)
                                               the 2600 tufts realized into one mesh (each vertex knows its tuft's
                                               phase, yaw and scale), the sway as Geometry Nodes from a keyed clock
"""

from __future__ import annotations

import numpy as np

from ._nodes import NB, E, new_tree, clear_material


def _pcg(x):
    from .sea import pcg_hash
    return pcg_hash(np.asarray(x, np.float32))


def land_material(name='ocean_land'):
    import bpy
    from eidoblend.terrain import _pbr
    cs, s3, wg = _pbr.load_set('coast_sand_01'), _pbr.load_set('sand_03'), _pbr.load_set('withered_grass')
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, out = clear_material(mat)
    nb = NB(nt, x0=-2200, y0=900, rows=34)
    tc = nb.node('ShaderNodeTexCoord')
    px, py_b, h = nb.separate(tc.outputs['Object'])              # design frame, Blender axes (the land object is unturned)
    pz = -nb.s(py_b)                                            # three's z

    def tex(img, u, v, interpolation='Linear'):
        return nb.image(img, u, v, interpolation=interpolation, extension='REPEAT')
    uS = (px * (1 / 3.1), pz * (1 / 3.1))
    uS2 = ((px * 0.8 - pz * 0.6) * (1 / 8.3), (px * 0.6 + pz * 0.8) * (1 / 8.3))
    uW = (px * (1 / 2.4), pz * (1 / 2.4))
    uG = (px * (1 / 2.2), pz * (1 / 2.2))
    macro = nb.sin(px * 0.37 + nb.sin(pz * 0.23) * 1.7) * nb.cos(pz * 0.31 - px * 0.11) * 0.5 + 0.5
    wet = 1.0 - nb.smoothstep(0.1, 0.42, h)
    grassN = nb.sin(px * 0.61 + nb.cos(pz * 0.43) * 2.0) * nb.sin(pz * 0.53 - px * 0.21) * 0.5 + 0.5
    rd = nb.sqrt((px - 0.2) * (px - 0.2) + (pz - 0.45) * (pz - 0.45)) * (1 / 3.4)
    rise = nb.smoothstep(1.2, 0.35, rd)                         # around her
    grass = nb.clamp(nb.smoothstep(0.95, 1.35, h) * nb.smoothstep(0.25, 0.6, grassN)
                     + rise * nb.smoothstep(0.9, 1.15, h) * 0.85, 0.0, 1.0)
    sD1, sD2 = tex(cs['color'], *uS)[:3], tex(cs['color'], *uS2)[:3]
    mk = macro * 0.25 + 0.85
    dryC = tuple(nb.mix(a, b, 0.35) * mk for a, b in zip(sD1, sD2))
    wetC = tuple(c * 0.42 for c in tex(s3['color'], *uW)[:3])
    grassC = tuple(c * 0.92 for c in tex(wg['color'], *uG)[:3])
    color = tuple(nb.mix(nb.mix(dryC[i], wetC[i], wet), grassC[i], grass) for i in range(3))
    aS, aW, aG = tex(cs['arm'], *uS), tex(s3['arm'], *uW), tex(wg['arm'], *uG)
    rough = nb.mix(nb.mix(aS[1], aW[1] * 0.3 + 0.42, wet), aG[1], grass)
    ao = nb.mix(nb.mix(aS[0], 1.0, wet), aG[0], grass)
    # three's aoNode darkens the ambient light only; Principled has no AO input: the cavity goes into the albedo at 0.6
    aok = 1.0 + (ao - 1.0) * 0.6
    color = tuple(c * aok for c in color)
    nS, nW, nG = tex(cs['normal'], *uS)[:3], tex(s3['normal'], *uW)[:3], tex(wg['normal'], *uG)[:3]
    ncol = tuple(nb.mix(nb.mix(nS[i], nW[i], wet), nG[i], grass) for i in range(3))
    bsdf = nb.node('ShaderNodeBsdfPrincipled')
    bsdf.hide = False
    nb.link(color, bsdf.inputs['Base Color'])
    nb.link(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = 0.0
    nm = nb.node('ShaderNodeNormalMap', space='TANGENT', uv_map='uv')
    nm.hide = False
    nm.inputs['Strength'].default_value = 1.0
    nb.link(ncol, nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def dune_grass_material(name, gradient):
    """gradient: (256, 3) uint8 sRGB, row 0 = the blade's base."""
    import bpy
    from .util import image_from_array
    g = np.zeros((256, 4, 4), np.uint8)
    g[:, :, :3] = gradient[:, None, :]
    g[:, :, 3] = 255
    img = image_from_array('ocean_dunegrass_gradient', g, colorspace='sRGB', float_buffer=False)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, out = clear_material(mat)
    nb = NB(nt, x0=-1200, y0=300)
    v = nb.attr('v', 'GEOMETRY')
    shade = nb.attr('shade', 'GEOMETRY')
    r, gg, b, _a = nb.image(img, 0.5, v, interpolation='Linear', extension='EXTEND')
    bsdf = nb.node('ShaderNodeBsdfPrincipled')
    bsdf.hide = False
    nb.link((r * shade, gg * shade, b * shade), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.78
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    mat.use_backface_culling = False
    return mat


def _sway_group():
    """land.js's grass positionNode: sway = (sin(t 1.1 + ph) 0.6 + sin(t 2.3 + 1.7 ph) 0.25) wind, offset
    (sway k, 0, sway k 0.6) with k = 0.16 y^2.
    WebGPU = 0 (default): y is the blade's own height and the offset turns with the tuft (yaw, scale): the base stays
    planted, the tips sway, which is what the formula is written for.
    WebGPU = 1: the film's exact arithmetic. three applies an InstancedMesh's matrix to positionLocal BEFORE the
    material's positionNode (NodeMaterial.setupPosition), so the JS read the design-frame height (ground + blade) and
    offset along design x / z: on the 0.7 - 2 m dunes the whole tuft, base included, slid by up to ~0.2 m."""
    import bpy
    name = 'ocean_dunegrass_sway'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'GeometryNodeTree', inputs=[('Geometry', 'NodeSocketGeometry'),
                            ('Time', 'NodeSocketFloat', 0.0), ('Wind', 'NodeSocketFloat', 1.0),
                            ('WebGPU', 'NodeSocketFloat', 0.0)],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    t, wind, wg = E(nb, gi.outputs['Time']), E(nb, gi.outputs['Wind']), E(nb, gi.outputs['WebGPU'])
    qy, ph, yaw, s = nb.attr('qy'), nb.attr('ph'), nb.attr('yaw'), nb.attr('s')
    sway = (nb.sin(t * 1.1 + ph) * 0.6 + nb.sin(t * 2.3 + ph * 1.7) * 0.25) * wind
    k = qy * qy * 0.16
    ox, oz = sway * k * s, sway * k * 0.6 * s                     # tuft-local (three), scaled
    cy, sy = nb.cos(yaw), nb.sin(yaw)
    pos = nb.node('GeometryNodeInputPosition')
    _px, _py, pzb = nb.separate(pos.outputs[0])
    kw = pzb * pzb * 0.16                                        # the design-frame height (WebGPU = 1)
    wx = nb.mix(ox * cy + oz * sy, sway * kw, wg)                # three rotation about +Y by yaw
    wz = nb.mix(oz * cy - ox * sy, sway * kw * 0.6, wg)
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    tree.links.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
    nb.link((wx, -nb.s(wz), 0.0), setp.inputs['Offset'])
    tree.links.new(setp.outputs['Geometry'], go.inputs['Geometry'])
    return tree


def dune_grass_object(name, tuft, blades, mat, parent=None, collection=None):
    """The tufts realized: blades [x, y, z, yaw, s] (three design), tuft (P (n, 3), I (m, 3), UV (n, 2))."""
    import bpy
    from . import _bl
    P, I, UV = tuft
    n, nv = len(blades), len(P)
    B = np.asarray(blades, np.float64)
    i = np.arange(n)
    sy_ = B[:, 4] * (0.85 + 0.3 * ((i * 7919) % 13) / 13)       # the per-tuft vertical scale (land.js)
    cy, sy = np.cos(B[:, 3]), np.sin(B[:, 3])
    lx, ly, lz = P[None, :, 0] * B[:, 4, None], P[None, :, 1] * sy_[:, None], P[None, :, 2] * B[:, 4, None]
    wx = lx * cy[:, None] + lz * sy[:, None] + B[:, 0, None]
    wz = -lx * sy[:, None] + lz * cy[:, None] + B[:, 2, None]
    wy = ly + B[:, 1, None]
    pos = np.stack([wx, -wz, wy], -1).reshape(-1, 3)
    tris = (I[None, :, :] + (i * nv)[:, None, None]).reshape(-1, 3)
    me = _bl.mesh_from_arrays(name, pos, tris)
    _bl.add_point_attr(me, 'qy', np.tile(P[:, 1], n))
    _bl.add_point_attr(me, 'v', np.tile(UV[:, 1], n))
    _bl.add_point_attr(me, 'ph', np.repeat(_pcg(i.astype(np.float32) + np.float32(3.0)) * 6.283, nv))
    _bl.add_point_attr(me, 'shade', np.repeat(_pcg(i.astype(np.float32) + np.float32(11.0)) * 0.35 + 0.75, nv))
    _bl.add_point_attr(me, 'yaw', np.repeat(B[:, 3], nv))
    _bl.add_point_attr(me, 's', np.repeat(B[:, 4], nv))
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if parent is not None:
        ob.parent = parent
    ob['t'] = 0.0
    ob['wind'] = 1.0
    mod = ob.modifiers.new('sway', 'NODES')
    mod.node_group = _sway_group()
    _bl.drive_modifier_input(ob, mod, 'Time', ob, 't')
    _bl.drive_modifier_input(ob, mod, 'Wind', ob, 'wind')
    return ob
