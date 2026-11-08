"""hand_edit.py <file.blend> <object> <dx>: what a person does in Blender's window (open, move one object, save), done
headless, so run_tests.py can check that a hand-edited build is rendered as edited and never rebuilt over unasked.

    bash run_blender.sh blender/tests/pipeline/hand_edit.py <file.blend> stool 0.6
"""
import sys

import bpy

blend, name, dx = sys.argv[sys.argv.index('--') + 1:][:3]
bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
ob = bpy.data.objects[name]
ob.location.x += float(dx)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_mainfile()
print(f'[hand_edit] moved {name} by {dx} m in x and saved {blend}', flush=True)
