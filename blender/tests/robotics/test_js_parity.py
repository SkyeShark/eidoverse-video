"""The whole catalog against the WebGPU edition, number for number (no render).

js_parity_dump.mjs (run it first, see its header) loads every catalog model in the WebGPU runtime and records its
roots, joint state, default joints, clips, parts, stats, ports, machine data and the world matrix of every glTF node
(and every split track shoe) at rest and after robot.sample(clip, t) for each clip at t = 1.25 s and 5.5 s. This test
loads the same models with make_robot(textures=False) and compares, converting three's matrices to Blender's axes
(C^-1 W C for nodes, C^-1 M for port frames). It also checks the runtime test's determinism rule (sample(clip, 2),
sample(clip, 8), sample(clip, 2) give identical matrices) and that every part has mapped triangles.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_js_parity.py [-- ids...]
"""

import json
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters.robotics import catalog, make_robot  # noqa: E402

TOL = 3e-5          # metres / matrix elements: the dump rounds to 1e-6 and Blender stores transforms as float32
ONLY = K.argv()
RESULTS_FIL = {}


def shoe_of(robot, key):
    part, node = key[len('shoe:'):].rsplit('@n', 1)
    parent = robot.node_obj.get(int(node))
    for o in robot.extra_objects:
        if o.get('track_shoe') and o.get('part_id') == part and o.parent == parent:
            return o
    return None


def obj_of(robot, key):
    if key.startswith('shoe:'):
        return shoe_of(robot, key)
    return robot.node_obj.get(int(key[1:]))


def compare_worlds(robot, worlds):
    bpy.context.view_layer.update()
    gi = robot.group.matrix_world.inverted()
    worst, missing, where = 0.0, 0, None
    for key, e in worlds.items():
        o = obj_of(robot, key)
        if o is None:
            missing += 1
            continue
        d = K.mdiff(gi @ o.matrix_world, K.world_from_three(e))
        if d > worst:
            worst, where = d, key
    return worst, missing, where


def snapshot(robot):
    bpy.context.view_layer.update()
    return [o.matrix_world.copy() for o in robot.motion_objects()]


