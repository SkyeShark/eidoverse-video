import bpy, os, sys
out = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
o = bpy.data.objects['human']
for m in list(bpy.data.meshes):
    if m is not o.data and m.users == 0: bpy.data.meshes.remove(m)
o.data.name = 'human'
bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'human.blend'))
bpy.ops.export_scene.gltf(filepath=os.path.join(out, 'human.glb'), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_normals=True, export_texcoords=True, export_materials='EXPORT')
print('REEXPORTED', o.data.name)
