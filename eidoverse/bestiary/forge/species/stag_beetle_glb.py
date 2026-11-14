"""B10 (static) the beetle's glb (the Bestiary lead's round 10-28; the rig is the next round): every placed piece of
stag_beetle_parts at x10 (metres; extras.bestiary.life_scale 0.1), its low with the UVs of stag_beetle_uv (mirrored copies
through the tangent sign: the tangents are each copy's own), the texture pages of stag_beetle_skin, one primitive per
(page, material kind). Materials in STANDARD slots so a plain viewer shows a believable chitin and the runtime reads
every channel itself (the octopus's convention):
  cuticle    pbrMetallicRoughness (base colour; ORM as metallicRoughness with metallicFactor 0: its B is the coat's
             roughness, data), the normal map, occlusion = ORM R; KHR_materials_clearcoat 1 (roughness factor the zone's
             mean for a plain viewer: the runtime reads ORM B per texel); KHR_materials_ior 1.56; KHR_materials_specular
             0.2 (the base's own small lobe: stag_beetle_skin's layer model); the MASKS pack in KHR_materials_volume's
             thickness texture (factor 0); the DISPLAY pack as the emissive texture (factor 0); the IRID pack as
             KHR_materials_iridescence's texture and thickness texture at factor 0 (the iridescent option turns it on)
  eye        the cuticle's slots, extras bestiary 'compound_eye' (the runtime's dark glossy eye, facets as a micro-normal)
  membrane   the sleeves: extras bestiary 'membrane' (soft, translucent at the runtime)
"""
import json

import numpy as np

from .. import bake as BK
from .. import gltf as GL
from . import stag_beetle_parts as BP

KINDS = ('cuticle', 'eye', 'membrane')


def kind_of(master):
    if master['kind'] == 'sleeve':
        return 'membrane'
    if master['region'] == 'eye':
        return 'eye'
    return 'cuticle'


def assemble(masters, uvs, scale=0.01):
    """every instance's low: V (metres at x10), N, TAN, UV, and per triangle (page, kind, instance id); plus the instance
    table (name, master, vertex range, triangle range, flip)"""
    Vs, Ns, Ts, UVs_, Fs, pg, kd, iid = [], [], [], [], [], [], [], []
    table = []
    off = 0
    toff = 0
    for m in masters:
        U = uvs[m['name']]
        k = KINDS.index(kind_of(m))
        for it in m['instances']:
            V = BP.place(U['V'], it) * scale
            N = U['N'] @ it['M'].T
            N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
            F = U['F'][:, ::-1].copy() if it['flip'] else U['F'].copy()
            N2, TAN = BK.low_frames(V, F, U['UV'], N)
            Vs.append(V)
            Ns.append(N2)
            Ts.append(TAN)
            UVs_.append(U['UV'])
            Fs.append(F + off)
            pg.append(U['page'])
            kd.append(np.full(len(F), k))
            iid.append(np.full(len(F), len(table)))
            table.append(dict(name=it['name'], master=m['name'], region=m['region'], side=it['side'], flip=it['flip'],
                              verts=[off, off + len(V)], tris=[toff, toff + len(F)]))
            off += len(V)
            toff += len(F)
    return dict(V=np.concatenate(Vs), N=np.concatenate(Ns), TAN=np.concatenate(Ts), UV=np.concatenate(UVs_),
                F=np.concatenate(Fs), page=np.concatenate(pg), kind=np.concatenate(kd), inst=np.concatenate(iid),
                table=table)


