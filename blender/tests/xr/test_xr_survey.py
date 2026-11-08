"""tests/xr/test_xr_survey.py: survey_xr on five films round one built, read only, no render (an API run):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/xr/test_xr_survey.py

survey_xr says what export_xr would do to a film without changing it. Each .blend (another family's test output) is
opened and surveyed; checked: what each film needs is named, and nothing is changed (the .blend's object count and
every object's render visibility are the same after the survey; nothing is saved).
  example      a Poly Haven product shot: image-textured PBR (nothing to bake), two area lights
  crows        two skinned crows: armatures, skinned meshes, an area light
  meadow       the flora brush's meadow: patches whose wind deforms them, millions of triangles (Quest: over)
  fire_teapot  a volume fire (not glTF: named), keyed fire lights (tracks), animated material values (not played)
  robot_walk   my robot body walking: two skinned meshes, sun lights
"""
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
TESTS = os.path.join(WORKTREE, 'blender', 'tests')
OUT = os.path.join(HERE, 'out', 'survey')
os.makedirs(OUT, exist_ok=True)

from eidoblend.xr import export as X  # noqa: E402
from eidoblend.xr import glb as G     # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


FILMS = {
    'example': 'pipeline/out/example.blend', 'crows': 'pipeline/out/crows.blend', 'meadow': 'flora/out/meadow.blend',
    'fire_teapot': 'fx/out/fire_teapot.blend', 'robot_walk': 'characters/out/robot_walk.blend'}
surveys = {}
for name, rel in FILMS.items():
    path = os.path.join(TESTS, rel)
    if not os.path.exists(path):
        check(f'{name}: the built .blend exists (its family test makes it)', False, rel)
        continue
    bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
    sc = bpy.context.scene
    before = (len(bpy.data.objects), sorted((o.name, o.hide_render) for o in bpy.data.objects))
    s = X.survey_xr(sc)
    after = (len(bpy.data.objects), sorted((o.name, o.hide_render) for o in bpy.data.objects))
    check(f'{name}: the survey changes nothing (objects and their visibility)', before == after,
          f'{before[0]} objects')
    surveys[name] = s
    grade = G.budget({'triangles': s['triangles_now'], 'draws': 0, 'texture_mb_gpu': 0})['triangles']
    print(f"[survey] {name}: {json.dumps({k: s[k] for k in ('objects', 'unsupported', 'materials', 'motion', 'lights')}, default=str)[:900]}"
          f" triangles {s['triangles_now']} ({grade})", flush=True)

if 'example' in surveys:
    s = surveys['example']
    check('example: image-textured PBR, nothing to bake; two area lights; a world', not s['materials']['to_bake']
          and [k for _, k in s['lights']].count('AREA') == 2 and s['world'], (s['materials'], s['lights']))
if 'crows' in surveys:
    s = surveys['crows']
    check('crows: two armatures with skinned meshes, nothing else to convert', s['objects'].get('ARMATURE') == 2
          and len(s['motion']['skinned']) == 2 and not s['motion']['moving_instances'] and not s['motion']['deforming'],
          s['motion'])
if 'meadow' in surveys:
    s = surveys['meadow']
    grade = G.budget({'triangles': s['triangles_now'], 'draws': 0, 'texture_mb_gpu': 0})['triangles']
    check('meadow: the wind-deformed patches are named, and its triangles grade over the Quest budget',
          len(s['motion']['deforming']) >= 1 and grade == 'over', (s['motion']['deforming'][:3], s['triangles_now']))
if 'fire_teapot' in surveys:
    s = surveys['fire_teapot']
    kinds = {k for k, _, _ in s['animated']}
    check('fire_teapot: the volume fire is named as not glTF; its keyed lights and animated material values found',
          any('volume' in why for _, why in s['unsupported']) and 'light' in kinds and 'material' in kinds,
          (s['unsupported'], sorted(kinds)))
if 'robot_walk' in surveys:
    s = surveys['robot_walk']
    check('robot_walk: my body: two skinned meshes on one armature, sun lights, no camera of its own',
          s['objects'].get('ARMATURE') == 1 and len(s['motion']['skinned']) == 2
          and {k for _, k in s['lights']} == {'SUN'} and 'CAMERA' not in s['objects'], (s['objects'], s['lights']))
with open(os.path.join(OUT, 'surveys.json'), 'w') as f:
    json.dump(surveys, f, indent=1, default=str)
n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