def main():
    cat = catalog()
    ids = [i for i in cat['models'] if not ONLY or i in ONLY]
    summary = {}
    for rid in ids:
        js = json.load(open(os.path.join(K.DUMP, K.safe(rid) + '.json'), encoding='utf-8'))
        K.clean_scene()
        try:
            r = make_robot(rid, textures=False)
        except Exception:  # noqa: BLE001
            K.check(f'{rid}: loads', False, traceback.format_exc().splitlines()[-1])
            continue
        rec = {}
        try:
            K.check(f'{rid}: clips {r.clips}', r.clips == js['clips'], f"js {js['clips']}")
            # filament.js installFilament adds the PTFE tubes and the live strand at load (the fabrication port's)
            glb_parts = set(cat['models'][rid]['parts'])
            fil = sorted(set(js['parts']) - set(r.parts()) - glb_parts) if not r.filament else []
            K.check(f'{rid}: parts', sorted(r.parts()) == sorted(set(js['parts']) - set(fil)),
                    f'{len(r.parts())} vs {len(js["parts"])}' + (f'; filament.js adds {fil}' if fil else ''))
            st = r.stats()
            if fil:
                RESULTS_FIL[rid] = fil
                K.check(f'{rid}: stats parts (+ {len(fil)} filament.js parts)', st['parts'] + len(fil) == js['stats']['parts'])
            else:
                ok = all(st[k] == js['stats'][k] for k in ('triangles', 'parts')) and st['primitives'] == js['stats']['meshes']
                K.check(f'{rid}: stats triangles / meshes (glTF primitives) / parts', ok,
                        f"{st['triangles']}/{st['primitives']}/{st['parts']} vs {js['stats']['triangles']}/"
                        f"{js['stats']['meshes']}/{js['stats']['parts']}")
            # a node's glTF primitives concatenate in order in Blender's one mesh (the triangle ownership relies on it)
            bad = []
            for o in r.objects:
                node = o.get('gltf_node')
                if o.type != 'MESH' or node is None or 'mesh' not in r.gltf['nodes'][node]:
                    continue
                prims = r.gltf['meshes'][r.gltf['nodes'][node]['mesh']]['primitives']
                if len(prims) < 2:
                    continue
                counts = [r.gltf['accessors'][p['indices']]['count'] // 3 for p in prims]
                mi = [p.material_index for p in o.data.polygons]
                runs, k = [], 0
                for c in counts:
                    runs.append(set(mi[k:k + c]))
                    k += c
                mats = [p.get('material') for p in prims]
                order_ok = all(next(iter(runs[a])) != next(iter(runs[b])) for a in range(len(runs)) for b in range(a)
                               if len(runs[a]) == 1 and len(runs[b]) == 1 and mats[a] != mats[b])
                if k != len(mi) or any(len(s) != 1 for s in runs) or not order_ok:
                    bad.append(o.name)
            K.check(f'{rid}: multi-primitive meshes keep their primitives in order', not bad, f'{bad[:3]}')
            want_roots = {n: k for n, k in js['roots'].items()}
            got_roots = {n: f"n{o['gltf_node']}" for n, o in r.roots.items()}
            K.check(f'{rid}: roots (names and nodes)', got_roots == want_roots, f'{len(got_roots)} vs {len(want_roots)}')
            K.check(f'{rid}: state after load', all(abs(r.state.get(n, 1e9) - v) < 1e-9 for n, v in js['state'].items())
                    and set(r.state) == set(js['state']))
            if js.get('defaultJoints'):
                K.check(f'{rid}: default joints', r.default_joints == js['defaultJoints'] or
                        all(abs(r.default_joints[n] - v) < 1e-12 for n, v in js['defaultJoints'].items()))
            pw, pmis = 0.0, []
            for n, p in js['ports'].items():
                q = r.ports.get(n)
                if q is None or q['interface'] != p['interface'] or f"n{q['owner']['gltf_node']}" != p['owner']:
                    pmis.append(n)
                    continue
                pw = max(pw, K.mdiff(q['matrix'], K.frame_from_three(p['matrix'])))
            extra = sorted(set(r.ports) - set(js['ports']))
            K.check(f'{rid}: ports ({len(js["ports"])}) names, interfaces, owners, frames', not pmis and not extra
                    and pw < TOL, f'worst {pw:.2e} missing {pmis[:3]} extra {extra[:3]}')
            w, miss, where = compare_worlds(r, js['rest'])
            K.check(f'{rid}: rest world matrices of {len(js["rest"])} nodes', w < TOL and miss == 0,
                    f'worst {w:.2e} at {where}, {miss} unmatched')
            if js.get('machine'):
                m = r.machine
                ok = (abs(m['bed_top'] - js['machine']['bedTop']) < 1e-9 and m['tool'] == js['machine']['tool']
                      and all(abs(a - b) < 1e-9 for x, y in zip(m['axis_limits'], js['machine']['axisLimits'])
                              for a, b in zip(x, y)))
                K.check(f'{rid}: machine (bed top, tool, axis limits)', ok)
                if 'restTip' in js['machine']:
                    rt = js['machine']['restTip']
                    K.check(f'{rid}: machine rest tip', max(abs(a - b) for a, b in zip(m['rest_tip'], (rt[0], -rt[2], rt[1])))
                            < TOL, f"{[round(v, 5) for v in m['rest_tip']]}")
                for case in js.get('moveTool') or []:
                    x, h, z = case['p']
                    p = (x, -z, h)
                    if 'error' in case:
                        try:
                            r.reset()
                            r.move_tool(p)
                            K.check(f'{rid}: move_tool {p} rejected', False)
                        except ValueError:
                            K.check(f'{rid}: move_tool {p} rejected', True)
                        continue
                    r.reset()
                    r.move_tool(p)
                    tip, wtip = r.tool_tip(), r.tool_tip(True)
                    jt, jw = case['tip'], case['world']
                    e1 = max(abs(a - b) for a, b in zip(tip, (jt[0], -jt[2], jt[1])))
                    e2 = max(abs(a - b) for a, b in zip(wtip, (jw[0], -jw[2], jw[1])))
                    K.check(f'{rid}: move_tool {tuple(round(v, 3) for v in p)} -> tool_tip (bed frame, world)',
                            e1 < TOL and e2 < TOL, f'{e1:.2e} / {e2:.2e}')
            for clip, times in js['samples'].items():
                if clip == 'filament-feed' and r.filament is None:
                    print(f'SKIP {rid}: {clip} (the live filament is filament.js\'s: the fabrication port installs it)')
                    continue
                for t, s in times.items():
                    if 'error' in s:
                        continue
                    try:
                        r.sample(clip, float(t))
                    except Exception as e:  # noqa: BLE001
                        K.check(f'{rid}: sample {clip} {t}', False, repr(e))
                        continue
                    w, miss, where = compare_worlds(r, s['worlds'])
                    ok = w < TOL and miss == 0
                    stw = max((abs(r.state.get(n, 1e9) - v) for n, v in s['state'].items()), default=0.0)
                    K.check(f'{rid}: sample {clip} t={t}: {len(s["worlds"])} world matrices + joint state', ok
                            and stw < 1e-7 and set(r.state) == set(s['state']),
                            f'worst {w:.2e} at {where}, {miss} unmatched, state {stw:.1e}')
            for clip in r.clips:
                if clip == 'filament-feed' and r.filament is None:
                    continue
                r.sample(clip, 2)
                a = snapshot(r)
                r.sample(clip, 8)
                r.sample(clip, 2)
                b = snapshot(r)
                d = max((K.mdiff(x, y) for x, y in zip(a, b)), default=0.0)
                K.check(f'{rid}: {clip} is deterministic and seekable', d < 1e-6, f'{d:.1e}')
            mapped = set()
            for name, faces in r.part_for_face.items():
                o = bpy.data.objects.get(name)
                if o is not None and o.type == 'MESH':
                    if len(faces) != len(o.data.polygons):
                        K.check(f'{rid}: triangle ownership length of {name}', False)
                    mapped.update(faces)
            unmapped = [p for p in r.parts() if p not in mapped and any(r.part_for_face.values())]
            K.check(f'{rid}: every part has mapped triangles', not unmapped, f'{unmapped[:3]}')
            rec = {'clips': r.clips, 'stats': st}
        except Exception:  # noqa: BLE001
            K.check(f'{rid}: parity run', False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
        summary[rid] = rec
        r.dispose()
    K.save_results('js_parity_subset' if ONLY else 'js_parity', {'models': summary, 'filament_js_parts': RESULTS_FIL})


main()
