# build_pages.py — the two drifting constitution pages for DAISY verse 3 (pages.glb).
# US Letter 215.9 x 279.4 mm, 40 x 52 quads, real paper curl made from ISOMETRIC bends (paper is
# developable: every bend below preserves arc length, so the print never looks stretched):
#   page_2023: a crisp bow along the long axis + a lifted top-right corner (flap bend about a diagonal)
#   page_2026: a softer, wider bow + a gently lifted bottom-left corner + a faint transverse breath
# Text side faces glTF +Z (Blender -Y). UVs match THREE.PlaneGeometry in three.js: uv (0,0) at the
# bottom-left corner seen from the text side, uv().x across the width, uv().y = 1 at the TOP edge.
# (Blender stores v = 1 - that, because the glTF exporter writes t = 1 - v.)
#
#   blender --background --factory-startup --python build_pages.py -- <out_dir>
import bpy, bmesh, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else '.')
TEX = os.path.join(OUT, 'tex', 'pages')
W, H = 0.2159, 0.2794
NX, NY = 40, 52
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)

def roll(q, p0, g, span, theta_tip, pw=1.5):
    """Isometric corner roll: past the generator line (p0, g) the sheet rolls up (+z) with curvature that
    grows toward the corner, kappa(s) = a * s**pw, reaching a total turn theta_tip at s = span (the tip).
    Arc length is preserved exactly (the profile is integrated), so the print never stretches."""
    n = Vector((-g.y, g.x))                                  # in-plane normal of the line, toward the corner
    d = (Vector((q[0], q[1])) - p0).dot(n)
    if d <= 0: return q
    a = theta_tip * (pw + 1) / span ** (pw + 1)
    steps = 96; ds = d / steps; dn = dz = 0.0
    for k in range(steps):
        sm = (k + 0.5) * ds
        th = a * sm ** (pw + 1) / (pw + 1)
        dn += math.cos(th) * ds; dz += math.sin(th) * ds
    xy = Vector((q[0], q[1])) - n * d + n * dn
    return (xy.x, xy.y, q[2] + dz)

def bow(q, R):
    """Isometric bow about an axis parallel to the page width (x) on the text side: both short edges lift."""
    x, y, z = q
    phi = y / R; rho = R - z
    return (x, rho * math.sin(phi), R - rho * math.cos(phi))

def page(name, bows, flaps, breath=0.0, breath_phase=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    verts = []
    for j in range(NY + 1):
        row = []
        for i in range(NX + 1):
            u, t = i / NX, j / NY                              # t = 0 bottom .. 1 top (page space)
            q = ((u - 0.5) * W, (t - 0.5) * H, 0.0)
            for (p0, g, span, th) in flaps: q = roll(q, p0, g, span, th)
            q = bow(q, bows)
            if breath:
                env = math.sin(math.pi * t) ** 2
                q = (q[0], q[1], q[2] + breath * env * math.sin(2 * math.pi * (u * 1.1) + breath_phase))
            # page space (x right, y up, z out of the text side) -> Blender (X, Z up, text faces -Y)
            v = bm.verts.new((q[0], -q[2], q[1]))
            row.append((v, u, t))
        verts.append(row)
    uvl = bm.loops.layers.uv.new('UVMap')
    for j in range(NY):
        for i in range(NX):
            quad = [verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]]
            f = bm.faces.new([q[0] for q in quad])
            for loop, (_, u, t) in zip(f.loops, quad):
                loop[uvl].uv = (u, 1.0 - t)                  # Blender v = 1 - t  ->  three uv().y = t
    bm.normal_update()
    # face winding: make the text side (-Y in Blender) the FRONT face
    bm.faces.ensure_lookup_table()
    if bm.faces[len(bm.faces) // 2].normal.y > 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    return ob

def material(name, color_file):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    def img(fn, noncolor):
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(os.path.join(TEX, fn))
        if noncolor: n.image.colorspace_settings.name = 'Non-Color'
        return n
    c = img(color_file, False); nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
    orm = img('paper_orm.jpg', True)
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(orm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
    nm = img('paper_normal.png', True)
    nmap = nt.nodes.new('ShaderNodeNormalMap'); nmap.inputs['Strength'].default_value = 1.0
    nt.links.new(nm.outputs['Color'], nmap.inputs['Color']); nt.links.new(nmap.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = 0.35
    m.use_backface_culling = False
    return m

# page_2023: crisp. Bow R=0.60 m; the top-right corner rolls up softly: generator line 70 mm from the tip
# (measured along the diagonal), 36 deg of total turn at the tip.
span = 0.070
tip = Vector((W / 2, H / 2)); nrm = Vector((1, 1)).normalized()
p0 = tip - nrm * span; g = Vector((1, -1)).normalized()
p23 = page('page_2023', 0.60, [(p0, g, span, math.radians(36))])
p23.data.materials.append(material('paper_2023', 'page_2023_color.jpg'))
# page_2026: softer. Bow R=0.90 m; the bottom-left corner lifts gently: 95 mm span, 22 deg; a faint breath.
span = 0.095
tip = Vector((-W / 2, -H / 2)); nrm = Vector((-1, -1)).normalized()
p0 = tip - nrm * span; g = Vector((-1, 1)).normalized()
p26 = page('page_2026', 0.90, [(p0, g, span, math.radians(22))], breath=0.0016, breath_phase=0.7)
p26.data.materials.append(material('paper_2026', 'page_2026_color.jpg'))

for ob in (p23, p26):
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = [min(p[i] for p in bb) for i in range(3)]; hi = [max(p[i] for p in bb) for i in range(3)]
    print('PAGE', ob.name, 'tris', 2 * NX * NY, 'bbox_blender', [round(x, 4) for x in lo], [round(x, 4) for x in hi])
p26.location.x = 0.0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'pages.blend'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'pages.glb'), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_normals=True, export_texcoords=True,
                          export_materials='EXPORT', export_image_format='AUTO')
print('EXPORTED', os.path.join(OUT, 'pages.glb'))
