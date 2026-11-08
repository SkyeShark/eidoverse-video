"""The robot_body tests' stage: the characters family's probe stage (tests/characters/_stage.py: probe EEVEE settings,
the claude_robot example's studio light, floors, cameras), loaded by path, with this folder's own out/ for outputs, plus
a few helpers these tests share (deno for the JS originals, a clip's raw normalized pose)."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
_spec = importlib.util.spec_from_file_location('characters_stage', os.path.join(REPO, 'blender', 'tests', 'characters', '_stage.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
C.OUT = OUT

MAIN = os.path.join(os.path.dirname(REPO), 'eidoverse-video-prealpha-0.01')
THREE_JS = next((p for p in (os.path.join(REPO, 'node_modules', 'three', 'build', 'three.module.js'),
                             os.path.join(MAIN, 'node_modules', 'three', 'build', 'three.module.js')) if os.path.exists(p)), None)


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def deno():
    d = shutil.which('deno')
    if d:
        return d
    p = os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe\deno.exe')
    return p if os.path.exists(p) else None


def run_deno(mjs, *args, timeout=900):
    exe = deno()
    if exe is None:
        raise RuntimeError('deno not found')
    r = subprocess.run([exe, 'run', '--no-config', '--no-lock', '-A', mjs, *args], capture_output=True, text=True,
                       timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f'deno {os.path.basename(mjs)} failed ({r.returncode}):\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r.stdout


def write_json(name, obj):
    p = os.path.join(OUT, name)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, default=str)
    return p


def solids_bvh(objs):
    """one BVH over objects' evaluated meshes in world space (walls, furniture: what a camera must stay in front of)"""
    import bpy
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for ob in objs:
        if ob.type != 'MESH':
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        b0 = len(verts)
        verts.extend(ev.matrix_world @ v.co for v in me.vertices)
        polys.extend([b0 + i for i in p.vertices] for p in me.polygons)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


def clear_view(bvh, target, want, margin=0.25):
    """a camera place on the line from `target` toward `want` with nothing between them: where a wall or a solid
    stands on that line, the camera comes in to `margin` in front of it (so a probe never looks at a wall's back)"""
    from mathutils import Vector
    t, w = Vector(target), Vector(want)
    d = w - t
    L = d.length
    if L < 1e-6:
        return w
    d /= L
    hit = bvh.ray_cast(t, d, L + margin)
    if hit[0] is None:
        return w
    return t + d * max(0.3, hit[3] - margin)


def best_view(bvh, target, wants, margin=0.25):
    """of several wanted camera places, the one that keeps the most of its distance in front of the solids (clear_view
    applied to each; ties go to the earlier)"""
    from mathutils import Vector
    best = None
    for w in wants:
        c = clear_view(bvh, target, w, margin)
        keep = (c - Vector(target)).length / max(1e-6, (Vector(w) - Vector(target)).length)
        if best is None or keep > best[0] + 1e-3:
            best = (keep, c)
    return best[1]


def raw_pose(h, clip, tc):
    """the clip's NORMALIZED pose at clip time tc before any DOF pass: ({name: Quaternion three}, hips position three)"""
    from mathutils import Quaternion
    from eidoblend.characters._math import q_to_three, v_to_three
    rot, loc = clip.sample(tc)
    N = {}
    for n, b in h.humanoid.items():
        q = rot.get(b)
        N[n] = q_to_three(h.normalized_from_basis(b, q)) if q is not None else Quaternion()
    off = h.hips_location_offset(loc.get(h.humanoid['hips'], (0.0, 0.0, 0.0)))
    return N, v_to_three(h.rest_head[h.humanoid['hips']] + off)