def write(path, A, pages, extras, coat_rough=0.14, ior=1.56, spec=0.2, film=(250.0, 650.0), film_ior=1.6, log=print):
    """pages: per page dict of uint8 images (albedo, normal, orm, masks, display, irid). Returns the byte size"""
    g = GL.GLB(generator='eidoverse bestiary forge: stag beetle (B5-B8 + static B10)')
    tex = []
    # the octopus's t13 'engine' convention: PNG for the data that must stay exact (normals, the ORM and the packs), JPEG
    # q94 for the colour (headless deno decodes both; WebP needs a browser-side support check: gltf.texture's note)
    for P in pages:
        t = dict(albedo=g.texture(P['albedo'], fmt='jpeg', quality=94),
                 normal=g.texture(P['normal'], fmt='png'), orm=g.texture(P['orm'], fmt='png'),
                 masks=g.texture(P['masks'], fmt='png'), display=g.texture(P['display'], fmt='png'),
                 irid=g.texture(P['irid'], fmt='png'))
        tex.append(t)
    mats = {}
    for pi, t in enumerate(tex):
        for k in KINDS:
            sel = (A['page'] == pi) & (A['kind'] == KINDS.index(k))
            if not sel.any():
                continue
            mi = g.material(f'beetle_{k}_p{pi}', base=t['albedo'], normal=t['normal'], orm=t['orm'],
                            volume_tex=t['masks'], emissive_tex=t['display'], irid_tex=t['irid'],
                            double_sided=(k == 'membrane'), extras=dict(
                                bestiary={'cuticle': 'cuticle', 'eye': 'compound_eye', 'membrane': 'membrane'}[k],
                                recipe='stag_beetle', page=pi,
                                orm_channels='R occlusion, G base roughness, B COAT roughness (metallicFactor 0); '
                                             'both roughness channels carry the bake\'s sub-texel normal spread (B5)',
                                masks_channels='R soft / thin, G setae, B accent, A chestnut pattern zone (0 or 1 only)',
                                display_channels='R part id (REGIONS index / 255), G iridophore mask, B per-cell random '
                                                 '(RGB: B8)',
                                irid_channels='R setae sheen amount (B5: the runtime\'s sheen lobe over the coat), G film '
                                              'thickness (0..1 of the family range), B coat amount (RGB: B8; the film '
                                              'mask is DISPLAY G)',
                                pack_layout='b8_opaque',
                                slots='masks ride KHR_materials_volume thicknessTexture, display the emissiveTexture '
                                      '(factor 0), irid KHR_materials_iridescence (factor 0)'))
            m = g.j['materials'][mi]
            m['pbrMetallicRoughness']['metallicFactor'] = 0.0
            m['pbrMetallicRoughness']['roughnessFactor'] = 1.0
            ext = m.setdefault('extensions', {})
            if k != 'membrane':
                ext['KHR_materials_clearcoat'] = {'clearcoatFactor': 1.0, 'clearcoatRoughnessFactor': float(coat_rough)}
                g.ext_used.add('KHR_materials_clearcoat')
            ext['KHR_materials_ior'] = {'ior': float(ior)}
            ext['KHR_materials_specular'] = {'specularFactor': float(spec)}
            g.ext_used.update({'KHR_materials_ior', 'KHR_materials_specular'})
            ir = ext['KHR_materials_iridescence']
            ir['iridescenceIor'] = float(film_ior)
            ir['iridescenceThicknessMinimum'] = float(film[0])
            ir['iridescenceThicknessMaximum'] = float(film[1])
            mats[(pi, k)] = mi
    prims = []
    for (pi, k), mi in mats.items():
        sel = (A['page'] == pi) & (A['kind'] == KINDS.index(k))
        prims.append((A['F'][sel].astype(np.uint32), mi))
    mesh = g.mesh('stag_beetle', A['V'], A['N'], A['TAN'], A['UV'], prims)
    root = g.node('stag_beetle', root=True, extras=dict(bestiary=extras))
    g.node('stag_beetle_mesh', mesh=mesh, parent=root)
    size = g.save(path, extras=dict(bestiary=extras))
    log(f'[glb] {path}: {len(A["V"]):,} vertices, {len(A["F"]):,} triangles, {len(prims)} primitives, '
        f'{len(g.j["textures"])} textures, {size / 1e6:.1f} MB')
    return size


def verify(path, A):
    """re-import exact: positions, normals, UVs and triangles as written"""
    R = GL.read(path)
    j = R['json']
    acc = R['accessor']
    p0 = j['meshes'][0]['primitives'][0]['attributes']
    V = acc(p0['POSITION'])
    UV = acc(p0['TEXCOORD_0'])
    err_v = float(np.abs(V - A['V'].astype(np.float32)).max())
    err_uv = float(np.abs(UV[:, 1] - (1.0 - A['UV'][:, 1]).astype(np.float32)).max())
    ntri = sum(len(acc(p['indices'])) // 3 for p in j['meshes'][0]['primitives'])
    return dict(max_pos_err=err_v, max_uv_err=err_uv, triangles=ntri, extensions=j.get('extensionsUsed', []),
                materials=[m['name'] for m in j['materials']])
