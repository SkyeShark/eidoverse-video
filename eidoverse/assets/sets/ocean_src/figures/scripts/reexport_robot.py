import bpy, os, sys
out = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
for name in ('robot_metal', 'robot_lens', 'robot_lamp'):
    bpy.data.materials[name].use_backface_culling = True     # closed solids: single-sided in glTF
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'robot.blend'))
bpy.ops.object.select_all(action='DESELECT')
for n in ('robot', 'robot_body', 'robot_lamps'): bpy.data.objects[n].select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(out, 'robot.glb'), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_normals=True, export_texcoords=True,
                          export_materials='EXPORT', export_image_format='AUTO')
print('REEXPORTED robot')
